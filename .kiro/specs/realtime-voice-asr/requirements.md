# 需求文档：实时语音输入与ASR流式转录（Realtime Voice ASR）

## 简介

实时语音输入与ASR流式转录模块为 SuperInsight 访谈系统新增长时间实时语音录入能力。用户在访谈会话页面按下录音按钮后，浏览器通过 MediaRecorder API 持续采集音频，经 WebSocket 流式传输至后端；后端使用 faster-whisper（CTranslate2）对音频分片进行近实时转录，将部分转录结果推送回前端实时展示。随着转录文本累积，AI 定期分析已转录内容并生成访谈补全提纲，帮助用户发现遗漏话题。

本模块复用现有 `audio_transcriber.py` 中的 faster-whisper 模型，复用 `interview-infra` 子模块的 JWT 认证，并与 `intelligent-interview` 子模块的访谈会话上下文集成。

## 术语表

- **Voice_Recorder**：浏览器端语音录制组件，基于 MediaRecorder API 采集音频数据
- **Audio_Streamer**：WebSocket 音频流传输通道，负责将浏览器采集的音频分片发送至后端
- **ASR_Engine**：后端自动语音识别引擎，基于 faster-whisper（CTranslate2）对音频分片执行转录
- **Transcription_Display**：前端转录文本实时展示区域，显示部分转录结果和最终转录结果
- **Outline_Generator**：AI 提纲生成器，基于累积转录文本分析访谈内容并生成补全提纲
- **Interview_Session**：访谈会话，复用 `intelligent-interview` 子模块中的会话实例
- **Audio_Chunk**：音频分片，浏览器端按固定时间间隔切割的音频数据片段
- **Partial_Transcript**：部分转录结果，ASR_Engine 对单个音频分片的转录输出
- **Accumulated_Transcript**：累积转录文本，当前录音会话中所有部分转录结果的拼接文本
- **Completion_Outline**：补全提纲，AI 基于累积转录文本生成的结构化访谈补充建议

## 依赖子模块

| 子模块 | 提供能力 |
|--------|----------|
| `intelligent-interview` | Interview_Session 会话上下文、SessionManager |
| `interview-infra` | InterviewSecurity（JWT 认证、多租户隔离） |
| 现有 `audio_transcriber.py` | faster-whisper 模型加载、音频格式转换 |

## 需求

### 需求 1：浏览器端实时语音录制

**用户故事：** 作为访谈用户，我希望在访谈对话页面通过按钮控制语音录制的开始和停止，以便用语音代替打字输入访谈内容。

#### 验收标准

1. WHEN 用户点击录音按钮, THE Voice_Recorder SHALL 请求浏览器麦克风权限并开始采集音频数据
2. WHILE Voice_Recorder 正在录音, THE Voice_Recorder SHALL 在界面上展示录音状态指示（录音时长和动态波形图标）
3. WHEN 用户点击停止按钮, THE Voice_Recorder SHALL 停止音频采集并关闭麦克风资源
4. THE Voice_Recorder SHALL 使用 MediaRecorder API 以 webm/opus 格式采集音频，每 1 秒生成一个 Audio_Chunk
5. IF 浏览器不支持 MediaRecorder API 或用户拒绝麦克风权限, THEN THE Voice_Recorder SHALL 展示明确的错误提示信息并保持文字输入可用
6. WHILE Voice_Recorder 正在录音, THE Voice_Recorder SHALL 支持持续录音至少 30 分钟而不中断

### 需求 2：WebSocket 音频流式传输

**用户故事：** 作为访谈用户，我希望录制的音频能实时传输到后端进行转录，以便在说话的同时看到文字输出。

#### 验收标准

1. WHEN Voice_Recorder 开始录音, THE Audio_Streamer SHALL 建立 WebSocket 连接至后端 ASR 端点（`/api/interview/sessions/{session_id}/asr`）
2. THE Audio_Streamer SHALL 在 WebSocket 握手阶段通过查询参数传递 JWT token 进行身份认证
3. WHEN Voice_Recorder 生成一个 Audio_Chunk, THE Audio_Streamer SHALL 立即通过 WebSocket 以二进制帧发送该分片
4. IF WebSocket 连接断开, THEN THE Audio_Streamer SHALL 在 3 秒内自动尝试重连，最多重试 3 次
5. IF 重连 3 次均失败, THEN THE Audio_Streamer SHALL 停止录音并向用户展示连接失败提示
6. WHEN 用户停止录音, THE Audio_Streamer SHALL 发送结束信号并关闭 WebSocket 连接

### 需求 3：后端 ASR 流式转录

**用户故事：** 作为系统，我需要接收流式音频数据并使用 faster-whisper 进行近实时转录，以便将转录结果推送给前端。

#### 验收标准

1. THE ASR_Engine SHALL 提供 WebSocket 端点 `/api/interview/sessions/{session_id}/asr` 接收音频流
2. WHEN ASR_Engine 收到 WebSocket 连接请求, THE ASR_Engine SHALL 验证 JWT token 的有效性和会话归属
3. WHEN ASR_Engine 累积收到足够的 Audio_Chunk（约 2-3 秒音频）, THE ASR_Engine SHALL 使用 faster-whisper 对该段音频执行转录
4. WHEN 转录完成一个片段, THE ASR_Engine SHALL 通过 WebSocket 以 JSON 格式推送 Partial_Transcript（包含 text、start_time、end_time 字段）
5. THE ASR_Engine SHALL 使用 faster-whisper 内置的 VAD（语音活动检测）过滤静音片段，减少无效转录
6. IF 转录过程中发生错误, THEN THE ASR_Engine SHALL 通过 WebSocket 推送错误消息（包含 error_code 和 error_message 字段），不中断连接
7. WHEN 用户发送结束信号, THE ASR_Engine SHALL 转录剩余缓冲区音频并推送最终结果，然后关闭连接

### 需求 4：前端转录文本实时展示

**用户故事：** 作为访谈用户，我希望在录音过程中实时看到语音转文字的结果，以便确认系统正确理解了我的表述。

#### 验收标准

1. WHEN Audio_Streamer 收到 Partial_Transcript, THE Transcription_Display SHALL 在 200 毫秒内将转录文本追加展示在转录区域
2. THE Transcription_Display SHALL 在对话区域上方或内嵌位置展示实时转录文本，与现有聊天消息列表视觉区分
3. WHILE Voice_Recorder 正在录音, THE Transcription_Display SHALL 持续滚动至最新转录文本位置
4. WHEN 用户停止录音, THE Transcription_Display SHALL 将完整的 Accumulated_Transcript 作为一条用户消息自动提交至访谈会话

### 需求 5：AI 实时分析与补全提纲生成

**用户故事：** 作为访谈用户，我希望 AI 能在我说话的过程中分析内容并给出补全提纲，以便我知道还需要补充哪些信息。

#### 验收标准

1. WHILE Voice_Recorder 正在录音, THE Outline_Generator SHALL 每当 Accumulated_Transcript 新增超过 15 秒的转录内容时触发一次分析
2. WHEN Outline_Generator 触发分析, THE Outline_Generator SHALL 基于 Accumulated_Transcript 和当前 Interview_Session 上下文生成 Completion_Outline
3. THE Completion_Outline SHALL 包含结构化的主题列表，每个主题包含 topic_name（主题名称）和 description（补充说明）字段
4. WHEN 新的 Completion_Outline 生成完成, THE Outline_Generator SHALL 通过 WebSocket 推送至前端并替换之前的提纲内容
5. THE Transcription_Display SHALL 在录音界面侧边或下方展示最新的 Completion_Outline
6. IF Accumulated_Transcript 长度不足 30 秒, THEN THE Outline_Generator SHALL 不触发分析，等待更多内容积累

### 需求 6：录音会话与访谈会话集成

**用户故事：** 作为访谈用户，我希望语音录入的内容能无缝融入访谈对话流程，以便语音和文字输入可以交替使用。

#### 验收标准

1. WHEN 用户停止录音且 Accumulated_Transcript 非空, THE Interview_Session SHALL 将 Accumulated_Transcript 作为用户消息发送至会话（等同于文字输入）
2. WHILE Voice_Recorder 正在录音, THE Interview_Session SHALL 禁用文字输入框，防止同时输入
3. WHEN 录音消息发送至会话后, THE Interview_Session SHALL 按照现有对话流程生成 AI 响应和隐含缺口检测
4. THE Interview_Session SHALL 在消息历史中标记语音输入的消息（展示麦克风图标），与文字输入消息区分
5. IF Interview_Session 已结束（状态为 completed 或 terminated）, THEN THE Voice_Recorder SHALL 禁用录音按钮并展示会话已结束提示
