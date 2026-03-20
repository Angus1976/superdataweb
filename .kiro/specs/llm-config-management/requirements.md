# 需求文档：LLM 配置管理与场景提示词管理

## 简介

本功能为 SuperInsight 访谈系统引入真实的大语言模型（LLM）集成能力，替换当前 `SessionManager.send_message()` 中的硬编码桩响应。管理员可在后台配置 LLM 服务商参数（API Key、Base URL、模型名称等），并增强现有场景提示词的结构化管理。整体设计遵循项目已有的百度网盘配置模式：数据库存储租户级配置 + 环境变量作为回退默认值 + 管理员后台 UI + 连通性测试。

## 术语表

- **LLM_Config_Service**：后端 LLM 配置管理服务，负责配置的 CRUD、加密存储和连通性测试
- **LLM_Client_Service**：后端 LLM 调用客户端，负责读取配置并向 LLM 服务商发起 API 请求
- **LLM_Config_Page**：前端管理员 LLM 配置页面
- **Prompt_Manager**：场景提示词管理模块，负责结构化提示词的组装和预览
- **Session_Manager**：访谈会话管理器（已有 `SessionManager` 类），负责处理用户消息并返回 AI 响应
- **Industry_Template_Page**：已有的行业模板管理页面，将增强提示词编辑功能
- **Tenant**：租户，系统中的企业隔离单元
- **OpenAI_Compatible_API**：兼容 OpenAI Chat Completions 接口规范的 LLM 服务（如 OpenAI、DeepSeek、通义千问等）

## 需求

### 需求 1：LLM 服务商配置存储

**用户故事：** 作为管理员，我希望能配置 LLM 服务商的连接参数，以便系统能调用真实的大语言模型进行访谈。

#### 验收标准

1. THE LLM_Config_Service SHALL 提供按租户存储 LLM 配置的能力，配置项包括：provider_name（服务商名称）、api_key、base_url、model_name、temperature（0.0-2.0）、max_tokens（1-32000）
2. WHEN 管理员提交 LLM 配置时，THE LLM_Config_Service SHALL 将 api_key 以加密形式存储到数据库中，读取时返回掩码显示（仅显示前4位和后4位）
3. WHEN 数据库中不存在当前租户的 LLM 配置时，THE LLM_Config_Service SHALL 回退读取环境变量（LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_NAME、LLM_TEMPERATURE、LLM_MAX_TOKENS）作为默认值
4. WHEN 管理员更新已有配置时，THE LLM_Config_Service SHALL 使用 UPSERT 语义写入数据库，确保每个租户仅保留一条配置记录
5. THE LLM_Config_Service SHALL 创建 `llm_config` 数据库表，包含 tenant_id（主键）、provider_name、encrypted_api_key、base_url、model_name、temperature、max_tokens、created_at、updated_at 字段

### 需求 2：LLM 连通性测试

**用户故事：** 作为管理员，我希望在保存配置前能测试 LLM 服务的连通性，以便确认配置参数正确可用。

#### 验收标准

1. WHEN 管理员点击"测试连接"按钮时，THE LLM_Config_Service SHALL 使用提交的配置参数向 LLM 服务商发送一条简短的测试请求（如发送"你好"并验证响应）
2. WHEN 测试请求在 15 秒内收到有效响应时，THE LLM_Config_Service SHALL 返回 `{"ok": true, "message": "连接成功", "model": "<模型名称>", "response_time_ms": <响应耗时>}`
3. IF LLM 服务商返回认证错误（HTTP 401/403），THEN THE LLM_Config_Service SHALL 返回 `{"ok": false, "message": "API Key 无效或无权限"}`
4. IF 测试请求超时或网络不可达，THEN THE LLM_Config_Service SHALL 返回 `{"ok": false, "message": "连接超时，请检查 Base URL 是否正确"}`

### 需求 3：LLM 配置管理页面

**用户故事：** 作为管理员，我希望在后台有一个专门的页面来管理 LLM 配置，以便直观地设置和测试 LLM 服务。

#### 验收标准

1. THE LLM_Config_Page SHALL 在管理员后台侧边栏中显示"LLM 配置"菜单项，路由路径为 `/admin/llm-config`
2. THE LLM_Config_Page SHALL 提供表单，包含以下字段：服务商名称（下拉选择：OpenAI / DeepSeek / 通义千问 / 自定义）、API Key（密码输入框）、Base URL（文本输入框，带默认值提示）、模型名称（文本输入框）、Temperature（数字滑块，范围 0.0-2.0，步长 0.1）、Max Tokens（数字输入框，范围 1-32000）
3. WHEN 页面加载时，THE LLM_Config_Page SHALL 调用后端接口获取当前配置并回填表单，API Key 显示为掩码形式
4. WHEN 管理员选择不同服务商时，THE LLM_Config_Page SHALL 自动填充该服务商的默认 Base URL（如 OpenAI 为 `https://api.openai.com/v1`，DeepSeek 为 `https://api.deepseek.com/v1`）
5. THE LLM_Config_Page SHALL 提供"测试连接"按钮，点击后显示加载状态，并将测试结果以成功/失败样式展示
6. THE LLM_Config_Page SHALL 提供"保存配置"按钮，保存成功后显示成功提示
7. WHILE 当前用户角色不是 admin 时，THE LLM_Config_Page SHALL 不在侧边栏中显示，直接访问路由时重定向到首页

### 需求 4：结构化场景提示词管理

**用户故事：** 作为管理员，我希望能以结构化方式编辑场景提示词，以便更精确地控制 AI 访谈行为。

#### 验收标准

1. THE Industry_Template_Page SHALL 在模板编辑弹窗中将"系统提示词"字段替换为结构化编辑器，包含四个分区：角色定义（role_definition）、任务描述（task_description）、行为规则（behavior_rules）、输出格式（output_format）
2. THE Prompt_Manager SHALL 将四个分区内容按固定模板拼接为完整的 system_prompt 字符串，拼接格式为：`## 角色定义\n{role_definition}\n\n## 任务描述\n{task_description}\n\n## 行为规则\n{behavior_rules}\n\n## 输出格式\n{output_format}`
3. WHEN 编辑已有模板时，THE Prompt_Manager SHALL 尝试将现有 system_prompt 按分区标记解析回四个字段；解析失败时将完整内容填入"角色定义"字段，其余字段留空
4. THE Industry_Template_Page SHALL 在结构化编辑器下方提供"预览完整提示词"折叠面板，实时显示拼接后的完整 system_prompt
5. THE Prompt_Manager SHALL 对拼接后的 system_prompt 进行长度校验，总长度不超过 8000 个字符

### 需求 5：提示词预览与测试

**用户故事：** 作为管理员，我希望能预览和测试提示词效果，以便在正式使用前验证提示词质量。

#### 验收标准

1. THE Industry_Template_Page SHALL 在模板编辑弹窗中提供"测试提示词"按钮
2. WHEN 管理员点击"测试提示词"按钮时，THE Prompt_Manager SHALL 使用当前租户的 LLM 配置，将拼接后的 system_prompt 作为系统消息、加上一条固定的测试用户消息（"请简单介绍你的角色和能力"）发送给 LLM
3. WHEN LLM 返回响应时，THE Industry_Template_Page SHALL 在弹窗中以对话气泡形式展示测试结果
4. IF 当前租户未配置 LLM 服务，THEN THE Industry_Template_Page SHALL 显示提示"请先在 LLM 配置页面完成服务商配置"并禁用测试按钮

### 需求 6：LLM 客户端服务层

**用户故事：** 作为开发者，我希望有一个统一的 LLM 客户端服务层，以便所有需要调用 LLM 的模块共享配置和错误处理逻辑。

#### 验收标准

1. THE LLM_Client_Service SHALL 提供异步方法 `chat_completion(tenant_id, messages, temperature, max_tokens)` 用于发送聊天补全请求，messages 参数为 `[{"role": "system"|"user"|"assistant", "content": str}]` 格式
2. THE LLM_Client_Service SHALL 从数据库加载当前租户的 LLM 配置，数据库无配置时回退到环境变量
3. THE LLM_Client_Service SHALL 提供流式响应方法 `chat_completion_stream(tenant_id, messages, temperature, max_tokens)`，返回异步生成器逐块产出响应文本
4. IF LLM 服务商返回 HTTP 429（速率限制），THEN THE LLM_Client_Service SHALL 等待 Retry-After 头指定的时间后重试，最多重试 2 次
5. IF LLM 服务商返回非 2xx 响应且非速率限制错误，THEN THE LLM_Client_Service SHALL 抛出包含状态码和错误消息的 `LLMServiceError` 异常
6. IF 当前租户未配置 LLM 服务且环境变量也未设置，THEN THE LLM_Client_Service SHALL 抛出 `LLMNotConfiguredError` 异常，消息为"LLM 服务未配置，请联系管理员"
7. THE LLM_Client_Service SHALL 使用 httpx.AsyncClient 发送请求，请求超时设置为 60 秒

### 需求 7：替换桩响应为真实 LLM 调用

**用户故事：** 作为用户，我希望在访谈中获得真实的 AI 响应，而不是固定的模板回复。

#### 验收标准

1. WHEN 用户在访谈会话中发送消息时，THE Session_Manager SHALL 调用 LLM_Client_Service 获取 AI 响应，替换当前的硬编码桩响应
2. THE Session_Manager SHALL 构建消息列表：第一条为 system 消息（使用当前会话关联模板的 system_prompt），后续为历史对话消息（user/assistant 交替），最后追加当前用户消息
3. WHEN 会话启动时，THE Session_Manager SHALL 从 Redis 缓存或数据库加载会话关联的行业模板 system_prompt
4. IF LLM_Client_Service 抛出 LLMNotConfiguredError，THEN THE Session_Manager SHALL 返回友好提示"AI 服务尚未配置，请联系管理员完成 LLM 设置"作为 AI 响应，HTTP 状态码保持 200
5. IF LLM_Client_Service 抛出 LLMServiceError，THEN THE Session_Manager SHALL 返回"AI 服务暂时不可用，请稍后重试"作为 AI 响应，并记录错误日志

### 需求 8：流式响应支持

**用户故事：** 作为用户，我希望在访谈中看到 AI 逐字输出响应，以获得更流畅的交互体验。

#### 验收标准

1. THE Session_Manager SHALL 提供 SSE（Server-Sent Events）端点 `POST /api/interview/sessions/{session_id}/messages/stream`，支持流式返回 AI 响应
2. WHEN 客户端请求流式端点时，THE Session_Manager SHALL 调用 LLM_Client_Service 的流式方法，将每个文本块以 SSE `data:` 事件发送给客户端
3. WHEN 流式响应完成时，THE Session_Manager SHALL 发送 `data: [DONE]` 事件标记结束，并将完整响应存储到消息历史中
4. IF 流式传输过程中发生错误，THEN THE Session_Manager SHALL 发送 `data: {"error": "AI 响应中断，请重试"}` 事件并关闭连接
