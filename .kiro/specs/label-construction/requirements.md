# 需求文档：标签构造子模块（Label Construction）

## 简介

标签构造子模块（`label-construction`）是 `client-interview` 父模块的数据输出子模块，负责将访谈提取结果转换为标准化 AI 友好型数据标签（AI_Friendly_Label），实现 PostgreSQL + Neo4j 双重存储，集成 Ragas 质量评估，支持离线访谈数据导入与合并，以及将标签数据同步至 Label Studio 任务池。

本子模块从父模块 `.kiro/specs/client-interview/` 中提取，技术栈复用 FastAPI + React 19 + Ant Design + PostgreSQL (JSONB) + Neo4j + Redis/Celery + Label Studio。

## 术语表

- **Label_Constructor**：标签构造器，将访谈提取结果转换为标准化 AI_Friendly_Label，支持生成、解析、格式化、校验和存储
- **AI_Friendly_Label**：AI 友好型标签，包含实体（entities）、规则（rules）、关系（relations）的标准化 JSON 结构
- **Neo4j_Mapper**：Neo4j 映射器，将实体和关系映射至 Neo4j 知识图谱
- **Quality_Assessor**：质量评估器，复用现有 Ragas 框架对标签进行质量评估
- **Offline_Importer**：离线导入器，解析 Excel/JSON 离线访谈数据并与在线结果合并
- **Label_Studio_Connector**：Label Studio 连接器，将标签数据同步至 Label Studio 任务池，包含 AI 预标注
- **BusinessEntity**：Neo4j 中的业务实体节点标签
- **BusinessRule**：Neo4j 中的业务规则节点标签
- **ExtractionResult**：实体提取结果，由 `demand-collection` 子模块定义，包含 entities、rules、relations
- **InterviewEntityExtractor**：实体提取器，由 `demand-collection` 子模块提供，用于合并后数据的 AI 预标注
- **QualityReport**：质量评估报告，包含 overall_score 和 dimension_scores
- **ImportResult**：离线文件解析后的标准化内部数据格式
- **MergedData**：离线数据与在线访谈结果合并后的数据集
- **InterviewSecurity**：安全层，由 `interview-infra` 子模块提供 JWT 认证和多租户隔离

## 依赖子模块

| 子模块 | 提供能力 |
|--------|----------|
| `demand-collection` | Pydantic 模型（Entity, Rule, Relation, AIFriendlyLabel, ExtractionResult）、InterviewEntityExtractor、LabelConstructor.parse/format/validate |
| `intelligent-interview` | 访谈会话数据（会话结束后的 ExtractionResult） |
| `interview-infra` | InterviewSecurity（JWT 认证 + 多租户隔离） |

## 需求

### 需求 1：AI 友好型数据标签构造

**用户故事：** 作为数据工程师，我希望系统能将访谈结果转换为标准化的 AI 友好型标签结构，以便后续标注和知识图谱构建。

#### 验收标准

1. WHEN 调用 `/api/interview/{project_id}/generate-labels` 接口, THE Label_Constructor SHALL 将在线访谈结果转换为包含实体（entities）、规则（rules）和关系（relations）的标准化 JSON 结构
2. THE Label_Constructor SHALL 将生成的 AI_Friendly_Label 同时存储至 Neo4j（实体关系）和 PostgreSQL（完整 JSON）
3. WHEN 生成标签数据后, THE Neo4j_Mapper SHALL 将实体映射为 BusinessEntity 节点，将关系映射为动态类型边
4. WHEN 标签生成完成, THE Quality_Assessor SHALL 使用 Ragas 框架对生成的标签进行质量评估，返回包含 overall_score 和 dimension_scores 的 QualityReport
5. THE Label_Constructor SHALL 输出的 AI_Friendly_Label 符合以下 JSON 结构规范：包含 `entities`（实体数组）、`rules`（规则数组）和 `relations`（关系数组）三个顶层字段

### 需求 2：离线访谈数据导入与合并

**用户故事：** 作为咨询顾问，我希望能够导入离线访谈数据（Excel/JSON），并与在线访谈结果合并，以便生成更完整的标签数据。

#### 验收标准

1. WHEN 调用 `/api/interview/{project_id}/import-offline` 接口并上传 Excel 或 JSON 文件, THE Offline_Importer SHALL 解析文件内容并转换为标准化的 ImportResult
2. WHEN 离线数据导入完成, THE Offline_Importer SHALL 将离线数据与该项目的在线访谈结果进行合并，生成包含两者所有数据的 MergedData
3. WHEN 合并完成, THE InterviewEntityExtractor SHALL 对合并后的数据执行 AI 预标注
4. IF 上传的离线数据文件格式不合法或内容解析失败, THEN THE Offline_Importer SHALL 返回详细的错误信息，包含失败原因和数据行号
5. THE Offline_Importer SHALL 支持 Excel（.xlsx）和 JSON（.json）两种文件格式的离线数据导入

### 需求 3：Label Studio 任务同步

**用户故事：** 作为数据工程师，我希望能够一键将生成的标签数据同步至 Label Studio，以便标注任务自动出现在任务池中并带有预标注。

#### 验收标准

1. WHEN 调用 `/api/interview/{project_id}/sync-to-label-studio` 接口, THE Label_Studio_Connector SHALL 将该项目的 AI_Friendly_Label 同步至 Label Studio 任务池
2. WHEN 同步完成, THE Label_Studio_Connector SHALL 确保同步的任务包含 AI 预标注数据
3. THE Label_Studio_Connector SHALL 复用现有的 Label Studio PAT 认证和 JWT 自动刷新机制
4. IF 与 Label Studio 的连接失败, THEN THE Label_Studio_Connector SHALL 返回连接失败的错误信息并记录日志
