# 实施计划：需求收集子模块（Demand Collection）

## 概述

基于需求文档（3 项需求、13 条验收标准）和设计文档（3 个核心组件、6 条正确性属性），将 `demand-collection` 子模块拆分为增量式编码任务。后端使用 Python (FastAPI)，前端使用 TypeScript (React 19 + Ant Design)，数据层使用 PostgreSQL (JSONB)。

本子模块提取自父模块 `.kiro/specs/client-interview/`，仅包含项目创建、文档上传、行业模板管理和数据模型定义相关任务。

## 任务

- [x] 1. 数据库表结构与 Pydantic 数据模型
  - [x] 1.1 创建 PostgreSQL 迁移脚本，建立 `client_projects` 和 `industry_templates` 两张表及索引
    - 按照设计文档中的 SQL DDL 创建迁移文件
    - `client_projects` 表包含 CHECK 约束（industry 枚举）、JSONB 默认值、外键关系
    - `industry_templates` 表包含 name、industry、system_prompt、config JSONB 字段
    - _需求: 1.2, 2.1_
  - [x] 1.2 实现 Pydantic 数据模型（`src/interview/models.py`）
    - 定义 Entity, Rule, Relation, AIFriendlyLabel, ProjectCreateRequest, ExtractionResult, EntityAttribute, ErrorResponse 等模型
    - 包含字段校验（min_length, max_length, pattern 等）
    - _需求: 3.1, 3.2_
  - [x] 1.3 编写属性测试：AI_Friendly_Label 往返一致性
    - **Property 6: AI_Friendly_Label 往返一致性**
    - 使用 Hypothesis 生成随机合法 AIFriendlyLabel，验证 parse(format(parse(json))) == parse(json)
    - **验证: 需求 3.1, 3.2, 3.3**
  - [x] 1.4 编写属性测试：标签结构合规
    - **Property 3: 标签生成结构合规**
    - 验证生成的 AIFriendlyLabel 包含 entities、rules、relations 三个顶层字段且通过 JSON Schema 校验
    - **验证: 需求 3.1, 3.2**

- [x] 2. 行业模板管理
  - [x] 2.1 创建行业模板种子数据和 CRUD 接口
    - 预置金融、电商、制造三套 Industry_Template 种子数据
    - 实现 GET/POST/PUT `/api/interview/templates` 接口
    - _需求: 2.1, 2.2_
  - [x] 2.2 编写属性测试：行业模板 CRUD
    - **Property 4: 行业模板 CRUD**
    - 验证创建的模板可通过查询接口获取且内容一致
    - **验证: 需求 2.2**
  - [x] 2.3 编写属性测试：项目创建自动加载行业模板
    - **Property 5: 项目创建自动加载行业模板**
    - 验证启动会话时自动加载对应行业的 Industry_Template
    - **验证: 需求 2.3**

- [x] 3. 项目创建与文档上传
  - [x] 3.1 实现 InterviewSystem.create_project 和项目管理 API
    - 实现 POST/GET `/api/interview/projects` 接口
    - 项目数据存储至 PostgreSQL JSONB
    - 集成租户隔离（仅返回当前租户项目）
    - _需求: 1.1, 1.2, 1.5_
  - [x] 3.2 编写属性测试：项目创建持久化
    - **Property 1: 项目创建持久化**
    - 验证合法请求在 client_projects 表中产生新记录且 JSONB 包含原始数据
    - **验证: 需求 1.2**
  - [x] 3.3 实现 InterviewEntityExtractor 类（`src/interview/entity_extractor.py`）
    - 封装现有 src/ai/ 模块的实体提取能力
    - 实现 extract_from_document：从上传文档提取实体
    - 实现 merge_extractions：合并多次提取结果
    - _需求: 1.4_
  - [x] 3.4 实现文档上传 API（`POST /api/interview/{project_id}/upload-document`）
    - 支持 Word、Excel、PDF 格式，使用 python-docx / openpyxl / PyPDF2 解析
    - 不支持的格式返回 400 错误及支持格式列表
    - 解析失败返回 422 错误及失败原因
    - 调用 Entity_Extractor 进行初始实体提取
    - 返回结构化 JSON 提取结果
    - _需求: 1.4, 1.5, 1.6_
  - [x] 3.5 编写属性测试：文档上传触发实体提取
    - **Property 2: 文档上传触发实体提取**
    - 验证支持格式的文档上传后 Entity_Extractor 被调用并返回结构化 ExtractionResult
    - **验证: 需求 1.4**

- [x] 4. 检查点 - 确保后端 API 和数据模型测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 5. 前端项目创建页面
  - [x] 5.1 实现项目创建页面（`/interview/start`）
    - 使用 Ant Design Form 组件构建项目创建表单
    - 包含项目名称输入、行业选择下拉框、业务领域输入
    - 支持需求文档上传（Word/Excel/PDF）
    - 展示实体提取结果（结构化 JSON）
    - 文件格式不支持时展示错误提示
    - _需求: 1.1, 1.4, 1.5, 1.6_

- [x] 6. 最终检查点 - 确保前后端功能完整
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选属性测试任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号（本子模块编号），确保可追溯性
- 本子模块的需求编号与父模块的映射关系：需求 1 → 父需求 1，需求 2 → 父需求 11，需求 3 → 父需求 12
- 属性编号与父模块的映射关系：Property 1 → 父 Property 1，Property 2 → 父 Property 2，Property 3 → 父 Property 8，Property 4 → 父 Property 19，Property 5 → 父 Property 20，Property 6 → 父 Property 21
- 检查点任务确保增量验证，及时发现问题
- 属性测试使用 Hypothesis 框架验证通用正确性属性
