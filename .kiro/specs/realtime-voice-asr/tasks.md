# 实现计划：实时语音输入与ASR流式转录

## 概述

基于设计文档，按后端数据模型 → 音频缓冲 → WebSocket 处理器 → AI 提纲 → 路由注册 → 前端组件的顺序逐步实现。每一步构建在前一步之上，确保无孤立代码。后端使用 Python（FastAPI），前端使用 TypeScript（React 19 + Ant Design）。

## Tasks

- [x] 1. 创建后端 Pydantic 数据模型
  - [x] 1.1 创建 `src/interview/asr_models.py`，定义 `PartialTranscript`、`OutlineTopic`、`CompletionOutline`、`ASRWebSocketMessage`、`ASRControlMessage` 模型
    - 按照设计文档中的数据模型部分实现所有字段和类型约束
    - `PartialTranscript`: text(str), start_time(float), end_time(float), is_final(bool=False)
    - `OutlineTopic`: topic_name(str), description(str)
    - `CompletionOutline`: topics(list[OutlineTopic])
    - `ASRWebSocketMessage`: type(str), 以及各类型对应的可选字段
    - `ASRControlMessage`: type(str)
    - _需求: 3.4, 5.3_

  - [x] 1.2 编写 Property 6 属性测试：转录结果 JSON 格式完整性
    - **Property 6: 转录结果 JSON 格式完整性**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机 PartialTranscript，验证序列化后的 JSON 包含 `type="transcript"`、非空 `text`、`start_time >= 0`、`end_time > start_time`
    - **验证: 需求 3.4**

  - [x] 1.3 编写 Property 11 属性测试：提纲结构完整性
    - **Property 11: 提纲结构完整性**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机 OutlineTopic 列表，验证 CompletionOutline 中每个 topic 的 `topic_name` 和 `description` 非空
    - **验证: 需求 5.3**

- [x] 2. 实现 AudioBufferManager 音频缓冲管理器
  - [x] 2.1 创建 `src/interview/audio_buffer.py`，实现 `AudioBufferManager` 类
    - `__init__(target_duration_sec=2.5)`: 初始化缓冲区和目标时长
    - `add_chunk(data: bytes)`: 添加音频分片到缓冲区
    - `is_ready() -> bool`: 基于 opus 码率估算判断是否达到目标时长
    - `flush() -> bytes | None`: 取出并清空缓冲区，返回合并数据；空缓冲区返回 None
    - `estimate_duration() -> float`: 基于 opus 平均码率（~32kbps）估算当前缓冲区时长
    - _需求: 3.3, 3.7_

  - [x] 2.2 编写 Property 5 属性测试：音频缓冲区累积与刷新
    - **Property 5: 音频缓冲区累积与刷新**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机字节序列列表，验证：(1) 累积达到阈值时 `is_ready()` 返回 True；(2) `flush()` 返回所有分片的拼接；(3) flush 后缓冲区为空
    - **验证: 需求 3.3, 3.7**

- [x] 3. 实现 OutlineGenerator AI 提纲生成器
  - [x] 3.1 创建 `src/interview/outline_generator.py`，实现 `OutlineGenerator` 类
    - `generate(accumulated_transcript: str, session_context: dict) -> CompletionOutline`: 基于累积转录文本和会话上下文生成补全提纲
    - 使用现有 LLM 调用方式（参考 `system.py` 中的 AI 调用模式）
    - 返回结构化的 `CompletionOutline`（含 `topics` 列表）
    - 异常时返回空提纲或静默跳过，不影响转录流程
    - _需求: 5.1, 5.2, 5.3_

  - [x] 3.2 编写 Property 10 属性测试：AI 提纲触发条件
    - **Property 10: AI 提纲触发条件**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机 (总时长, 新增时长) 对，验证仅在总时长 ≥ 30 秒且新增时长 ≥ 15 秒时触发
    - **验证: 需求 5.1, 5.6**

- [x] 4. 实现 ASRWebSocketHandler WebSocket 会话处理器
  - [x] 4.1 创建 `src/interview/asr_handler.py`，实现 `ASRWebSocketHandler` 类
    - `__init__(websocket, session_id, token)`: 初始化 WebSocket、缓冲区、累积文本等状态
    - `handle()`: 主循环 — 认证 → 接收音频/控制消息 → 转录 → 推送结果
    - `_authenticate() -> str`: 使用 `_security.get_current_tenant(token)` 验证 JWT，验证会话归属，失败时以对应关闭码（4008/4004/4009）关闭连接
    - `_process_audio_chunk(data: bytes)`: 将音频分片加入 AudioBufferManager，缓冲区满时触发转录
    - `_transcribe_buffer() -> str | None`: 调用 `_transcriber`（复用 router.py 中的单例）转录缓冲区音频
    - `_send_transcript(text, start_time, end_time, is_final)`: 推送 `{"type":"transcript",...}` JSON 帧
    - `_maybe_generate_outline()`: 检查触发条件（总时长 ≥ 30s 且新增 ≥ 15s），调用 OutlineGenerator
    - `_flush_and_close()`: 转录剩余缓冲区，通过 `_session_mgr.send_message()` 提交累积文本，推送 AI 响应，关闭连接
    - 转录错误时推送 `{"type":"error",...}` 错误帧，不中断连接
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 5.1, 5.6, 6.1_

  - [x] 4.2 编写 Property 4 属性测试：JWT 认证拒绝无效 Token
    - **Property 4: JWT 认证拒绝无效 Token**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机字符串 token，验证无效 token 被拒绝
    - **验证: 需求 3.2**

  - [x] 4.3 编写 Property 7 属性测试：转录错误不中断连接
    - **Property 7: 转录错误不中断连接**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机异常类型，验证错误消息包含 `type="error"`、非空 `error_code` 和 `error_message`
    - **验证: 需求 3.6**

  - [x] 4.4 编写 Property 9 属性测试：录音结束提交累积文本
    - **Property 9: 录音结束提交累积文本**
    - 在 `tests/interview/test_asr_properties.py` 中使用 Hypothesis 生成随机文本序列，验证停止录音时累积文本通过 `send_message` 提交且 metadata 包含 `source: "voice"`
    - **验证: 需求 4.4, 6.1, 6.4**

- [x] 5. 检查点 - 确保后端所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [x] 6. 创建 ASR WebSocket 路由并注册到 FastAPI 应用
  - [x] 6.1 创建 `src/interview/asr_router.py`，定义 WebSocket 端点 `/api/interview/sessions/{session_id}/asr`
    - 接收 query param `token` 用于 JWT 认证
    - 实例化 `ASRWebSocketHandler` 并调用 `handle()`
    - _需求: 3.1, 2.1, 2.2_

  - [x] 6.2 在 `src/interview/main.py` 中注册 `asr_router`
    - 导入 `asr_router` 并通过 `app.include_router(asr_router)` 注册
    - _需求: 3.1_

- [x] 7. 创建前端 TypeScript 类型定义
  - [x] 7.1 创建 `src/frontend/types/asr.ts`，定义 `PartialTranscript`、`OutlineTopic`、`CompletionOutline`、`ASRWebSocketMessage` 接口
    - 按照设计文档中的 TypeScript 类型部分实现
    - _需求: 3.4, 5.3_

- [x] 8. 实现前端 VoiceRecorder 组件
  - [x] 8.1 创建 `src/frontend/components/VoiceRecorder.tsx`
    - 使用 MediaRecorder API 以 webm/opus 格式采集音频，每 1 秒生成一个 Audio_Chunk
    - 录音按钮控制开始/停止，展示录音状态（时长、动态图标）
    - 建立 WebSocket 连接至 `/api/interview/sessions/{session_id}/asr?token=xxx`
    - 以二进制帧发送 Audio_Chunk
    - 接收并解析 JSON 帧（transcript/outline/error/session_message）
    - WebSocket 断开时自动重连（最多 3 次，间隔 3 秒），全部失败后停止录音并提示
    - 停止录音时发送 `{"type":"stop"}` 文本帧
    - 浏览器不支持 MediaRecorder 或麦克风权限拒绝时展示错误提示
    - 录音超过 30 分钟自动停止
    - 会话已结束时禁用录音按钮
    - 所有 UI 文本使用中文
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.5_

  - [x] 8.2 编写 Property 1 属性测试：WebSocket URL 包含 JWT Token
    - **Property 1: WebSocket URL 包含 JWT Token**
    - 在 `src/frontend/__tests__/asr-websocket.test.ts` 中使用 fast-check 生成随机 JWT 字符串，验证构建的 URL query param 包含 `token` 参数且值一致
    - **验证: 需求 2.2**

  - [x] 8.3 编写 Property 2 属性测试：音频分片以二进制帧发送
    - **Property 2: 音频分片以二进制帧发送**
    - 在 `src/frontend/__tests__/asr-websocket.test.ts` 中使用 fast-check 生成随机 Uint8Array，验证 WebSocket 发送的数据与原始 Audio_Chunk 字节一致
    - **验证: 需求 2.3**

  - [x] 8.4 编写 Property 3 属性测试：WebSocket 重连次数上限
    - **Property 3: WebSocket 重连次数上限**
    - 在 `src/frontend/__tests__/asr-websocket.test.ts` 中使用 fast-check 生成随机断开事件序列，验证重连次数不超过 3 次
    - **验证: 需求 2.4**

- [x] 9. 实现前端 TranscriptionPanel 组件
  - [x] 9.1 创建 `src/frontend/components/TranscriptionPanel.tsx`
    - 接收 `transcripts` 数组，按序展示转录文本
    - 录音中自动滚动至最新文本
    - 展示 `CompletionOutline`（AI 提纲），新提纲替换旧提纲
    - 与现有聊天消息列表视觉区分（使用不同背景色/边框）
    - 所有 UI 文本使用中文
    - _需求: 4.1, 4.2, 4.3, 5.4, 5.5_

  - [x] 9.2 编写 Property 8 属性测试：转录文本按序追加
    - **Property 8: 转录文本按序追加**
    - 在 `src/frontend/__tests__/asr-display.test.ts` 中使用 fast-check 生成随机 PartialTranscript 序列，验证展示顺序与接收顺序一致
    - **验证: 需求 4.1**

  - [x] 9.3 编写 Property 12 属性测试：新提纲替换旧提纲
    - **Property 12: 新提纲替换旧提纲**
    - 在 `src/frontend/__tests__/asr-display.test.ts` 中使用 fast-check 生成连续 CompletionOutline，验证前端始终展示最新提纲
    - **验证: 需求 5.4**

- [x] 10. 集成 VoiceRecorder 和 TranscriptionPanel 到 InterviewSessionPage
  - [x] 10.1 修改 `src/frontend/pages/InterviewSessionPage.tsx`，集成语音录入功能
    - 在输入区域添加录音按钮（使用 `AudioOutlined` 图标，已导入）
    - 录音时禁用文字输入框（TextArea disabled）
    - 录音结束后将累积文本作为用户消息提交至会话
    - 在消息历史中标记语音输入消息（展示麦克风图标）
    - 会话已结束时禁用录音按钮
    - 在对话区域上方或内嵌位置展示 TranscriptionPanel
    - 管理 transcripts、outline、isRecording 等状态
    - _需求: 4.2, 4.4, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 10.2 编写 Property 13 属性测试：录音期间禁用文字输入
    - **Property 13: 录音期间禁用文字输入**
    - 在 `src/frontend/__tests__/asr-display.test.ts` 中使用 fast-check 生成随机 isRecording 布尔值，验证录音时文字输入框 disabled
    - **验证: 需求 6.2**

- [x] 11. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 备注

- 标记 `*` 的子任务为可选测试任务，可跳过以加速 MVP 开发
- 每个任务引用了具体的需求编号，确保可追溯性
- 属性测试验证设计文档中定义的 13 个正确性属性
- 后端属性测试使用 Hypothesis，前端属性测试使用 fast-check（已在 devDependencies 中）
- 检查点任务确保增量验证
