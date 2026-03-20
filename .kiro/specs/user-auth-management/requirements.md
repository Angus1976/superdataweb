# 需求文档：用户认证与企业管理系统

## 简介

为 SuperInsight Interview Service 构建完整的用户认证与企业管理系统。系统支持企业邮箱注册/登录、企业号关联、管理员对企业用户的增删改查及批量导入，并与现有 JWT 认证机制（`src/interview/security.py`）集成。

## 术语表

- **Auth_Service**: 用户认证服务，负责注册、登录、令牌签发与刷新
- **User_Manager**: 用户管理模块，负责企业用户的增删改查和批量导入
- **Enterprise**: 企业实体，通过唯一企业号标识，包含企业名称、域名等信息
- **Enterprise_Email**: 企业邮箱，格式为 `user@company.com`，其中 `@` 后的域名部分用于关联企业
- **Enterprise_Code**: 企业号，用于在注册时关联用户与企业的唯一标识符
- **Admin**: 管理员角色，拥有企业用户管理权限（增删改查、批量导入）
- **Member**: 普通成员角色，仅拥有基本访问权限
- **JWT_Token**: JSON Web Token，用于用户身份认证，包含 `user_id`、`tenant_id`、`role` 等声明
- **Refresh_Token**: 刷新令牌，用于在 Access Token 过期后获取新令牌
- **Batch_Import**: 批量导入操作，通过 Excel/CSV 文件一次性创建多个企业用户账号

## 需求

### 需求 1：用户注册

**用户故事：** 作为新用户，我希望使用企业邮箱和企业号进行注册，以便加入对应企业并使用系统。

#### 验收标准

1. WHEN 用户提交注册请求，THE Auth_Service SHALL 验证邮箱格式符合企业邮箱规范（包含 `@` 及有效域名，如 `user@company.com`）
2. WHEN 用户提交的企业邮箱域名部分无效或为公共邮箱域名（如 gmail.com、qq.com、163.com），THE Auth_Service SHALL 拒绝注册并返回提示信息"请使用企业邮箱注册"
3. WHEN 用户提交的 Enterprise_Code 在系统中不存在，THE Auth_Service SHALL 拒绝注册并返回提示信息"企业号不存在"
4. WHEN 用户提交的企业邮箱已被注册，THE Auth_Service SHALL 拒绝注册并返回提示信息"该邮箱已被注册"
5. THE Auth_Service SHALL 使用 bcrypt 算法对用户密码进行哈希处理后存储
6. WHEN 注册信息验证通过，THE Auth_Service SHALL 创建用户账号并将用户关联到 Enterprise_Code 对应的企业，默认角色为 Member
7. WHEN 用户注册成功，THE Auth_Service SHALL 返回 JWT_Token 和 Refresh_Token

### 需求 2：用户登录

**用户故事：** 作为已注册用户，我希望使用企业邮箱和密码登录系统，以便访问系统功能。

#### 验收标准

1. WHEN 用户提交登录请求，THE Auth_Service SHALL 验证企业邮箱和密码的组合是否正确
2. IF 用户提交的企业邮箱在系统中不存在，THEN THE Auth_Service SHALL 返回统一的错误信息"邮箱或密码错误"
3. IF 用户提交的密码与存储的哈希值不匹配，THEN THE Auth_Service SHALL 返回统一的错误信息"邮箱或密码错误"
4. WHEN 登录验证通过，THE Auth_Service SHALL 签发包含 `user_id`、`tenant_id`、`role` 声明的 JWT_Token
5. WHEN 登录验证通过，THE Auth_Service SHALL 同时签发 Refresh_Token
6. THE Auth_Service SHALL 将 JWT_Token 的有效期设置为 30 分钟，Refresh_Token 的有效期设置为 7 天

### 需求 3：令牌刷新

**用户故事：** 作为已登录用户，我希望在 Access Token 过期后能自动获取新令牌，以便无需重新登录即可继续使用系统。

#### 验收标准

1. WHEN 用户提交有效的 Refresh_Token，THE Auth_Service SHALL 签发新的 JWT_Token 和 Refresh_Token
2. IF 用户提交的 Refresh_Token 已过期，THEN THE Auth_Service SHALL 返回 HTTP 401 状态码
3. IF 用户提交的 Refresh_Token 无效或已被撤销，THEN THE Auth_Service SHALL 返回 HTTP 401 状态码
4. WHEN 新令牌签发成功，THE Auth_Service SHALL 将旧的 Refresh_Token 标记为已使用（单次使用策略）

### 需求 4：与现有 JWT 机制集成

**用户故事：** 作为开发者，我希望新的认证系统与现有的 `InterviewSecurity` 层无缝集成，以便现有 API 端点无需修改即可使用新的用户认证。

#### 验收标准

1. THE Auth_Service SHALL 使用与现有 `InterviewSecurity.get_current_tenant` 相同的 JWT_SECRET 和 JWT_ALGORITHM 配置
2. THE Auth_Service SHALL 在签发的 JWT_Token 中包含 `tenant_id` 声明，其值为用户所属企业的 ID
3. THE Auth_Service SHALL 在签发的 JWT_Token 中额外包含 `user_id` 和 `role` 声明
4. WHEN 现有端点通过 `get_current_tenant` 依赖注入获取 tenant_id 时，THE Auth_Service 签发的令牌 SHALL 与该依赖兼容，无需修改现有代码

### 需求 5：管理员用户管理（增删改查）

**用户故事：** 作为管理员，我希望能够管理企业内的用户账号，以便控制谁可以访问系统。

#### 验收标准

1. WHILE 用户角色为 Admin，THE User_Manager SHALL 允许查询本企业下的所有用户列表（支持分页）
2. WHILE 用户角色为 Admin，THE User_Manager SHALL 允许创建新的企业用户账号（指定邮箱、密码、角色）
3. WHILE 用户角色为 Admin，THE User_Manager SHALL 允许修改本企业用户的角色和状态（启用/禁用）
4. WHILE 用户角色为 Admin，THE User_Manager SHALL 允许删除本企业下的用户账号（软删除）
5. IF 非 Admin 角色的用户尝试访问用户管理接口，THEN THE User_Manager SHALL 返回 HTTP 403 状态码
6. THE User_Manager SHALL 仅允许管理员操作本企业（同一 tenant_id）下的用户，禁止跨企业操作

### 需求 6：批量导入用户

**用户故事：** 作为管理员，我希望通过上传 Excel 或 CSV 文件批量创建用户账号，以便高效地为企业添加多个用户。

#### 验收标准

1. WHILE 用户角色为 Admin，THE User_Manager SHALL 接受 `.xlsx` 或 `.csv` 格式的文件进行批量导入
2. WHEN 管理员上传批量导入文件，THE User_Manager SHALL 验证文件中每一行的邮箱格式和必填字段完整性
3. IF 批量导入文件中存在格式错误的行，THEN THE User_Manager SHALL 跳过错误行并在导入结果中报告错误详情（行号和错误原因）
4. IF 批量导入文件中存在已注册的邮箱，THEN THE User_Manager SHALL 跳过该行并在导入结果中标记为"邮箱已存在"
5. WHEN 批量导入完成，THE User_Manager SHALL 返回导入结果摘要（成功数、失败数、错误详情列表）
6. THE User_Manager SHALL 将单次批量导入的最大行数限制为 500 行

### 需求 7：企业管理

**用户故事：** 作为系统运营人员，我希望能够创建和管理企业信息，以便为企业分配唯一的企业号。

#### 验收标准

1. THE Auth_Service SHALL 为每个企业生成唯一的 Enterprise_Code
2. THE Auth_Service SHALL 存储企业的名称、域名和状态信息
3. WHEN 企业被禁用时，THE Auth_Service SHALL 拒绝该企业下所有用户的登录请求

### 需求 8：前端登录页面

**用户故事：** 作为用户，我希望通过一个简洁的登录页面输入企业邮箱和密码进行登录。

#### 验收标准

1. THE 登录页面 SHALL 提供企业邮箱输入框和密码输入框
2. WHEN 用户提交登录表单，THE 登录页面 SHALL 调用 Auth_Service 的登录接口并将 JWT_Token 存储到本地
3. IF 登录失败，THEN THE 登录页面 SHALL 显示 Auth_Service 返回的错误信息
4. WHEN 登录成功，THE 登录页面 SHALL 跳转到系统主页（`/interview/start`）
5. THE 登录页面 SHALL 提供"前往注册"链接，跳转到注册页面

### 需求 9：前端注册页面

**用户故事：** 作为新用户，我希望通过注册页面填写企业邮箱、密码和企业号完成注册。

#### 验收标准

1. THE 注册页面 SHALL 提供企业邮箱输入框（带提示文字"请输入企业邮箱，如 user@company.com"）、密码输入框和企业号输入框
2. THE 注册页面 SHALL 在企业邮箱输入框下方显示提示"请填写企业邮箱 @ 及域名"
3. WHEN 用户提交注册表单，THE 注册页面 SHALL 在前端验证邮箱格式后调用 Auth_Service 的注册接口
4. IF 注册失败，THEN THE 注册页面 SHALL 显示 Auth_Service 返回的错误信息
5. WHEN 注册成功，THE 注册页面 SHALL 自动登录并跳转到系统主页（`/interview/start`）
6. THE 注册页面 SHALL 提供"前往登录"链接，跳转到登录页面

### 需求 10：前端路由守卫与认证状态管理

**用户故事：** 作为用户，我希望未登录时自动跳转到登录页面，已登录时能正常访问受保护页面。

#### 验收标准

1. WHEN 未认证用户访问受保护路由，THE 前端路由守卫 SHALL 重定向到登录页面（`/login`）
2. WHEN 已认证用户访问登录或注册页面，THE 前端路由守卫 SHALL 重定向到系统主页（`/interview/start`）
3. THE 前端路由守卫 SHALL 在每次路由切换时检查 JWT_Token 是否存在且未过期
4. WHEN JWT_Token 即将过期（剩余有效期少于 5 分钟），THE 前端认证模块 SHALL 自动使用 Refresh_Token 获取新令牌
5. IF Refresh_Token 刷新失败，THEN THE 前端认证模块 SHALL 清除本地认证状态并重定向到登录页面

### 需求 11：前端管理员用户管理页面

**用户故事：** 作为管理员，我希望在管理页面中查看、创建、编辑和删除企业用户，以及批量导入用户。

#### 验收标准

1. WHILE 用户角色为 Admin，THE 管理页面 SHALL 显示企业用户列表（支持分页和搜索）
2. WHILE 用户角色为 Admin，THE 管理页面 SHALL 提供"新增用户"按钮，点击后弹出表单填写邮箱、密码和角色
3. WHILE 用户角色为 Admin，THE 管理页面 SHALL 在用户列表每行提供"编辑"和"删除"操作按钮
4. WHILE 用户角色为 Admin，THE 管理页面 SHALL 提供"批量导入"按钮，支持上传 Excel/CSV 文件
5. WHEN 批量导入完成，THE 管理页面 SHALL 显示导入结果摘要（成功数、失败数、错误详情）
6. IF 用户角色不是 Admin，THEN THE 前端路由守卫 SHALL 隐藏管理页面入口并禁止访问管理路由
