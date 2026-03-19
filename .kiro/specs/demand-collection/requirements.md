# 需求文档：需求收集子模块（Demand Collection）

## 简介

需求收集子模块（`demand-collection`）是 `client-interview` 父模块的核心入口子模块，负责客户项目创建、需求文档上传与初始实体提取、行业模板管理，以及 AI_Friendly_Label 数据模型的解析与格式化。本子模块为后续访谈对话、标签构造等子模块提供基础数据支撑。

本子模块从父模块 `.kiro/specs/client-interview/` 中提取，技术栈复用 FastAPI + React 19 + Ant Design + PostgreSQL (JSONB) + Redis/Celery。

## 术语表

- **Interview_System**：在线客户智能访谈系统，本模块的核心系统
- **Entity_Extractor**：实体提取器，复用现有 `src/ai/` 模块中的实体识别与属性标注模型
- **Industry_Template**：行业模板，针对不同行业（金融/电商/制造）预设的系统提示词模板
- **AI_Friendly_Label**：AI 友好型标签，包含实体（entities）、规则（rules）、关系（relations）的标准化 JSON 结构
- **Label_Constructor**：标签构造器，负责 AI_Friendly_Label 的解析、格式化和校验
- **Project**：项目，客户创建的业务需求收集单元，包含名称、行业和业务领域
- **ExtractionResult**：实体提取结果，包含 entities、rules、relations 的结构化数据

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

### 需求 2：行业模板可配置性

**用户故事：** 作为平台管理员，我希望能够配置和扩展行业模板，以便支持更多行业场景。

#### 验收标准

1. THE Interview_System SHALL 支持金融、电商、制造三个行业的预置 Industry_Template
2. WHERE 平台管理员需要新增行业模板, THE Interview_System SHALL 提供模板配置接口，支持新增和修改 Industry_Template
3. WHEN 客户创建项目并选择行业时, THE Interview_System SHALL 自动加载对应行业的 Industry_Template 作为访谈的系统提示词

### 需求 3：AI_Friendly_Label 的解析与格式化（往返一致性）

**用户故事：** 作为数据工程师，我希望 AI 友好型标签的 JSON 结构在解析和格式化过程中保持一致，以便数据在系统间传输时不丢失信息。

#### 验收标准

1. THE Label_Constructor SHALL 将 AI_Friendly_Label 解析为内部数据对象
2. THE Label_Constructor SHALL 将内部数据对象格式化输出为标准 AI_Friendly_Label JSON 结构
3. FOR ALL 合法的 AI_Friendly_Label JSON 数据，执行解析后再格式化再解析，SHALL 产生与首次解析等价的数据对象（往返一致性）
4. IF 输入的 JSON 数据不符合 AI_Friendly_Label 结构规范, THEN THE Label_Constructor SHALL 返回描述性错误信息，包含具体的校验失败字段
