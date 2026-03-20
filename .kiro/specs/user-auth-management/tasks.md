# 实现计划：用户认证与企业管理系统

## 概述

基于现有 FastAPI + SQLAlchemy async + PostgreSQL + Redis 技术栈，为 SuperInsight Interview Service 添加完整的用户认证与企业管理能力。后端使用 Python，前端使用 React + Ant Design + React Router，支持中英文国际化（i18n），使用 React Context 管理认证状态，与现有 InterviewSecurity JWT 机制集成。

## 任务

- [x] 1. 数据库迁移与后端基础设施
  - [x] 1.1 创建数据库迁移文件 `migrations/004_create_auth_tables.sql`
    - 创建 `enterprises` 表（id, name, code, domain, status, created_at, updated_at）
    - 创建 `users` 表（id, email, password_hash, enterprise_id, role, is_active, is_deleted, created_at, updated_at）
    - 创建 `refresh_tokens` 表（id, user_id, token_hash, is_used, expires_at, created_at）
    - 添加唯一索引和外键约束
    - _需求: 1.5, 1.6, 3.4, 4.2, 5.6, 7.1, 7.2_

  - [x] 1.2 扩展配置 `src/interview/config.py`
    - 新增 `ACCESS_TOKEN_EXPIRE_MINUTES`、`REFRESH_TOKEN_EXPIRE_DAYS`、`REDIS_URL` 配置项
    - 复用现有 `JWT_SECRET` 和 `JWT_ALGORITHM`
    - _需求: 2.6, 4.1_

  - [x] 1.3 添加后端依赖到 `requirements.txt`
    - 添加 `bcrypt`、`redis[hiredis]`、`openpyxl`、`python-csv` 等依赖
    - _需求: 1.5, 6.1_

  - [x] 1.4 创建 Pydantic 模型文件 `src/interview/auth_models.py`
    - 定义 RegisterRequest、LoginRequest、RefreshRequest、TokenResponse
    - 定义 UserCreateRequest、UserUpdateRequest、UserResponse、PaginatedUsers
    - 定义 BatchImportResult、BatchImportError
    - 实现企业邮箱验证器（拒绝公共邮箱域名）
    - _需求: 1.1, 1.2, 5.2, 6.5_

- [x] 2. 检查点 - 确保基础设施就绪
  - 确保所有基础文件创建完成，检查语法错误，如有问题请询问用户。

- [x] 3. 后端认证服务
  - [x] 3.1 创建 Redis 客户端工具 `src/interview/redis_client.py`
    - 初始化 Redis 异步连接
    - 提供 token 黑名单的 set/get/exists 方法
    - _需求: 3.4_

  - [x] 3.2 实现 AuthService `src/interview/auth_service.py`
    - 实现 `register` 方法：验证企业号存在性、邮箱唯一性、bcrypt 哈希密码、创建用户、签发令牌对
    - 实现 `login` 方法：验证邮箱密码、检查企业状态、签发令牌对
    - 实现 `create_access_token` 方法：JWT payload 包含 user_id、tenant_id（= enterprise_id）、role
    - 实现 `create_refresh_token` 方法：生成 refresh token 并存储哈希到数据库
    - 实现 `refresh_token` 方法：验证 refresh token、标记旧 token 已使用、签发新令牌对
    - 实现 `revoke_refresh_token` 方法：将 token 标记为已使用
    - _需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 7.3_

  - [x] 3.3 编写 AuthService 属性测试
    - **属性 1: JWT 令牌兼容性** — 由 AuthService 签发的 JWT 必须能被现有 `InterviewSecurity.get_current_tenant` 正确解析并返回 tenant_id
    - **验证: 需求 4.1, 4.2, 4.4**

  - [x] 3.4 编写 AuthService 单元测试
    - 测试注册流程：有效注册、公共邮箱拒绝、企业号不存在、邮箱重复
    - 测试登录流程：正确登录、错误密码、不存在邮箱、企业被禁用
    - 测试令牌刷新：有效刷新、过期 token、已使用 token
    - _需求: 1.1-1.7, 2.1-2.6, 3.1-3.4_

- [x] 4. 后端用户管理与企业服务
  - [x] 4.1 实现 EnterpriseService `src/interview/enterprise_service.py`
    - 实现 `create_enterprise`：生成唯一企业号、存储企业信息
    - 实现 `get_enterprise_by_code`：按企业号查询
    - 实现 `disable_enterprise`：禁用企业
    - _需求: 7.1, 7.2, 7.3_

  - [x] 4.2 实现 UserService `src/interview/user_service.py`
    - 实现 `list_users`：分页查询本企业用户（支持搜索）
    - 实现 `create_user`：管理员创建用户（bcrypt 密码哈希）
    - 实现 `update_user`：修改角色和启用/禁用状态
    - 实现 `delete_user`：软删除用户
    - 实现 `batch_import`：解析 Excel/CSV 文件，逐行验证并创建用户，返回导入结果摘要
    - 批量导入限制最大 500 行
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 4.3 编写 UserService 单元测试
    - 测试分页查询、创建用户、修改角色、软删除
    - 测试批量导入：正常导入、格式错误行跳过、邮箱重复跳过、超过 500 行限制
    - _需求: 5.1-5.6, 6.1-6.6_

- [x] 5. 后端路由与权限控制
  - [x] 5.1 创建认证路由 `src/interview/auth_router.py`
    - POST `/api/auth/register` — 用户注册（无需认证）
    - POST `/api/auth/login` — 用户登录（无需认证）
    - POST `/api/auth/refresh` — 刷新令牌（无需认证，需 Refresh Token）
    - _需求: 1.7, 2.4, 2.5, 3.1_

  - [x] 5.2 创建用户管理路由 `src/interview/user_router.py`
    - GET `/api/users` — 查询用户列表（Admin 权限）
    - POST `/api/users` — 创建用户（Admin 权限）
    - PUT `/api/users/{user_id}` — 修改用户（Admin 权限）
    - DELETE `/api/users/{user_id}` — 删除用户（Admin 权限）
    - POST `/api/users/batch-import` — 批量导入（Admin 权限）
    - 实现 `get_current_user` 依赖注入：从 JWT 提取 user_id、tenant_id、role
    - 实现 `require_admin` 依赖注入：检查 role == "admin"，否则返回 403
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1_

  - [x] 5.3 在 `src/interview/main.py` 中注册新路由
    - 引入并挂载 auth_router 和 user_router
    - _需求: 4.4_

  - [x] 5.4 编写路由集成测试
    - 测试认证路由：注册、登录、刷新令牌的 HTTP 请求/响应
    - 测试权限控制：非 Admin 访问用户管理接口返回 403
    - 测试租户隔离：Admin 无法操作其他企业的用户
    - _需求: 5.5, 5.6, 4.4_

- [x] 6. 检查点 - 后端功能验证
  - 确保所有后端测试通过，如有问题请询问用户。

- [x] 7. 前端国际化基础设施
  - [x] 7.1 创建 i18n 配置 `src/frontend/i18n/index.ts`
    - 配置 i18next + react-i18next
    - 默认语言设为中文（zh-CN）
    - 支持中英文切换
    - _需求: 用户额外要求 - 国际化_

  - [x] 7.2 创建中文语言包 `src/frontend/i18n/locales/zh-CN.json`
    - 包含登录、注册、管理页面、通用操作等所有文案
    - _需求: 用户额外要求 - 国际化_

  - [x] 7.3 创建英文语言包 `src/frontend/i18n/locales/en-US.json`
    - 与中文语言包结构一致的英文翻译
    - _需求: 用户额外要求 - 国际化_

- [x] 8. 前端认证状态管理
  - [x] 8.1 创建 Axios 实例与拦截器 `src/frontend/services/api.ts`
    - 创建 Axios 实例，请求拦截器自动附加 Authorization header
    - 响应拦截器：401 时自动使用 Refresh Token 刷新，刷新失败则清除状态并跳转登录页
    - 令牌即将过期（< 5 分钟）时主动刷新
    - _需求: 10.4, 10.5_

  - [x] 8.2 创建 AuthContext `src/frontend/contexts/AuthContext.tsx`
    - 使用 React Context 管理认证状态（user, tokens, isAuthenticated, role）
    - 提供 login、register、logout、refreshToken 方法
    - 初始化时从 localStorage 恢复认证状态
    - _需求: 10.1, 10.3, 10.4, 10.5_

  - [x] 8.3 创建 ProtectedRoute 组件 `src/frontend/components/ProtectedRoute.tsx`
    - 未认证用户重定向到 `/login`
    - 已认证用户访问 `/login` 或 `/register` 时重定向到 `/interview/start`
    - 支持角色权限检查（Admin 路由守卫）
    - _需求: 10.1, 10.2, 10.3, 11.6_

- [x] 9. 前端页面实现
  - [x] 9.1 创建登录页面 `src/frontend/pages/LoginPage.tsx`
    - 使用 Ant Design Form 组件，现代化酷炫设计（渐变背景、卡片阴影、品牌 Logo）
    - 企业邮箱和密码输入框，表单验证
    - 登录成功后存储 token 并跳转到 `/interview/start`
    - 登录失败显示错误信息
    - 提供"前往注册"链接
    - 支持 i18n 中英文切换
    - _需求: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 9.2 创建注册页面 `src/frontend/pages/RegisterPage.tsx`
    - 使用 Ant Design Form 组件，与登录页风格一致的现代化设计
    - 企业邮箱（带提示文字）、密码、企业号输入框
    - 前端邮箱格式验证
    - 注册成功后自动登录并跳转
    - 注册失败显示错误信息
    - 提供"前往登录"链接
    - 支持 i18n 中英文切换
    - _需求: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 9.3 创建管理员用户管理页面 `src/frontend/pages/AdminUserPage.tsx`
    - 使用 Ant Design Table 组件展示用户列表（分页、搜索）
    - "新增用户"按钮 + Modal 表单（邮箱、密码、角色选择）
    - 每行"编辑"和"删除"操作按钮
    - "批量导入"按钮 + Upload 组件（支持 .xlsx/.csv）
    - 导入完成后显示结果摘要（成功数、失败数、错误详情）
    - 现代化酷炫设计（统计卡片、操作栏、表格样式）
    - 支持 i18n 中英文切换
    - _需求: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 9.4 创建语言切换组件 `src/frontend/components/LanguageSwitcher.tsx`
    - 提供中英文切换下拉菜单
    - 集成到布局组件中
    - _需求: 用户额外要求 - 国际化_

- [x] 10. 前端路由整合
  - [x] 10.1 更新路由配置 `src/frontend/routes/interviewRoutes.tsx`
    - 添加 `/login`、`/register`、`/admin/users` 路由
    - 使用 ProtectedRoute 包裹受保护路由
    - Admin 路由使用角色守卫
    - _需求: 10.1, 10.2, 11.6_

  - [x] 10.2 更新布局组件 `src/frontend/layouts/InterviewLayout.tsx`
    - 侧边栏菜单添加"用户管理"入口（仅 Admin 可见）
    - 顶部添加用户信息显示、语言切换和退出登录按钮
    - _需求: 11.6_

- [x] 11. 检查点 - 前端功能验证
  - 确保所有前端组件无语法错误、类型检查通过，如有问题请询问用户。

- [x] 12. Docker 与集成配置
  - [x] 12.1 更新 `docker-compose.standalone.yml`
    - 添加 `ACCESS_TOKEN_EXPIRE_MINUTES` 和 `REFRESH_TOKEN_EXPIRE_DAYS` 环境变量
    - 确保 Redis 连接配置正确
    - _需求: 2.6, 4.1_

  - [x] 12.2 更新 `Dockerfile.interview`
    - 确保新增的 Python 依赖（bcrypt, redis, openpyxl）被正确安装
    - _需求: 1.5, 6.1_

- [x] 13. 最终检查点 - 全部验证
  - 确保所有测试通过，后端路由正确注册，前端页面正常渲染，如有问题请询问用户。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号，确保可追溯性
- 检查点任务用于阶段性验证，确保增量开发的正确性
- 属性测试验证核心正确性属性（JWT 兼容性），单元测试验证具体场景和边界条件
- 前端使用 Ant Design 最佳实践，确保现代化酷炫的 UI 设计
- 默认语言为中文，支持中英文国际化切换
