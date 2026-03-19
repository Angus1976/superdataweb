# 需求文档：智能访谈子模块（Intelligent Interview）

## 简介

智能访谈子模块（`intelligent-interview`）是 `client-interview` 父模块的核心交互子模块，负责访谈会话管理、多轮对话交互、隐含信息缺口检测与补全引导，以及访谈性能与异步处理。本子模块依赖 `demand-collection` 子模块提供的 Project、Industry_Template 和 InterviewEntityExtractor，依赖 `interview-infra` 子模块提供的 InterviewSecurity（JWT + Presidio + 多租户）。

本子模块从父模块 `.kiro/specs/client-interview/` 中提取，技术栈复用 FastAPI + React 19 + Ant Design + PostgreSQL (JSONB) + Redis/Celery。

## 术语表

- **Interview_System**：在线客户智能访谈系统，本模块的核心系统
- **Interview_Session**：访谈会话，客户与 AI 之间的多轮对话交互实例
- **Entity_Extractor**：实体提取器，复用 `demand-collection` 子模块中的 InterviewEntityExtractor
- **Industry_Template**：行业模板，由 `demand-collection` 子模块管理，本模块在会话启动时加载
- **Project**：项目，由 `demand-collection` 子模块创建和管理
- **Interview_Summary**：访谈摘要，访谈结束后自动生成的结构化总结文档
- **Implicit_Gap**：隐含信息缺口，AI 检测到的客户未明确表述但业务逻辑所需的信息空白
- **Completion_Suggestion**：补全建议，AI 基于上下文生成的信息补全推荐项
- **InterviewSecurity**：安全层，由 `interview-infra` 子模块提供 JWT 认证、Presidio 脱敏和多租户隔离
- **Presidio**：微软开源的数据脱敏工具，用于对话内容中的敏感信息去标识化
- **AIResponse**：AI 响应对象，包含回复消息、隐含缺口列表、当前轮次和最大轮次
- **SessionStatus**：会话状态对象，包含当前轮次、异步任务进度等信息

## 依赖子模块

| 子模块 | 提供能力 |
|--------|----------|
| `demand-collection` | Project 模型、Industry_Template、InterviewEntityExtractor（extract_from_message）、Pydantic 数据模型 |
| `interview-infra` | InterviewSecurity（JWT 认证 + Presidio 脱敏 + 多租户隔离） |

## 需求

### 需求 1：智能访谈对话交互

**用户故事：** 作为客户，我希望通过聊天式对话描述业务规则，以便 AI 能够准确理解并实时提取关键信息。

#### 验收标准

1. WHEN 客户进入 `/interview/session/:project_id` 页面, THE Interview_System SHALL 展示聊天式对话界面，并加载该项目关联的 Industry_Template
2. THE Interview_System SHALL 提供 3 套内置系统提示词模板（金融、电商、制造），支持按行业切换
3. WHEN 客户发送一条对话消息, THE Entity_Extractor SHALL 在该轮对话结束后调用现有实体/属性提取模型进行实时提取
4. WHEN 实体提取完成, THE Interview_System SHALL 在对话界面侧边栏实时展示提取到的 JSON 结构数据
5. WHILE Interview_Session 的对话轮次达到 30 轮, THE Interview_System SHALL 自动结束该访谈会话
6. WHEN Interview_Session 结束（达到最大轮次或客户主动结束）, THE Interview_System SHALL 自动生成 Interview_Summary 和初步实体-规则-属性列表

### 需求 2：隐含信息缺口检测与补全引导

**用户故事：** 作为客户，我希望 AI 能够主动发现我遗漏的信息并引导我补充，以便需求收集更加完整。

#### 验收标准

1. WHEN 每轮对话结束后, THE Interview_System SHALL 分析当前对话上下文，检测 Implicit_Gap
2. WHEN 检测到 Implicit_Gap, THE Interview_System SHALL 自动生成引导性问题并推荐给客户
3. WHEN 客户点击"一键补全"按钮, THE Interview_System SHALL 基于当前上下文生成 5 条 Completion_Suggestion
4. WHERE 客户设备支持 Web Speech API, THE Interview_System SHALL 提供语音输入选项作为文字输入的替代方式

### 需求 3：访谈性能与异步处理

**用户故事：** 作为客户，我希望每轮访谈对话的响应速度足够快，以便获得流畅的交互体验。

#### 验收标准

1. WHEN 客户发送一轮对话消息, THE Interview_System SHALL 在 2 秒内返回 AI 响应（利用现有 Celery 异步任务队列）
2. THE Interview_System SHALL 使用现有 Celery 异步任务队列处理实体提取和标签生成等耗时操作
3. WHILE 异步任务正在执行, THE Interview_System SHALL 在前端界面展示处理进度指示