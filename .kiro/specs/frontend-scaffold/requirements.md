# 需求文档

## 简介

为现有的 React 前端组件搭建完整的 Vite + React + TypeScript 构建脚手架，使前端能够作为独立的开发服务器运行，并通过开发代理连接后端 FastAPI 服务（端口 8011）。项目已有完整的页面组件、路由定义、认证上下文、国际化配置和 API 服务层，但缺少 `package.json`、`vite.config.ts`、`index.html`、`App.tsx`、`main.tsx` 等构建入口文件。

## 术语表

- **Frontend_Scaffold**: 前端构建脚手架，包含 Vite 构建配置、入口文件、依赖声明等，使前端源码可独立编译和运行
- **Vite_Dev_Server**: Vite 开发服务器，提供热模块替换（HMR）和开发代理功能，默认监听端口 5173
- **Backend_API**: 后端 FastAPI 服务，通过 docker-compose.standalone.yml 映射到宿主机端口 8011，API 路径前缀为 `/api`
- **Dev_Proxy**: Vite 开发代理，将前端 `/api` 请求转发到 Backend_API（localhost:8011）
- **Entry_HTML**: `index.html` 入口文件，Vite 以此作为构建入口点
- **App_Component**: `App.tsx` 根组件，集成路由配置、AuthProvider 和 i18n 初始化
- **Main_Entry**: `main.tsx` 入口脚本，挂载 App_Component 到 DOM
- **Package_Manifest**: `package.json` 文件，声明项目依赖和脚本命令

## 需求

### 需求 1：创建 Package_Manifest

**用户故事：** 作为前端开发者，我希望有一个完整的 package.json 文件，以便能够安装依赖并运行开发脚本。

#### 验收标准

1. THE Package_Manifest SHALL 声明项目名称、版本和 `private: true` 标记
2. THE Package_Manifest SHALL 包含 `dev`、`build` 和 `preview` 脚本命令
3. THE Package_Manifest SHALL 在 dependencies 中包含以下运行时依赖：react、react-dom、react-router-dom、antd、@ant-design/icons、axios、i18next、react-i18next
4. THE Package_Manifest SHALL 在 devDependencies 中包含以下开发依赖：vite、@vitejs/plugin-react、typescript、@types/react、@types/react-dom
5. WHEN 开发者执行 `npm install` 后执行 `npm run dev` 时，THE Vite_Dev_Server SHALL 成功启动且无依赖缺失错误

### 需求 2：创建 Vite 构建配置

**用户故事：** 作为前端开发者，我希望 Vite 正确配置 React 插件和开发代理，以便前端能编译 TSX 并将 API 请求转发到后端。

#### 验收标准

1. THE Frontend_Scaffold SHALL 在 `src/frontend/vite.config.ts` 中提供 Vite 配置文件
2. THE Vite 配置 SHALL 启用 `@vitejs/plugin-react` 插件以支持 JSX/TSX 编译
3. THE Dev_Proxy SHALL 将所有匹配 `/api` 路径的请求转发到 `http://localhost:8011`
4. THE Dev_Proxy SHALL 设置 `changeOrigin: true` 以正确处理跨域请求头
5. THE Vite 配置 SHALL 将 `src/frontend` 设置为项目根目录（root）

### 需求 3：创建 Entry_HTML

**用户故事：** 作为前端开发者，我希望有一个 HTML 入口文件，以便 Vite 能以此为起点构建前端应用。

#### 验收标准

1. THE Entry_HTML SHALL 位于 `src/frontend/index.html`
2. THE Entry_HTML SHALL 包含一个 `id="root"` 的挂载点 div 元素
3. THE Entry_HTML SHALL 通过 `<script type="module" src="./main.tsx">` 引用 Main_Entry
4. THE Entry_HTML SHALL 设置 `<html lang="zh-CN">` 和 `<meta charset="UTF-8">`
5. THE Entry_HTML SHALL 设置页面标题为 "SuperInsight"

### 需求 4：创建 Main_Entry

**用户故事：** 作为前端开发者，我希望有一个 main.tsx 入口脚本，以便将 React 应用挂载到 DOM。

#### 验收标准

1. THE Main_Entry SHALL 位于 `src/frontend/main.tsx`
2. THE Main_Entry SHALL 使用 `ReactDOM.createRoot` 将 App_Component 渲染到 `id="root"` 的 DOM 元素
3. THE Main_Entry SHALL 在渲染前导入 i18n 初始化模块（`./i18n`）以确保国际化就绪
4. THE Main_Entry SHALL 使用 `React.StrictMode` 包裹 App_Component

### 需求 5：创建 App_Component

**用户故事：** 作为前端开发者，我希望有一个根组件整合路由、认证和国际化，以便所有现有页面能正常工作。

#### 验收标准

1. THE App_Component SHALL 位于 `src/frontend/App.tsx`
2. THE App_Component SHALL 使用 `BrowserRouter` 包裹所有路由
3. THE App_Component SHALL 使用 `AuthProvider` 包裹路由，使所有子组件可访问认证上下文
4. THE App_Component SHALL 使用 `React.Suspense` 包裹路由内容，并提供加载中的回退 UI
5. THE App_Component SHALL 通过 `<Routes>` 组件集成 `interviewRoutes` 中定义的所有路由
6. WHEN 用户访问根路径 `/` 时，THE App_Component SHALL 将用户重定向到 `/login`

### 需求 6：TypeScript 配置

**用户故事：** 作为前端开发者，我希望有正确的 TypeScript 配置，以便 TSX 文件能通过类型检查并正确编译。

#### 验收标准

1. THE Frontend_Scaffold SHALL 在 `src/frontend/tsconfig.json` 中提供 TypeScript 配置
2. THE TypeScript 配置 SHALL 设置 `jsx` 为 `react-jsx` 以支持 JSX 转换
3. THE TypeScript 配置 SHALL 设置 `strict: true` 以启用严格类型检查
4. THE TypeScript 配置 SHALL 设置 `moduleResolution` 为 `bundler` 以兼容 Vite 的模块解析
5. THE TypeScript 配置 SHALL 将 `include` 范围限定为 `src/frontend` 目录下的文件

### 需求 7：开发代理连通性

**用户故事：** 作为前端开发者，我希望前端开发服务器能正确代理 API 请求到后端，以便前端页面能正常调用后端接口。

#### 验收标准

1. WHEN 前端发起 `/api/auth/login` 请求时，THE Dev_Proxy SHALL 将请求转发到 `http://localhost:8011/api/auth/login`
2. WHEN 前端发起 `/api/interview/health` 请求时，THE Dev_Proxy SHALL 将请求转发到 `http://localhost:8011/api/interview/health`
3. WHEN 前端发起 `/api/users` 请求时，THE Dev_Proxy SHALL 将请求转发到 `http://localhost:8011/api/users`
4. THE Dev_Proxy SHALL 保留原始请求路径不做重写

### 需求 8：现有组件兼容性

**用户故事：** 作为前端开发者，我希望所有现有的页面和组件在新脚手架下能正常工作，无需修改现有源码。

#### 验收标准

1. THE Frontend_Scaffold SHALL 确保 LoginPage、RegisterPage、InterviewStartPage、InterviewSessionPage、OfflineImportPage、LabelPreviewPage、AdminUserPage 的导入路径保持有效
2. THE Frontend_Scaffold SHALL 确保 ProtectedRoute 和 LanguageSwitcher 组件的导入路径保持有效
3. THE Frontend_Scaffold SHALL 确保 AuthContext 的 Provider 在路由组件之上，使 `useAuth` 钩子在所有页面中可用
4. THE Frontend_Scaffold SHALL 确保 InterviewLayout 布局组件的导入路径保持有效
5. WHEN Vite_Dev_Server 启动后，THE Frontend_Scaffold SHALL 使所有现有 `.tsx` 文件通过 TypeScript 编译且无类型错误
