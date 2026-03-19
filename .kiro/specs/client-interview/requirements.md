# 需求文档

## 简介

SuperInsight 在线客户智能访谈与 AI 友好型数据标签模块（`client-interview`）是 SuperInsight 企业级 AI 数据治理平台（v2.3.0）的新增模块。该模块通过在线智能访谈方式收集客户业务需求，利用 AI 实时提取实体、规则和属性，并生成标准化的 AI 友好型数据标签，最终与现有标注任务池、知识图谱和质量评估体系深度集成。模块遵循 100% 复用现有技术栈的原则，基于 FastAPI + React 19 + Ant Design + PostgreSQL + Neo4j + Label Studio + Celery 构建。

## 术语表

- **Interview_System**：在线客户智能访谈系统，本模块的核心系统
- **Interview_Session**：访谈会话，客户与 AI 之间的多轮对话交互实例
- **Entity_Extractor**：实体提取器，复用现有 `src/ai/` 模块中的实体识别与属性标注模型
- **Label_Constructor**：标签构造器，将访谈结果转换为标准化 AI 友好型数据标签的组件
- **Label_Studio_Connector**：Label Studio 连接器，负责将标签数据同步至 Label Studio 的组件
- **Neo4j_Mapper**：Neo4j 映射器，负责将实体关系映射至 Neo4j 知识图谱的组件
- **Quality_Assessor**：质量评估器，复用现有 Ragas 框架进行标签质量评估的组件
- **Offline_Importer**：离线导入器，负责导入离线访谈数据（Excel/JSON）的组件
- **Project**：项目，客户创建的业务需求收集单元，包含名称、行业和业务领域
- **Interview_Summary**：访谈摘要，访谈结束后自动生成的结构化总结文档
- **Industry_Template**：行业模板，针对不同行业（金融/电商/制造）预设的系统提示词模板
- **Implicit_Gap**：隐含信息缺口，AI 检测到的客户未明确表述但业务逻辑所需的信息空白
- **AI_Friendly_Label**：AI 友好型标签，包含实体、规则、关系的标准化 JSON 结构
- **Completion_Suggestion**：补全建议，AI 基于上下文生成的信息补全推荐项
- **Presidio**：微软开源的数据脱敏工具，用于对话内容中的敏感信息去标识化

## 需求

### 需求 1：客户项目创建与需求收集

**用户故事：** 作为客户，我希望能够创建项目并上传需求文档，以便系统自动提取初始实体信息，启动智能访谈流程。

#### 验收标准

1. WHEN 客户访问 `/interview/start` 页面, THE Interview_System SHALL 展示项目创建表单，包含项目名称、行业选择和业务领域输入字段
2. WHEN 客户提交项目创建表单, THE Interview_System SHALL 在 PostgreSQL 的 `client_projects` 表中创建一条新记录，使用 JSONB 格式存储原始需求数据
3. THE Interview_System SHALL 复用现有 JWT 认证机制完成客户的注册与登录验证
4. WHEN 客户上传需求文档（支持 Word、Excel、PDF 格式）, THE Entity_Extractor SHALL 自动调用现有 `src/ai/` 模块对文档进行初始实体提取
5. WHEN 实体提取完成, THE Interview_System SHALL 将提取结果以结构化 JSON 格式展示给客户
6. IF 上传的文件格式不在支持范围内, THEN THE Interview_System SHALL 返回明确的错误提示，说明支持的文件格式列表

### 需求 2：智能访谈对话交互

**用户故事：** 作为客户，我希望通过聊天式对话描述业务规则，以便 AI 能够准确理解并实时提取关键信息。

#### 验收标准

1. WHEN 客户进入 `/interview/session/:project_id` 页面, THE Interview_System SHALL 展示聊天式对话界面，并加载该项目关联的 Industry_Template
2. THE Interview_System SHALL 提供 3 套内置系统提示词模板（金融、电商、制造），支持按行业切换
3. WHEN 客户发送一条对话消息, THE Entity_Extractor SHALL 在该轮对话结束后调用现有实体/属性提取模型进行实时提取
4. WHEN 实体提取完成, THE Interview_System SHALL 在对话界面侧边栏实时展示提取到的 JSON 结构数据
5. WHILE Interview_Session 的对话轮次达到 30 轮, THE Interview_System SHALL 自动结束该访谈会话
6. WHEN Interview_Session 结束（达到最大轮次或客户主动结束）, THE Interview_System SHALL 自动生成 Interview_Summary 和初步实体-规则-属性列表

### 需求 3：隐含信息缺口检测与补全引导

**用户故事：** 作为客户，我希望 AI 能够主动发现我遗漏的信息并引导我补充，以便需求收集更加完整。

#### 验收标准

1. WHEN 每轮对话结束后, THE Interview_System SHALL 分析当前对话上下文，检测 Implicit_Gap
2. WHEN 检测到 Implicit_Gap, THE Interview_System SHALL 自动生成引导性问题并推荐给客户
3. WHEN 客户点击"一键补全"按钮, THE Interview_System SHALL 基于当前上下文生成 5 条 Completion_Suggestion
4. WHERE 客户设备支持 Web Speech API, THE Interview_System SHALL 提供语音输入选项作为文字输入的替代方式

### 需求 4：AI 友好型数据标签构造

**用户故事：** 作为数据工程师，我希望系统能将访谈结果转换为标准化的 AI 友好型标签结构，以便后续标注和知识图谱构建。

#### 验收标准

1. WHEN 调用 `/api/interview/{project_id}/generate-labels` 接口, THE Label_Constructor SHALL 将在线访谈结果转换为包含实体（entities）、规则（rules）和关系（relations）的标准化 JSON 结构
2. THE Label_Constructor SHALL 将生成的 AI_Friendly_Label 同时存储至 Neo4j（实体关系）和 PostgreSQL（完整 JSON）
3. WHEN 生成标签数据后, THE Neo4j_Mapper SHALL 将实体和关系映射至 Neo4j 知识图谱
4. WHEN 标签生成完成, THE Quality_Assessor SHALL 使用 Ragas 框架对生成的标签进行质量评估
5. THE Label_Constructor SHALL 输出的 AI_Friendly_Label 符合以下 JSON 结构规范：包含 `entities`（实体数组）、`rules`（规则数组）和 `relations`（关系数组）三个顶层字段

### 需求 5：离线访谈数据导入与合并

**用户故事：** 作为咨询顾问，我希望能够导入离线访谈数据（Excel/JSON），并与在线访谈结果合并，以便生成更完整的标签数据。

#### 验收标准

1. WHEN 调用 `/api/interview/{project_id}/import-offline` 接口并上传 Excel 或 JSON 文件, THE Offline_Importer SHALL 解析文件内容并转换为标准化的内部数据格式
2. WHEN 离线数据导入完成, THE Label_Constructor SHALL 将离线数据与该项目的在线访谈结果进行合并
3. WHEN 合并完成, THE Entity_Extractor SHALL 对合并后的数据执行 AI 预标注
4. IF 上传的离线数据文件格式不合法或内容解析失败, THEN THE Offline_Importer SHALL 返回详细的错误信息，包含失败原因和数据行号
5. THE Offline_Importer SHALL 支持 Excel（.xlsx）和 JSON（.json）两种文件格式的离线数据导入


### 需求 6：Label Studio 任务同步

**用户故事：** 作为数据工程师，我希望能够一键将生成的标签数据同步至 Label Studio，以便标注任务自动出现在任务池中并带有预标注。

#### 验收标准

1. WHEN 调用 `/api/interview/{project_id}/sync-to-label-studio` 接口, THE Label_Studio_Connector SHALL 将该项目的 AI_Friendly_Label 同步至 Label Studio 任务池
2. WHEN 同步完成, THE Label_Studio_Connector SHALL 确保同步的任务包含 AI 预标注数据
3. THE Label_Studio_Connector SHALL 复用现有的 Label Studio PAT 认证和 JWT 自动刷新机制
4. IF 与 Label Studio 的连接失败, THEN THE Label_Studio_Connector SHALL 返回连接失败的错误信息并记录日志

### 需求 7：访谈数据安全与多租户隔离

**用户故事：** 作为平台管理员，我希望所有访谈对话数据经过脱敏处理且客户数据严格隔离，以便满足企业数据安全合规要求。

#### 验收标准

1. THE Interview_System SHALL 使用 Presidio 对所有访谈对话内容进行敏感信息去标识化处理后再存储
2. THE Interview_System SHALL 基于多租户机制实现客户数据隔离，确保每个客户仅能访问自身项目数据
3. WHEN 客户请求访问非自身项目的数据, THE Interview_System SHALL 拒绝请求并返回权限不足的错误响应
4. THE Interview_System SHALL 对所有访谈相关 API 接口执行 JWT 认证校验

### 需求 8：访谈性能与异步处理

**用户故事：** 作为客户，我希望每轮访谈对话的响应速度足够快，以便获得流畅的交互体验。

#### 验收标准

1. WHEN 客户发送一轮对话消息, THE Interview_System SHALL 在 2 秒内返回 AI 响应（利用现有 Celery 异步任务队列）
2. THE Interview_System SHALL 使用现有 Celery 异步任务队列处理实体提取和标签生成等耗时操作
3. WHILE 异步任务正在执行, THE Interview_System SHALL 在前端界面展示处理进度指示

### 需求 9：前端导航与响应式布局

**用户故事：** 作为客户，我希望能够从平台主导航方便地进入智能访谈模块，并在移动设备上正常使用。

#### 验收标准

1. THE Interview_System SHALL 在现有 React Router 导航菜单中新增"客户智能访谈"入口
2. THE Interview_System SHALL 基于 Ant Design 的响应式能力，确保访谈界面在桌面端和移动端均可正常使用
3. WHEN 客户点击导航菜单中的"客户智能访谈"入口, THE Interview_System SHALL 跳转至 `/interview/start` 页面

### 需求 10：部署与监控

**用户故事：** 作为运维工程师，我希望新模块能够无缝集成到现有 Docker Compose 部署中，并通过现有监控体系观察运行状态。

#### 验收标准

1. THE Interview_System SHALL 以新增 `interview-service` 容器的方式无缝集成到现有 `docker-compose.yml` 配置中
2. THE Interview_System SHALL 复用现有 Prometheus 监控体系，新增访谈完成率指标的监控面板
3. WHEN 访谈会话完成, THE Interview_System SHALL 上报访谈完成率、隐含信息补全率等核心指标至 Prometheus

### 需求 11：行业模板可配置性

**用户故事：** 作为平台管理员，我希望能够配置和扩展行业模板，以便支持更多行业场景。

#### 验收标准

1. THE Interview_System SHALL 支持金融、电商、制造三个行业的预置 Industry_Template
2. WHERE 平台管理员需要新增行业模板, THE Interview_System SHALL 提供模板配置接口，支持新增和修改 Industry_Template
3. WHEN 客户创建项目并选择行业时, THE Interview_System SHALL 自动加载对应行业的 Industry_Template 作为访谈的系统提示词

### 需求 12：AI_Friendly_Label 的解析与格式化（往返一致性）

**用户故事：** 作为数据工程师，我希望 AI 友好型标签的 JSON 结构在解析和格式化过程中保持一致，以便数据在系统间传输时不丢失信息。

#### 验收标准

1. THE Label_Constructor SHALL 将 AI_Friendly_Label 解析为内部数据对象
2. THE Label_Constructor SHALL 将内部数据对象格式化输出为标准 AI_Friendly_Label JSON 结构
3. FOR ALL 合法的 AI_Friendly_Label JSON 数据，执行解析后再格式化再解析，SHALL 产生与首次解析等价的数据对象（往返一致性）
4. IF 输入的 JSON 数据不符合 AI_Friendly_Label 结构规范, THEN THE Label_Constructor SHALL 返回描述性错误信息，包含具体的校验失败字段
