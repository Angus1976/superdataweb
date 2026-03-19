# 需求文档：基础设施子模块（Interview Infrastructure）

## 简介

基础设施子模块（`interview-infra`）是 `client-interview` 父模块的基础层子模块，负责安全认证（JWT + Presidio 脱敏 + 多租户隔离）、Prometheus 监控指标上报、FastAPI Router 统一错误处理、Docker 部署配置，以及前端导航入口与响应式布局。本子模块为其他所有子模块（demand-collection、intelligent-interview、label-construction）提供基础设施支撑。

本子模块从父模块 `.kiro/specs/client-interview/` 中提取，技术栈复用 FastAPI + React 19 + Ant Design + PostgreSQL + Redis + Prometheus + Docker Compose。SuperInsight v2.3.0。

## 术语表

- **Interview_System**：在线客户智能访谈系统，本模块的核心系统
- **InterviewSecurity**：访谈安全层组件，封装 JWT 认证、Presidio 脱敏和多租户隔离能力
- **Presidio**：微软开源的数据脱敏工具，用于对话内容中的敏感信息去标识化
- **JWT**：JSON Web Token，用于 API 接口的身份认证
- **Tenant**：租户，平台中的独立客户组织，数据严格隔离
- **ErrorResponse**：统一错误响应格式，包含 error、message、details、request_id 字段
- **Prometheus**：开源监控系统，用于采集和查询运行指标

## 需求

### 需求 1：访谈数据安全与多租户隔离

**用户故事：** 作为平台管理员，我希望所有访谈对话数据经过脱敏处理且客户数据严格隔离，以便满足企业数据安全合规要求。

#### 验收标准

1. THE InterviewSecurity SHALL 使用 Presidio 对所有访谈对话内容进行敏感信息去标识化处理后再存储
2. THE InterviewSecurity SHALL 基于多租户机制实现客户数据隔离，确保每个客户仅能访问自身项目数据
3. WHEN 客户请求访问非自身项目的数据, THE InterviewSecurity SHALL 拒绝请求并返回权限不足的错误响应（HTTP 403）
4. THE Interview_System SHALL 对所有访谈相关 API 接口执行 JWT 认证校验，未携带有效 JWT 的请求返回未认证错误（HTTP 401）

### 需求 2：前端导航与响应式布局

**用户故事：** 作为客户，我希望能够从平台主导航方便地进入智能访谈模块，并在移动设备上正常使用。

#### 验收标准

1. THE Interview_System SHALL 在现有 React Router 导航菜单中新增"客户智能访谈"入口
2. THE Interview_System SHALL 基于 Ant Design 的响应式能力，确保访谈界面在桌面端和移动端均可正常使用
3. WHEN 客户点击导航菜单中的"客户智能访谈"入口, THE Interview_System SHALL 跳转至 `/interview/start` 页面

### 需求 3：部署与监控

**用户故事：** 作为运维工程师，我希望新模块能够无缝集成到现有 Docker Compose 部署中，并通过现有监控体系观察运行状态。

#### 验收标准

1. THE Interview_System SHALL 以新增 `interview-service` 容器的方式无缝集成到现有 `docker-compose.yml` 配置中
2. THE Interview_System SHALL 复用现有 Prometheus 监控体系，新增访谈完成率和隐含信息补全率指标的监控
3. WHEN 访谈会话完成, THE Interview_System SHALL 上报访谈完成率、隐含信息补全率等核心指标至 Prometheus
