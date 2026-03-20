# 实施计划：LLM 配置管理与场景提示词管理

## 概述

按增量方式实现 LLM 配置管理功能：先建数据层和核心服务，再实现 API 路由和前端页面，最后集成到 SessionManager 并添加 SSE 流式端点。每个任务构建在前一个任务之上，确保无孤立代码。

## 任务

- [x] 1. 数据库迁移与 Pydantic 模型
  - [x] 1.1 创建数据库迁移文件 `migrations/008_create_llm_config.sql`
    - 创建 `llm_config` 表，包含 tenant_id（主键）、provider_name、encrypted_api_key、base_url、model_name、temperature（NUMERIC(3,1)）、max_tokens、created_at、updated_at
    - 添加 CHECK 约束：temperature ∈ [0.0, 2.0]，max_tokens ∈ [1, 32000]
    - _需求: 1.5_
  - [x] 1.2 创建 Pydantic 模型文件 `src/interview/llm_models.py`
    - 定义 LLMConfigRequest、LLMConfigResponse、ConnectivityResult、StructuredPromptRequest、ChatMessage 模型
    - 定义 LLMServiceError 和 LLMNotConfiguredError 异常类
    - _需求: 1.1, 2.2, 2.3, 2.4, 4.2, 6.1, 6.5, 6.6_

- [x] 2. LLM 配置服务（llm_config_service.py）
  - [x] 2.1 实现 LLMConfigService 类
    - 实现 encrypt_api_key / decrypt_api_key（Fernet 对称加密，密钥从 LLM_ENCRYPTION_KEY 或 JWT_SECRET 派生）
    - 实现 mask_api_key（前4位 + **** + 后4位，≤8 位返回 ****）
    - 实现 save_config（UPSERT 语义，加密 api_key 后写入 DB）
    - 实现 get_config（读取 DB，api_key 返回掩码）
    - 实现 get_config_decrypted（读取 DB，api_key 解密，仅内部使用）
    - 实现 get_effective_config（优先 DB，回退环境变量 LLM_API_KEY/LLM_BASE_URL/LLM_MODEL_NAME/LLM_TEMPERATURE/LLM_MAX_TOKENS，均无则抛 LLMNotConfiguredError）
    - 实现 test_connectivity（使用 httpx 向 LLM 服务商发送测试请求，返回 ConnectivityResult）
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_
  - [x] 2.2 编写属性测试：API Key 加密往返与掩码显示
    - **Property 2: API Key 加密往返与掩码显示**
    - 使用 Hypothesis 生成随机 api_key 字符串，验证 encrypt→decrypt 往返一致性和 mask 格式
    - **验证: 需求 1.2**
  - [x] 2.3 编写属性测试：环境变量回退
    - **Property 3: 环境变量回退**
    - 模拟无 DB 配置场景，设置随机环境变量，验证 get_effective_config 回退行为；环境变量也未设置时验证抛出 LLMNotConfiguredError
    - **验证: 需求 1.3, 6.2, 6.6**

- [x] 3. 提示词管理器（prompt_manager.py）
  - [x] 3.1 实现 PromptManager 类
    - 实现 assemble（四分区拼接为完整 system_prompt，格式：## 角色定义\n{}\n\n## 任务描述\n{}\n\n## 行为规则\n{}\n\n## 输出格式\n{}）
    - 实现 parse（将完整 system_prompt 解析回四分区；解析失败时全部填入 role_definition，其余为空）
    - 实现 validate_length（校验总长度 ≤ 8000 字符）
    - _需求: 4.2, 4.3, 4.5_
  - [x] 3.2 编写属性测试：提示词组装/解析往返一致性
    - **Property 4: 提示词组装/解析往返一致性**
    - 使用 Hypothesis 生成随机四分区字符串（不含分区标记），验证 assemble→parse 往返；生成不含标记的随机字符串验证 fallback
    - **验证: 需求 4.2, 4.3**
  - [x] 3.3 编写属性测试：提示词长度校验
    - **Property 5: 提示词长度校验**
    - 生成随机长度字符串，验证 validate_length 返回值与 len() <= 8000 一致
    - **验证: 需求 4.5**

- [x] 4. 检查点 - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 5. LLM 客户端服务（llm_client.py）
  - [x] 5.1 实现 LLMClient 类
    - 注入 LLMConfigService 依赖
    - 实现 chat_completion（加载租户配置，构建 OpenAI 兼容请求，httpx.AsyncClient 发送，超时 60 秒）
    - 实现 chat_completion_stream（流式响应，返回 AsyncGenerator[str, None]）
    - 实现 429 重试逻辑（读取 Retry-After 头，最多重试 2 次）
    - 非 2xx 非 429 时抛出 LLMServiceError
    - 未配置时抛出 LLMNotConfiguredError
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
  - [x] 5.2 编写属性测试：LLM 错误状态码映射
    - **Property 7: LLM 错误状态码映射**
    - 生成随机非 2xx 非 429 状态码，mock httpx 响应，验证抛出 LLMServiceError 且包含正确状态码
    - **验证: 需求 6.5**
  - [x] 5.3 编写属性测试：消息列表构建顺序
    - **Property 8: 消息列表构建顺序**
    - 生成随机 system_prompt、随机长度历史消息列表、随机当前消息，验证构建结果结构：首条 system、中间历史、末条 user，总长度 = 1 + len(history) + 1
    - **验证: 需求 7.2**

- [x] 6. 后端 API 路由（llm_config_router.py）与 SessionManager 集成
  - [x] 6.1 创建 `src/interview/llm_config_router.py`
    - 实现 POST /api/llm-config/config（保存配置，admin 权限校验）
    - 实现 GET /api/llm-config/config（获取配置，api_key 掩码返回）
    - 实现 POST /api/llm-config/config/test（测试连通性，admin 权限校验）
    - 遵循 baidu_pan_router.py 的 _get_user_info + _require_admin 模式
    - _需求: 1.1, 1.2, 1.4, 2.1, 2.2, 2.3, 2.4, 3.7_
  - [x] 6.2 在 `src/interview/main.py` 中注册 llm_config_router
    - 导入并 include_router(llm_config_router)
    - _需求: 1.1_
  - [x] 6.3 增强 SessionManager.send_message() 集成 LLMClient
    - 在 `src/interview/system.py` 的 SessionManager 中注入 LLMClient 和 PromptManager
    - 构建消息列表：system（模板 prompt）+ 历史消息 + 当前用户消息
    - 调用 LLMClient.chat_completion() 替换硬编码桩响应
    - 捕获 LLMNotConfiguredError → 返回友好提示 "AI 服务尚未配置，请联系管理员完成 LLM 设置"
    - 捕获 LLMServiceError → 返回 "AI 服务暂时不可用，请稍后重试" + 记录错误日志
    - _需求: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [x] 6.4 添加 SSE 流式端点
    - 在 `src/interview/router.py` 中添加 POST /api/interview/sessions/{session_id}/messages/stream
    - 使用 FastAPI StreamingResponse + text/event-stream
    - 每个文本块发送 `data: {chunk}\n\n`，完成时发送 `data: [DONE]\n\n`，错误时发送 `data: {"error": "AI 响应中断，请重试"}\n\n`
    - 完整响应存储到消息历史
    - _需求: 8.1, 8.2, 8.3, 8.4_
  - [x] 6.5 编写属性测试：SSE 事件格式
    - **Property 9: SSE 事件格式**
    - 生成随机文本块，验证 SSE 格式化结果为 `data: {chunk}\n\n`；验证完成标记为 `data: [DONE]\n\n`
    - **验证: 需求 8.2, 8.3**

- [x] 7. 更新 docker-compose 环境变量
  - 在 `docker-compose.standalone.yml` 的 interview-service 环境变量中添加 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_NAME、LLM_TEMPERATURE、LLM_MAX_TOKENS、LLM_ENCRYPTION_KEY
  - 在 `src/interview/config.py` 的 Settings 类中添加对应属性
  - 在 `requirements.txt` 中添加 `cryptography>=41.0.0`（Fernet 加密依赖）
  - _需求: 1.3_

- [x] 8. 检查点 - 确保所有后端测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 9. 前端 LLM 配置页面
  - [x] 9.1 创建 `src/frontend/pages/LLMConfigPage.tsx`
    - 表单字段：服务商下拉（OpenAI / DeepSeek / 通义千问 / 自定义）、API Key 密码框、Base URL 文本框、模型名称文本框、Temperature 滑块（0.0-2.0，步长 0.1）、Max Tokens 数字输入框（1-32000）
    - 页面加载时调用 GET /api/llm-config/config 回填表单，API Key 显示掩码
    - 服务商切换自动填充默认 Base URL（OpenAI: https://api.openai.com/v1，DeepSeek: https://api.deepseek.com/v1，通义千问: https://dashscope.aliyuncs.com/compatible-mode/v1）
    - "测试连接"按钮调用 POST /api/llm-config/config/test，显示加载状态和结果
    - "保存配置"按钮调用 POST /api/llm-config/config，成功后显示提示
    - 所有 UI 文本使用中文
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [x] 9.2 添加前端路由和侧边栏菜单
    - 在 `src/frontend/routes/interviewRoutes.tsx` 中添加 `/admin/llm-config` 路由（ProtectedRoute requireAdmin）
    - 在 `src/frontend/layouts/InterviewLayout.tsx` 侧边栏 admin 菜单中添加"LLM 配置"项
    - 在 `src/frontend/services/api.ts` 中添加 llmConfigApi 函数（getConfig、saveConfig、testConnectivity）
    - _需求: 3.1, 3.7_

- [x] 10. 前端行业模板页面增强
  - [x] 10.1 增强 IndustryTemplatePage 模板编辑弹窗
    - 将单一 system_prompt TextArea 替换为四分区结构化编辑器（角色定义、任务描述、行为规则、输出格式）
    - 添加折叠面板实时预览拼接后的完整 system_prompt
    - 添加"测试提示词"按钮，调用 LLM 测试端点（POST /api/llm-config/config/test 或新增提示词测试端点）
    - 未配置 LLM 时禁用测试按钮并显示提示"请先在 LLM 配置页面完成服务商配置"
    - 添加长度校验提示（≤ 8000 字符）
    - _需求: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4_

- [x] 11. 前端属性测试与服务商映射验证
  - [x] 11.1 编写属性测试：服务商默认 URL 映射
    - **Property 6: 服务商默认 URL 映射**
    - 使用 fast-check 从已知服务商列表中随机选择，验证返回的默认 URL 与预期映射一致
    - **验证: 需求 3.4**
  - [x] 11.2 编写属性测试：配置保存/读取往返一致性
    - **Property 1: 配置保存/读取往返一致性**
    - 使用 Hypothesis 生成随机配置参数，验证 save→load 往返一致性（provider_name、base_url、model_name、temperature、max_tokens）；多次保存同一 tenant_id 验证仅保留一条记录
    - **验证: 需求 1.1, 1.4**

- [x] 12. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

## 备注

- 标记 `*` 的任务为可选，可跳过以加速 MVP 交付
- 每个任务引用具体需求编号以确保可追溯性
- 检查点确保增量验证
- 属性测试验证通用正确性属性，单元测试验证具体示例和边界情况
- 后端使用 Python（FastAPI + Hypothesis），前端使用 TypeScript（React + Ant Design + fast-check）
