# 实施计划：基础设施子模块（Interview Infrastructure）

## 概述

基于需求文档（3 项需求、10 条验收标准）和设计文档（5 个核心组件、4 条正确性属性），将 `interview-infra` 子模块拆分为增量式编码任务。后端使用 Python (FastAPI + Presidio + prometheus_client)，前端使用 TypeScript (React 19 + Ant Design)，部署使用 Docker Compose。

本子模块提取自父模块 `.kiro/specs/client-interview/`，是基础（FOUNDATION）模块，其他子模块（demand-collection、intelligent-interview、label-construction）依赖本模块提供的安全层、错误处理和监控能力。

## 任务

- [x] 1. 安全层与认证机制
  - [x] 1.1 实现 InterviewSecurity 类（`src/interview/security.py`）
    - 实现 verify_tenant_access：查询 client_projects 表校验租户对项目的访问权限，不匹配返回 False
    - 实现 sanitize_content：集成 Presidio AnalyzerEngine + AnonymizerEngine，支持手机号、身份证号、邮箱、银行卡号、姓名等 PII 检测与脱敏
    - 实现 get_current_tenant：解码 JWT token 提取 tenant_id claim，token 无效时抛出认证异常
    - 复用现有 JWT 认证中间件
    - _需求: 1.1, 1.2, 1.3, 1.4_
  - [x] 1.2 编写属性测试：Presidio 敏感信息脱敏
    - **Property 1: Presidio 敏感信息脱敏**
    - 使用 Hypothesis 生成含 PII 模式的文本（手机号、身份证号、邮箱），验证脱敏后不包含原始敏感信息
    - **验证: 需求 1.1**
  - [x] 1.3 编写属性测试：多租户数据隔离
    - **Property 2: 多租户数据隔离**
    - 验证租户 A 无法访问租户 B 的项目数据，返回 HTTP 403
    - **验证: 需求 1.2, 1.3**
  - [x] 1.4 编写属性测试：JWT 认证校验
    - **Property 3: JWT 认证校验**
    - 验证不携带有效 JWT 的请求被拒绝，返回 HTTP 401
    - **验证: 需求 1.4**

- [x] 2. 检查点 - 确保安全层测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 3. Prometheus 监控指标
  - [x] 3.1 实现 Prometheus 指标定义与上报（`src/interview/metrics.py`）
    - 定义 interview_sessions_total Counter（按 status 标签：active/completed/terminated）
    - 定义 interview_completion_rate Gauge
    - 定义 implicit_gap_total Counter 和 implicit_gap_completed Counter
    - 定义 implicit_gap_completion_rate Gauge
    - 定义 interview_request_duration Histogram（按 endpoint/method 标签）
    - 实现 report_session_completed 函数：会话完成时更新所有相关指标
    - _需求: 3.2, 3.3_
  - [x] 3.2 编写属性测试：Prometheus 指标上报
    - **Property 4: Prometheus 指标上报**
    - 验证已完成的会话向 Prometheus 上报访谈完成率和隐含信息补全率指标，且指标值在 0.0 ~ 1.0 范围内
    - **验证: 需求 3.2, 3.3**

- [x] 4. FastAPI Router 汇总与错误处理
  - [x] 4.1 创建统一的 FastAPI Router（`src/interview/router.py`）
    - 定义 ErrorResponse Pydantic 模型（error, message, details, request_id）
    - 实现 JWT 认证依赖注入（get_current_tenant），无效 token 返回 HTTP 401
    - 实现租户访问校验依赖注入（verify_project_access），无权限返回 HTTP 403
    - 实现统一异常处理器：HTTPException → ErrorResponse，ValidationError → HTTP 422
    - 实现各错误场景的 HTTP 状态码映射（401/403/404/400/409/422/502/504）
    - 配置 `/api/interview/*` 路由前缀
    - _需求: 1.4, 错误处理设计_

- [x] 5. 检查点 - 确保后端基础设施测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [x] 6. 前端导航与响应式布局
  - [x] 6.1 在 React Router 导航菜单中新增"客户智能访谈"入口
    - 在现有导航菜单 items 中新增 interview 菜单项（icon: MessageOutlined，label: 客户智能访谈）
    - 点击跳转至 `/interview/start`
    - 新增 `/interview/start` 和 `/interview/session/:projectId` 路由定义
    - 实现 InterviewLayout 响应式布局组件，基于 Ant Design Grid useBreakpoint 适配桌面端和移动端
    - _需求: 2.1, 2.2, 2.3_

- [x] 7. Docker 部署配置
  - [x] 7.1 新增 interview-service 容器配置
    - 编写 Dockerfile.interview（基于 python:3.11-slim，安装依赖，暴露 8001 端口）
    - 在 docker-compose.yml 中新增 interview-service 容器定义
    - 配置与 PostgreSQL、Redis 的网络连接和环境变量
    - 配置 Prometheus 监控端点（/metrics）
    - 配置健康检查（/health）
    - _需求: 3.1, 3.2_

- [x] 8. 最终检查点 - 基础设施模块集成验证
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的子任务为可选属性测试任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号（本子模块编号），确保可追溯性
- 本子模块的需求编号与父模块的映射关系：需求 1 → 父需求 7，需求 2 → 父需求 9，需求 3 → 父需求 10
- 属性编号与父模块的映射关系：Property 1 → 父 Property 15，Property 2 → 父 Property 16，Property 3 → 父 Property 17，Property 4 → 父 Property 18
- 任务编号与父模块的映射关系：任务 1 → 父任务 2，任务 3 → 父任务 13，任务 4 → 父任务 14，任务 6 → 父任务 19，任务 7 → 父任务 21
- 本模块是 FOUNDATION 模块，应优先于其他子模块实施
- 检查点任务确保增量验证，及时发现问题
- 属性测试使用 Hypothesis 框架验证通用正确性属性
