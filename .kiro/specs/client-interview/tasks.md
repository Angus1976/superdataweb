# 实施计划：客户智能访谈与 AI 友好型数据标签模块

## 概述

基于需求文档（12 项需求、44 条验收标准）和设计文档（8 个核心组件、21 条正确性属性），将 `client-interview` 模块拆分为增量式编码任务。后端使用 Python (FastAPI + Celery)，前端使用 TypeScript (React 19 + Ant Design)，数据层涉及 PostgreSQL、Neo4j、Redis，部署通过 Docker Compose。

## 任务

- [ ] 1. 数据库表结构与 Pydantic 数据模型
  - [ ] 1.1 创建 PostgreSQL 迁移脚本，建立 6 张表（client_projects, interview_sessions, interview_messages, ai_friendly_labels, industry_templates, offline_imports）及索引
    - 按照设计文档中的 SQL DDL 创建迁移文件
    - 包含 CHECK 约束、JSONB 默认值、外键关系
    - _需求: 1.2, 2.5, 4.2, 5.1, 11.1_
  - [ ] 1.2 实现 Pydantic 数据模型（`src/interview/models.py`）
    - 定义 Entity, Rule, Relation, AIFriendlyLabel, ProjectCreateRequest, InterviewMessage, AIResponse, ExtractionResult, QualityReport, ErrorResponse 等模型
    - 包含字段校验（min_length, max_length, pattern 等）
    - _需求: 4.5, 12.1, 12.2_
  - [ ]* 1.3 编写属性测试：AI_Friendly_Label 往返一致性
    - **Property 21: AI_Friendly_Label 往返一致性**
    - 使用 Hypothesis 生成随机合法 AIFriendlyLabel，验证 parse(format(parse(json))) == parse(json)
    - **验证: 需求 12.1, 12.2, 12.3**
  - [ ]* 1.4 编写属性测试：标签结构合规
    - **Property 8: 标签生成结构合规**
    - 验证生成的 AIFriendlyLabel 包含 entities、rules、relations 三个顶层字段且通过 JSON Schema 校验
    - **验证: 需求 4.1, 4.5**

- [ ] 2. 安全层与认证机制
  - [ ] 2.1 实现 InterviewSecurity 类（`src/interview/security.py`）
    - 实现 verify_tenant_access：校验租户对项目的访问权限
    - 实现 sanitize_content：集成 Presidio 进行敏感信息脱敏
    - 实现 get_current_tenant：从 JWT token 提取租户 ID
    - 复用现有 JWT 认证中间件
    - _需求: 1.3, 7.1, 7.2, 7.3, 7.4_
  - [ ]* 2.2 编写属性测试：Presidio 敏感信息脱敏
    - **Property 15: Presidio 敏感信息脱敏**
    - 使用 Hypothesis 生成含 PII 模式的文本，验证脱敏后不包含原始敏感信息
    - **验证: 需求 7.1**
  - [ ]* 2.3 编写属性测试：多租户数据隔离
    - **Property 16: 多租户数据隔离**
    - 验证租户 A 无法访问租户 B 的项目数据，返回 HTTP 403
    - **验证: 需求 7.2, 7.3**
  - [ ]* 2.4 编写属性测试：JWT 认证校验
    - **Property 17: JWT 认证校验**
    - 验证不携带有效 JWT 的请求被拒绝，返回 HTTP 401
    - **验证: 需求 7.4**

- [ ] 3. 检查点 - 确保数据模型和安全层测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 4. 行业模板管理
  - [ ] 4.1 创建行业模板种子数据和 CRUD 接口
    - 预置金融、电商、制造三套 Industry_Template 种子数据
    - 实现 GET/POST/PUT `/api/interview/templates` 接口
    - _需求: 2.2, 11.1, 11.2_
  - [ ]* 4.2 编写属性测试：行业模板 CRUD
    - **Property 19: 行业模板 CRUD**
    - 验证创建的模板可通过查询接口获取且内容一致
    - **验证: 需求 11.2**
  - [ ]* 4.3 编写属性测试：项目创建自动加载行业模板
    - **Property 20: 项目创建自动加载行业模板**
    - 验证启动会话时自动加载对应行业的 Industry_Template
    - **验证: 需求 11.3**

- [ ] 5. 项目创建与文档上传
  - [ ] 5.1 实现 InterviewSystem.create_project 和项目管理 API
    - 实现 POST/GET `/api/interview/projects` 接口
    - 项目数据存储至 PostgreSQL JSONB
    - 集成租户隔离（仅返回当前租户项目）
    - _需求: 1.1, 1.2, 1.5_
  - [ ]* 5.2 编写属性测试：项目创建持久化
    - **Property 1: 项目创建持久化**
    - 验证合法请求在 client_projects 表中产生新记录且 JSONB 包含原始数据
    - **验证: 需求 1.2**
  - [ ] 5.3 实现 InterviewEntityExtractor 类（`src/interview/entity_extractor.py`）
    - 封装现有 src/ai/ 模块的实体提取能力
    - 实现 extract_from_document：从上传文档提取实体
    - 实现 extract_from_message：从对话消息提取实体
    - 实现 merge_extractions：合并多次提取结果
    - _需求: 1.4, 2.3, 5.3_
  - [ ] 5.4 实现文档上传 API（`POST /api/interview/{project_id}/upload-document`）
    - 支持 Word、Excel、PDF 格式，使用 python-docx / openpyxl / PyPDF2 解析
    - 不支持的格式返回 400 错误及支持格式列表
    - 调用 Entity_Extractor 进行初始实体提取
    - 返回结构化 JSON 提取结果
    - _需求: 1.4, 1.5, 1.6_
  - [ ]* 5.5 编写属性测试：文档上传触发实体提取
    - **Property 2: 文档上传触发实体提取**
    - 验证支持格式的文档上传后 Entity_Extractor 被调用并返回结构化 ExtractionResult
    - **验证: 需求 1.4**

- [ ] 6. 访谈会话与对话交互
  - [ ] 6.1 实现访谈会话管理 API
    - POST `/api/interview/{project_id}/sessions`：启动会话，加载行业模板，初始化 Redis 缓存
    - POST `/api/interview/sessions/{session_id}/messages`：发送消息，生成 AI 响应，触发异步实体提取
    - POST `/api/interview/sessions/{session_id}/end`：结束会话
    - GET `/api/interview/sessions/{session_id}/status`：获取会话状态和异步任务进度
    - 使用 Presidio 对消息内容脱敏后存储
    - 实现 30 轮自动终止逻辑
    - _需求: 2.1, 2.3, 2.4, 2.5, 2.6, 7.1, 8.1_
  - [ ]* 6.2 编写属性测试：对话消息触发实体提取
    - **Property 3: 对话消息触发实体提取**
    - 验证客户消息发送后 Entity_Extractor 被异步调用并产生 ExtractionResult
    - **验证: 需求 2.3**
  - [ ]* 6.3 编写属性测试：会话最大轮次自动终止
    - **Property 4: 会话最大轮次自动终止**
    - 验证对话轮次达到 30 轮时会话状态变为 completed
    - **验证: 需求 2.5**
  - [ ]* 6.4 编写属性测试：会话结束生成摘要
    - **Property 5: 会话结束生成摘要**
    - 验证已结束的会话生成非空 Interview_Summary 和实体-规则-属性列表
    - **验证: 需求 2.6**
  - [ ] 6.5 实现隐含缺口检测与补全建议 API
    - 实现 detect_implicit_gaps：分析上下文检测隐含信息缺口
    - POST `/api/interview/sessions/{session_id}/completions`：生成 5 条补全建议
    - _需求: 3.1, 3.2, 3.3_
  - [ ]* 6.6 编写属性测试：隐含缺口检测与引导问题生成
    - **Property 6: 隐含缺口检测与引导问题生成**
    - 验证检测到缺口时生成至少一个引导性问题
    - **验证: 需求 3.1, 3.2**
  - [ ]* 6.7 编写属性测试：一键补全生成 5 条建议
    - **Property 7: 一键补全生成 5 条建议**
    - 验证调用补全接口返回恰好 5 条 CompletionSuggestion
    - **验证: 需求 3.3**

- [ ] 7. 检查点 - 确保访谈核心流程测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 8. 标签构造与存储
  - [ ] 8.1 实现 LabelConstructor 类（`src/interview/label_constructor.py`）
    - 实现 generate_labels：将 ExtractionResult 转换为 AIFriendlyLabel
    - 实现 parse / format：JSON 解析与格式化（往返一致性）
    - 实现 validate：结构校验，不合法时返回描述性错误（含具体字段）
    - 实现 store：同时存储至 PostgreSQL 和 Neo4j
    - _需求: 4.1, 4.2, 4.5, 12.1, 12.2, 12.3, 12.4_
  - [ ] 8.2 实现 Neo4jMapper 类（`src/interview/neo4j_mapper.py`）
    - 实现 map_entities：将实体映射为 BusinessEntity 节点
    - 实现 map_relations：将关系映射为动态类型边
    - 实现 map_label：完整映射实体 + 关系
    - _需求: 4.3_
  - [ ]* 8.3 编写属性测试：标签双重存储
    - **Property 9: 标签双重存储**
    - 验证 AIFriendlyLabel 同时存储至 PostgreSQL（完整 JSON）和 Neo4j（实体节点 + 关系边）
    - **验证: 需求 4.2, 4.3**
  - [ ] 8.4 实现 QualityAssessor 类（`src/interview/quality_assessor.py`）
    - 复用现有 Ragas 框架评估标签质量
    - 返回包含 overall_score 和 dimension_scores 的 QualityReport
    - _需求: 4.4_
  - [ ]* 8.5 编写属性测试：标签质量评估
    - **Property 10: 标签质量评估**
    - 验证 Quality_Assessor 对任意 AIFriendlyLabel 返回包含 overall_score 和 dimension_scores 的 QualityReport
    - **验证: 需求 4.4**
  - [ ] 8.6 实现标签生成 API（`POST /api/interview/{project_id}/generate-labels`）
    - 调用 LabelConstructor 生成标签
    - 调用 Neo4jMapper 映射至知识图谱
    - 调用 QualityAssessor 执行质量评估
    - 通过 Celery 异步处理耗时操作
    - _需求: 4.1, 4.2, 4.3, 4.4_

- [ ] 9. 离线导入与合并
  - [ ] 9.1 实现 OfflineImporter 类（`src/interview/offline_importer.py`）
    - 实现 import_file：解析 Excel(.xlsx) 和 JSON(.json) 文件
    - 实现 validate_file：校验文件格式和内容合法性
    - 实现 merge_with_online：将离线数据与在线访谈结果合并
    - 非法格式或解析失败返回详细错误（含失败原因和数据行号）
    - _需求: 5.1, 5.2, 5.4, 5.5_
  - [ ] 9.2 实现离线导入 API（`POST /api/interview/{project_id}/import-offline`）
    - 上传文件解析 → 合并在线结果 → 触发 AI 预标注
    - _需求: 5.1, 5.2, 5.3_
  - [ ]* 9.3 编写属性测试：离线文件解析
    - **Property 11: 离线文件解析**
    - 验证合法 Excel/JSON 文件成功解析为标准化 ImportResult
    - **验证: 需求 5.1**
  - [ ]* 9.4 编写属性测试：离线数据与在线结果合并
    - **Property 12: 离线数据与在线结果合并**
    - 验证合并后的 MergedData 包含两者所有数据，不丢失实体、规则或关系
    - **验证: 需求 5.2**
  - [ ]* 9.5 编写属性测试：合并数据触发预标注
    - **Property 13: 合并数据触发预标注**
    - 验证合并完成后 Entity_Extractor 被调用执行 AI 预标注
    - **验证: 需求 5.3**

- [ ] 10. Label Studio 同步
  - [ ] 10.1 实现 LabelStudioConnector 类（`src/interview/label_studio_connector.py`）
    - 复用现有 Label Studio 客户端（PAT + JWT 自动刷新）
    - 实现 sync_labels：同步标签至 Label Studio 任务池，包含 AI 预标注
    - 实现 check_connection：检查连接状态
    - 连接失败时返回错误信息并记录日志
    - _需求: 6.1, 6.2, 6.3, 6.4_
  - [ ] 10.2 实现同步 API（`POST /api/interview/{project_id}/sync-to-label-studio`）
    - 调用 LabelStudioConnector 执行同步
    - _需求: 6.1_
  - [ ]* 10.3 编写属性测试：Label Studio 同步含预标注
    - **Property 14: Label Studio 同步含预标注**
    - 验证同步至 Label Studio 的任务包含 AI 预标注数据
    - **验证: 需求 6.1, 6.2**

- [ ] 11. 检查点 - 确保后端所有组件测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 12. Celery 异步任务与 Redis 缓存
  - [ ] 12.1 实现 Celery 异步任务定义
    - 实体提取任务（extract_entities_task）
    - 标签生成任务（generate_labels_task）
    - 任务失败自动重试（最多 3 次，指数退避）
    - 任务状态通过 Redis 实时更新
    - _需求: 8.1, 8.2_
  - [ ] 12.2 实现 Redis 会话缓存管理
    - 活跃会话上下文缓存（TTL: 2h）
    - 异步任务状态缓存
    - 会话锁（防止并发消息，TTL: 30s）
    - _需求: 8.1, 8.2_

- [ ] 13. Prometheus 监控指标
  - [ ] 13.1 实现 Prometheus 指标上报
    - 访谈完成率指标
    - 隐含信息补全率指标
    - 在会话完成时上报指标
    - _需求: 10.2, 10.3_
  - [ ]* 13.2 编写属性测试：Prometheus 指标上报
    - **Property 18: Prometheus 指标上报**
    - 验证已完成的会话向 Prometheus 上报访谈完成率和隐含信息补全率指标
    - **验证: 需求 10.3**

- [ ] 14. FastAPI Router 汇总与错误处理
  - [ ] 14.1 创建统一的 FastAPI Router（`src/interview/router.py`）
    - 汇总所有 API 端点至 `/api/interview/*` 路由
    - 实现统一错误响应格式（ErrorResponse）
    - 集成 JWT 认证中间件和租户校验依赖
    - 实现各错误场景的 HTTP 状态码映射（401/403/404/400/409/422/502/504）
    - _需求: 7.4, 错误处理设计_

- [ ] 15. 检查点 - 确保后端完整功能测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 16. 前端项目创建页面
  - [ ] 16.1 实现项目创建页面（`/interview/start`）
    - 使用 Ant Design Form 组件构建项目创建表单
    - 包含项目名称输入、行业选择下拉框、业务领域输入
    - 支持需求文档上传（Word/Excel/PDF）
    - 展示实体提取结果（结构化 JSON）
    - 文件格式不支持时展示错误提示
    - _需求: 1.1, 1.4, 1.5, 1.6_

- [ ] 17. 前端访谈对话页面
  - [ ] 17.1 实现访谈对话页面（`/interview/session/:project_id`）
    - 聊天式对话界面，支持消息发送和 AI 响应展示
    - 侧边栏实时展示提取到的 JSON 结构数据
    - 隐含缺口引导问题展示
    - "一键补全"按钮，展示 5 条补全建议
    - 异步任务处理进度指示
    - 30 轮自动结束提示
    - 会话结束后展示访谈摘要
    - _需求: 2.1, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 8.3_
  - [ ] 17.2 实现语音输入功能（Web Speech API）
    - 检测浏览器 Web Speech API 支持
    - 提供语音输入按钮作为文字输入替代
    - _需求: 3.4_

- [ ] 18. 前端离线导入与标签预览页面
  - [ ] 18.1 实现离线导入界面
    - 文件上传组件（支持 .xlsx 和 .json）
    - 导入进度展示和错误详情展示
    - _需求: 5.1, 5.4, 5.5_
  - [ ] 18.2 实现标签预览与操作界面
    - AI_Friendly_Label JSON 结构预览
    - 一键同步至 Label Studio 按钮
    - 质量评估报告展示
    - _需求: 4.1, 6.1_

- [ ] 19. 前端导航与响应式布局
  - [ ] 19.1 在 React Router 导航菜单中新增"客户智能访谈"入口
    - 点击跳转至 `/interview/start`
    - 基于 Ant Design 响应式能力适配桌面端和移动端
    - _需求: 9.1, 9.2, 9.3_

- [ ] 20. 检查点 - 确保前端页面功能正常
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 21. Docker 部署配置
  - [ ] 21.1 新增 interview-service 容器配置
    - 在 docker-compose.yml 中新增 interview-service 容器
    - 配置与 PostgreSQL、Redis、Neo4j、Label Studio 的网络连接
    - 配置 Prometheus 监控端点
    - 编写 Dockerfile
    - _需求: 10.1, 10.2_

- [ ] 22. 最终检查点 - 全模块集成验证
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保可追溯性
- 检查点任务确保增量验证，及时发现问题
- 属性测试使用 Hypothesis 框架验证通用正确性属性
- 单元测试验证具体示例和边界条件
