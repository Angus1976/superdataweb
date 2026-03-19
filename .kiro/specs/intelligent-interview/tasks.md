# 实施计划：智能访谈子模块（Intelligent Interview）

## 概述

基于需求文档（3 项需求、13 条验收标准）和设计文档（InterviewSystem 会话管理、Celery 异步任务、Redis 缓存、5 条正确性属性），将 `intelligent-interview` 子模块拆分为增量式编码任务。后端使用 Python (FastAPI + Celery)，前端使用 TypeScript (React 19 + Ant Design)，数据层涉及 PostgreSQL 和 Redis。

### 依赖前置条件

- `demand-collection` 子模块已完成：Project、Industry_Template、InterviewEntityExtractor、Pydantic 数据模型可用
- `interview-infra` 子模块已完成：InterviewSecurity（JWT + Presidio + 多租户）可用

## 任务

- [x] 1. 数据库迁移与 Pydantic 模型
  - [x] 1.1 创建 PostgreSQL 迁移脚本，建立 interview_sessions 和 interview_messages 表及索引
    - 按照设计文档中的 SQL DDL 创建迁移文件
    - 包含 CHECK 约束（status、role）、JSONB 字段、外键关系
    - interview_sessions 引用 client_projects(id) 和 industry_templates(id)
    - interview_messages 引用 interview_sessions(id)
    - _需求: 1.5, 1.6_
  - [x] 1.2 实现本子模块新增的 Pydantic 数据模型（`src/interview/session_models.py`）
    - 定义 InterviewMessage, ImplicitGap, AIResponse, CompletionSuggestion, InterviewSummary, SessionStatus, PendingTask
    - 包含字段校验（content min_length=1 等）
    - 复用 demand-collection 的 Entity, Rule, Relation, ExtractionResult
    - _需求: 1.3, 1.4, 1.6, 2.1, 2.2, 2.3_

- [x] 2. Redis 会话缓存管理
  - [x] 2.1 实现 Redis 会话缓存管理模块（`src/interview/session_cache.py`）
    - 活跃会话上下文缓存（key: `interview:session:{session_id}:context`, TTL: 2h）
    - 异步任务状态缓存（key: `interview:task:{task_id}:status`）
    - 会话锁获取与释放（key: `interview:session:{session_id}:lock`, TTL: 30s, NX 模式）
    - 提供 load_context / save_context / acquire_lock / release_lock / update_task_status 方法
    - _需求: 3.1, 3.2_

- [x] 3. Celery 异步任务定义
  - [x] 3.1 实现 Celery 异步任务（`src/interview/tasks.py`）
    - extract_entities_task：调用 InterviewEntityExtractor.extract_from_message，结果写入 interview_messages.extraction_result
    - 任务失败自动重试（max_retries=3，指数退避：5s → 25s → 125s）
    - 任务状态通过 Redis 实时更新（processing → completed / failed）
    - _需求: 3.1, 3.2_

- [x] 4. 检查点 - 确保基础设施层就绪
  - 确保迁移脚本可执行、Pydantic 模型校验正确、Redis 缓存和 Celery 任务可运行。如有问题请向用户确认。

- [x] 5. 访谈会话管理 API
  - [x] 5.1 实现 InterviewSystem 会话管理方法（`src/interview/system.py` 扩展）
    - start_session：校验项目归属、加载 Industry_Template、创建 interview_sessions 记录、初始化 Redis 缓存
    - end_session：生成 InterviewSummary、更新 interview_sessions（status='completed', summary=JSONB）、清理 Redis
    - get_session_status：从 Redis 读取会话上下文和任务状态，返回 SessionStatus
    - _需求: 1.1, 1.6, 3.3_
  - [x] 5.2 实现 send_message 方法（核心对话交互逻辑）
    - 获取 Redis 会话锁（TTL: 30s），防止并发
    - 从 Redis 加载会话上下文
    - 调用 InterviewSecurity.sanitize_content 脱敏
    - 检查 current_round < 30，超限自动调用 end_session
    - 生成 AI 响应
    - 调用 detect_implicit_gaps 检测隐含缺口
    - 存储消息至 PostgreSQL（原文 + 脱敏内容 + round_number）
    - 更新 Redis 上下文（current_round + 1, TTL 刷新 2h）
    - 异步提交 extract_entities_task
    - 释放会话锁
    - 返回 AIResponse
    - _需求: 1.1, 1.3, 1.5, 3.1_
  - [x] 5.3 实现 detect_implicit_gaps 方法
    - 从 Redis 加载完整对话历史
    - 基于行业模板和对话内容分析缺失信息
    - 返回 ImplicitGap 列表（含 gap_description 和 suggested_question）
    - _需求: 2.1, 2.2_
  - [x] 5.4 实现 generate_completions 方法
    - 从 Redis 加载会话上下文
    - 分析已收集信息和缺失维度
    - 生成恰好 5 条 CompletionSuggestion（含 suggestion_text 和 category）
    - _需求: 2.3_
  - [x] 5.5 实现 FastAPI 路由端点（`src/interview/router.py` 扩展）
    - POST /api/interview/{project_id}/sessions
    - POST /api/interview/sessions/{session_id}/messages
    - POST /api/interview/sessions/{session_id}/end
    - GET /api/interview/sessions/{session_id}/status
    - POST /api/interview/sessions/{session_id}/completions
    - 集成 InterviewSecurity JWT 认证中间件和租户校验依赖
    - _需求: 1.1, 1.3, 1.5, 1.6, 2.1, 2.3, 3.3_

- [x] 6. 属性测试与单元测试
  - [x] 6.1 编写属性测试：对话消息触发实体提取
    - **Property 1: 对话消息触发实体提取**
    - 使用 Hypothesis 生成随机对话消息，验证 send_message 后 extract_entities_task 被异步调用并产生 ExtractionResult
    - 测试文件：`tests/interview/test_session_properties.py`
    - **验证: 需求 1.3**
  - [x] 6.2 编写属性测试：会话最大轮次自动终止
    - **Property 2: 会话最大轮次自动终止**
    - 使用 Hypothesis 生成 30-50 范围的轮次数，验证第 30 轮时会话状态变为 completed
    - 测试文件：`tests/interview/test_session_properties.py`
    - **验证: 需求 1.5**
  - [x] 6.3 编写属性测试：会话结束生成摘要
    - **Property 3: 会话结束生成摘要**
    - 使用 Hypothesis 生成随机对话历史，验证 end_session 返回非空 InterviewSummary
    - 测试文件：`tests/interview/test_session_properties.py`
    - **验证: 需求 1.6**
  - [x] 6.4 编写属性测试：隐含缺口检测与引导问题生成
    - **Property 4: 隐含缺口检测与引导问题生成**
    - 使用 Hypothesis 生成随机对话上下文，验证检测到缺口时生成至少一个引导性问题
    - 测试文件：`tests/interview/test_gap_properties.py`
    - **验证: 需求 2.1, 2.2**
  - [x] 6.5 编写属性测试：一键补全生成 5 条建议
    - **Property 5: 一键补全生成 5 条建议**
    - 使用 Hypothesis 生成随机会话上下文，验证 generate_completions 返回恰好 5 条 CompletionSuggestion
    - 测试文件：`tests/interview/test_gap_properties.py`
    - **验证: 需求 2.3**
  - [x] 6.6 编写单元测试
    - 会话创建与模板加载（`tests/interview/test_session.py`）
    - 空消息拒绝、已结束会话拒绝消息、并发消息拒绝（`tests/interview/test_chat.py`）
    - 缺口检测返回引导问题、无缺口时返回空列表（`tests/interview/test_gaps.py`）
    - 补全建议返回 5 条、包含 category（`tests/interview/test_completions.py`）
    - Celery 任务提交、重试逻辑、超时处理（`tests/interview/test_celery_tasks.py`）
    - Redis 缓存 TTL、会话锁获取/释放（`tests/interview/test_redis_cache.py`）
    - _需求: 1.1-1.6, 2.1-2.4, 3.1-3.3_

- [x] 7. 检查点 - 确保后端所有测试通过
  - 确保所有属性测试和单元测试通过，如有问题请向用户确认。

- [x] 8. 前端访谈对话页面
  - [x] 8.1 实现访谈对话页面（`/interview/session/:project_id`）
    - 使用 Ant Design 构建聊天式对话界面
    - 消息发送输入框 + AI 响应气泡展示
    - 侧边栏实时展示提取到的 JSON 结构数据（实体/规则/关系）
    - 隐含缺口引导问题展示（在 AI 响应下方高亮显示）
    - "一键补全"按钮，点击后展示 5 条补全建议弹窗
    - 异步任务处理进度指示（Spin / Progress 组件）
    - 30 轮自动结束提示（倒计时提醒 + 结束确认）
    - 会话结束后展示访谈摘要卡片
    - _需求: 1.1, 1.2, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 3.3_
  - [x] 8.2 实现语音输入功能（Web Speech API）
    - 检测浏览器 Web Speech API 支持
    - 提供语音输入按钮作为文字输入替代
    - 不支持时隐藏语音按钮
    - _需求: 2.4_

- [x] 9. 最终检查点 - 全子模块集成验证
  - 确保前后端联调正常、所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选属性测试任务，可跳过以加速 MVP 交付
- 本子模块依赖 `demand-collection` 和 `interview-infra` 子模块，需确保它们先行完成
- 每个任务引用了具体的需求编号（本子模块内部编号），确保可追溯性
- 属性测试使用 Hypothesis 框架，每个测试最少运行 100 次迭代
- 属性测试标签格式：`Feature: intelligent-interview, Property {number}: {property_text}`