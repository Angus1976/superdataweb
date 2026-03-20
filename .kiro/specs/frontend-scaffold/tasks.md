# 实施计划：Frontend Scaffold

## 概述

为现有 React 前端组件创建完整的 Vite + React + TypeScript 构建脚手架。按照依赖顺序逐步创建 6 个新文件，确保每一步都可增量验证。测试使用 Vitest + fast-check。

## 任务

- [x] 1. 创建 package.json 和 tsconfig.json 基础配置
  - [x] 1.1 创建 `src/frontend/package.json`
    - 声明项目名称 `superinsight-frontend`、版本 `0.1.0`、`private: true`
    - 添加 `dev`、`build`、`preview` 脚本命令
    - 在 dependencies 中添加：react、react-dom、react-router-dom、antd、@ant-design/icons、axios、i18next、react-i18next
    - 在 devDependencies 中添加：vite、@vitejs/plugin-react、typescript、@types/react、@types/react-dom、vitest、fast-check
    - _需求: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 创建 `src/frontend/tsconfig.json`
    - 设置 `jsx: "react-jsx"`、`strict: true`、`moduleResolution: "bundler"`
    - 设置 `target: "ES2020"`、`module: "ESNext"`、`lib: ["ES2020", "DOM", "DOM.Iterable"]`
    - 设置 `esModuleInterop: true`、`skipLibCheck: true`、`resolveJsonModule: true`、`isolatedModules: true`、`noEmit: true`
    - 设置 `include` 为 `./**/*.ts` 和 `./**/*.tsx`
    - _需求: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 2. 创建 Vite 配置和 HTML 入口
  - [x] 2.1 创建 `src/frontend/vite.config.ts`
    - 启用 `@vitejs/plugin-react` 插件
    - 配置 `/api` 代理到 `http://localhost:8011`，设置 `changeOrigin: true`，不做路径重写
    - _需求: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 2.2 创建 `src/frontend/index.html`
    - 设置 `<html lang="zh-CN">`、`<meta charset="UTF-8">`
    - 添加 `<meta name="viewport">` 标签
    - 设置 `<title>SuperInsight</title>`
    - 添加 `<div id="root"></div>` 挂载点
    - 通过 `<script type="module" src="./main.tsx">` 引用入口脚本
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. 创建 React 入口文件
  - [x] 3.1 创建 `src/frontend/main.tsx`
    - 导入 `./i18n` 初始化模块（在 App 导入之前）
    - 使用 `ReactDOM.createRoot` 挂载到 `#root`
    - 使用 `React.StrictMode` 包裹 `App` 组件
    - _需求: 4.1, 4.2, 4.3, 4.4_

  - [x] 3.2 创建 `src/frontend/App.tsx`
    - 使用 `BrowserRouter` 包裹所有内容
    - 在 `BrowserRouter` 内使用 `AuthProvider` 包裹路由
    - 使用 `React.Suspense` 包裹路由内容，回退 UI 使用 antd `Spin` 组件
    - 通过 `<Routes>` 集成 `interviewRoutes`
    - 根路径 `/` 重定向到 `/login`
    - _需求: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 8.1, 8.2, 8.3, 8.4_

- [x] 4. 检查点 - 验证文件完整性
  - 确保所有 6 个新文件已创建且内容正确，检查导入路径是否有效，如有问题请向用户确认。

- [x] 5. 编写单元测试和属性基测试
  - [x] 5.1 创建 `src/frontend/__tests__/package.test.ts` 单元测试
    - 验证 package.json 的 name、version、private 字段
    - 验证 scripts 包含 dev、build、preview
    - 验证 dependencies 包含所有 8 个运行时依赖
    - 验证 devDependencies 包含所有 5 个开发依赖
    - _需求: 1.1, 1.2, 1.3, 1.4_

  - [x] 5.2 创建 `src/frontend/__tests__/static-files.test.ts` 单元测试
    - 验证 index.html 包含 `id="root"` div、`lang="zh-CN"`、`charset="UTF-8"`、标题 "SuperInsight"、script 引用 main.tsx
    - 验证 vite.config.ts 包含 react 插件和 changeOrigin 配置
    - 验证 tsconfig.json 的 jsx、strict、moduleResolution 设置
    - _需求: 2.2, 2.4, 3.2, 3.3, 3.4, 3.5, 6.2, 6.3, 6.4_

  - [x] 5.3 创建 `src/frontend/__tests__/app-structure.test.ts` 单元测试
    - 验证 App.tsx 包含 BrowserRouter、AuthProvider、Suspense、Routes 组件树
    - 验证根路径重定向到 /login
    - 验证 main.tsx 使用 createRoot 和 StrictMode
    - 验证 main.tsx 在渲染前导入 i18n
    - _需求: 4.2, 4.3, 4.4, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 5.4 编写属性基测试：代理路径保留（Property 1）
    - **Property 1: 代理路径保留**
    - 使用 fast-check 生成随机 `/api/*` 路径，验证代理配置将请求转发到 `http://localhost:8011` 且路径不变
    - 注释格式：`Feature: frontend-scaffold, Property 1: 代理路径保留`
    - **验证: 需求 2.3, 7.1, 7.2, 7.3, 7.4**

  - [x] 5.5 编写属性基测试：依赖完整性（Property 2）
    - **Property 2: package.json 依赖完整性**
    - 扫描所有现有 `.ts`/`.tsx` 文件的 import 语句，提取第三方包名，验证每个包名都在 package.json 中声明
    - 注释格式：`Feature: frontend-scaffold, Property 2: package.json 依赖完整性`
    - **验证: 需求 1.3, 1.4, 1.5, 8.1, 8.2, 8.4**

  - [x] 5.6 编写属性基测试：导入路径有效性（Property 3）
    - **Property 3: 组件导入路径有效性**
    - 解析新建文件（App.tsx、main.tsx）中的相对导入路径，验证每个路径解析到实际存在的文件
    - 注释格式：`Feature: frontend-scaffold, Property 3: 组件导入路径有效性`
    - **验证: 需求 8.1, 8.2, 8.3, 8.4**

- [x] 6. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP
- 每个任务引用了具体的需求编号以确保可追溯性
- 检查点任务确保增量验证
- 属性基测试验证通用正确性属性，单元测试验证具体示例和边界情况
