# 实施计划：标签构造子模块（Label Construction）

## 概述

基于需求文档（3 项需求、14 条验收标准）和设计文档（5 个核心组件、8 条正确性属性），将 `label-construction` 子模块拆分为增量式编码任务。后端使用 Python (FastAPI + Celery)，前端使用 TypeScript (React 19 + Ant Design)，数据层涉及 PostgreSQL、Neo4j、Redis、Label Studio。

本子模块依赖 `demand-collection`（Pydantic 模型 + InterviewEntityExtractor + LabelConstructor.parse/format/validate）、`intelligent-interview`（会话 ExtractionResult）和 `interview-infra`（InterviewSecurity）。

## 任务

- [x] 1. 数据库表结构
  - [x] 1.1 创建 PostgreSQL 迁移脚本，建立 `ai_friendly_labels` 和 `offline_imports` 两张表及索引
    - `ai_friendly_labels` 表包含 label_data JSONB、quality_score JSONB、version 字段
    - `offline_imports` 表包含 file_type CHECK 约束、status CHECK 约束、error_details JSONB
    - 创建 idx_labels_project、idx_labels_tenant、idx_imports_project 索引
    - _需求: 1.2, 2.1_

- [x] 2. 标签构造与存储
  - [x] 2.1 实现 LabelConstructor.generate_labels 方法（`src/interview/label_constructor.py`）
    - 聚合多个 ExtractionResult 中的 entities、rules、relations
    - 基于 id 字段去重
    - 调用 validate 校验结构合规性（复用 demand-collection 的 validate）
    - 返回 AIFriendlyLabel
    - _需求: 1.1, 1.5_
  - [x] 2.2 实现 LabelConstructor.store 方法
    - PostgreSQL: 写入 ai_friendly_labels 表（label_data JSONB）
    - Neo4j: 调用 Neo4jMapper.map_label 映射实体和关系
    - _需求: 1.2_
  - [x] 2.3 实现 Neo4jMapper 类（`src/interview/neo4j_mapper.py`）
    - map_entities：将 entities 映射为 BusinessEntity 节点
    - map_relations：将 relations 映射为动态类型边
    - map_rules：将 rules 映射为 BusinessRule 节点 + APPLIES_TO 边
    - map_label：完整映射实体 + 关系 + 规则，返回 MappingResult
    - _需求: 1.3_
  - [x] 2.4 编写属性测试：标签生成结构合规
    - **Property 1: 标签生成结构合规**
    - 验证生成的 AIFriendlyLabel 包含 entities、rules、relations 三个顶层字段且通过 JSON Schema 校验
    - **验证: 需求 1.1, 1.5**
  - [x] 2.5 编写属性测试：标签双重存储
    - **Property 2: 标签双重存储**
    - 验证 AIFriendlyLabel 同时存储至 PostgreSQL（完整 JSON）和 Neo4j（实体节点 + 关系边）
    - **验证: 需求 1.2, 1.3**
  - [x] 2.6 编写属性测试：AI_Friendly_Label 往返一致性
    - **Property 8: AI_Friendly_Label 往返一致性**
    - 使用 Hypothesis 生成随机合法 AIFriendlyLabel，验证 parse(format(parse(json))) == parse(json)
    - **验证: 需求 1.5**

- [x] 3. 标签质量评估
  - [x] 3.1 实现 QualityAssessor 类（`src/interview/quality_assessor.py`）
    - 注入现有 Ragas 评估器
    - 实现 assess 方法：调用 Ragas 计算多维度分数
    - 返回 QualityReport（overall_score, dimension_scores, suggestions）
    - _需求: 1.4_
  - [x] 3.2 编写属性测试：标签质量评估
    - **Property 3: 标签质量评估**
    - 验证 QualityAssessor 对任意 AIFriendlyLabel 返回包含 overall_score 和 dimension_scores 的 QualityReport
    - **验证: 需求 1.4**

- [x] 4. 标签生成 API 与异步任务
  - [x] 4.1 实现标签生成 Celery 异步任务（generate_labels_task）
    - 查询项目的所有 ExtractionResult
    - 调用 LabelConstructor.generate_labels 生成标签
    - 调用 LabelConstructor.store 双重存储
    - 调用 QualityAssessor.assess 执行质量评估
    - 更新 ai_friendly_labels.quality_score
    - 失败时指数退避重试（最多 3 次）
    - _需求: 1.1, 1.2, 1.3, 1.4_
  - [x] 4.2 实现标签生成 API（`POST /api/interview/{project_id}/generate-labels`）
    - JWT 认证 + 租户校验
    - 提交 Celery 异步任务
    - 返回 task_id 和 processing 状态
    - _需求: 1.1_

- [x] 5. 检查点 - 确保标签构造核心功能测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 6. 离线导入与合并
  - [x] 6.1 实现 OfflineImporter 类（`src/interview/offline_importer.py`）
    - validate_file：校验文件格式（.xlsx / .json）和内容合法性
    - import_file：解析 Excel（openpyxl）和 JSON（json.loads）文件，返回 ImportResult
    - merge_with_online：从 PostgreSQL 查询在线 ExtractionResult，合并离线数据（基于 id 去重），返回 MergedData
    - 非法格式或解析失败返回详细错误（含失败原因和数据行号）
    - _需求: 2.1, 2.2, 2.4, 2.5_
  - [x] 6.2 实现预标注 Celery 异步任务（pre_annotate_merged_task）
    - 调用 InterviewEntityExtractor 对合并数据执行 AI 预标注
    - 更新 offline_imports 记录状态
    - _需求: 2.3_
  - [x] 6.3 实现离线导入 API（`POST /api/interview/{project_id}/import-offline`）
    - JWT 认证 + 租户校验
    - 上传文件解析 → 合并在线结果 → 触发异步预标注
    - 解析失败返回 422 + 行号错误详情
    - _需求: 2.1, 2.2, 2.3, 2.4_
  - [x] 6.4 编写属性测试：离线文件解析
    - **Property 4: 离线文件解析**
    - 验证合法 Excel/JSON 文件成功解析为标准化 ImportResult
    - **验证: 需求 2.1**
  - [x] 6.5 编写属性测试：离线数据与在线结果合并
    - **Property 5: 离线数据与在线结果合并**
    - 验证合并后的 MergedData 包含两者所有数据，不丢失实体、规则或关系
    - **验证: 需求 2.2**
  - [x] 6.6 编写属性测试：合并数据触发预标注
    - **Property 6: 合并数据触发预标注**
    - 验证合并完成后 InterviewEntityExtractor 被调用执行 AI 预标注
    - **验证: 需求 2.3**

- [x] 7. Label Studio 同步
  - [x] 7.1 实现 LabelStudioConnector 类（`src/interview/label_studio_connector.py`）
    - 注入现有 Label Studio 客户端（PAT + JWT 自动刷新）
    - sync_labels：将 AIFriendlyLabel 转换为 LS 任务格式，包含 predictions 预标注字段
    - check_connection：检查 LS 连接状态，失败时记录日志
    - 连接失败返回错误信息
    - _需求: 3.1, 3.2, 3.3, 3.4_
  - [x] 7.2 实现同步 API（`POST /api/interview/{project_id}/sync-to-label-studio`）
    - JWT 认证 + 租户校验
    - 调用 LabelStudioConnector.sync_labels 执行同步
    - 连接失败返回 502
    - _需求: 3.1_
  - [x] 7.3 编写属性测试：Label Studio 同步含预标注
    - **Property 7: Label Studio 同步含预标注**
    - 验证同步至 Label Studio 的任务包含 AI 预标注数据
    - **验证: 需求 3.1, 3.2**

- [x] 8. 检查点 - 确保后端所有组件测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 9. 前端离线导入与标签预览页面
  - [x] 9.1 实现离线导入界面
    - 使用 Ant Design Upload 组件，支持 .xlsx 和 .json 文件上传
    - 导入进度展示（Celery 任务状态轮询）
    - 错误详情展示（行号 + 字段 + 原因）
    - _需求: 2.1, 2.4, 2.5_
  - [x] 9.2 实现标签预览与操作界面
    - AI_Friendly_Label JSON 结构预览（Ant Design Tree / JSON Viewer）
    - 一键同步至 Label Studio 按钮
    - 质量评估报告展示（overall_score + dimension_scores）
    - _需求: 1.1, 1.4, 3.1_

- [x] 10. 最终检查点 - 确保前后端功能完整
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选属性测试任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号（本子模块编号），确保可追溯性
- 本子模块的需求编号与父模块的映射关系：需求 1 → 父需求 4，需求 2 → 父需求 5，需求 3 → 父需求 6
- 属性编号与父模块的映射关系：Property 1 → 父 Property 8，Property 2 → 父 Property 9，Property 3 → 父 Property 10，Property 4 → 父 Property 11，Property 5 → 父 Property 12，Property 6 → 父 Property 13，Property 7 → 父 Property 14，Property 8 → 父 Property 21
- 任务编号与父模块的映射关系：任务 2-4 → 父任务 8，任务 6 → 父任务 9，任务 7 → 父任务 10，任务 9 → 父任务 18
- 检查点任务确保增量验证，及时发现问题
- 属性测试使用 Hypothesis 框架验证通用正确性属性
