# 智慧校园安防系统

## 项目介绍

智慧校园安防系统前端项目，基于 Vue 3 + Vite + Element Plus 开发。

## 项目结构

```
demo/
├── frontend/          # 前端项目（人员A、B负责）
├── backend/           # 后端项目（人员C、D、E负责）
├── docs/              # 项目文档
├── ops/               # CI/CD配置（人员F负责）
├── README.md          # 项目说明
└── API_DOCUMENTATION.md  # 接口文档
```

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
cd frontend
npm run dev
```

启动成功后，访问 http://localhost:3000

### 3. 构建生产版本

```bash
cd frontend
npm run build
```

### 4. 预览生产版本

```bash
cd frontend
npm run preview
```

## 技术栈

### 前端
- Vue 3.3.4 - 渐进式JavaScript框架
- Vue Router 4.2.4 - 路由管理
- Pinia 2.1.4 - 状态管理
- Element Plus 2.3.14 - UI组件库
- Axios 1.5.1 - HTTP请求库
- Socket.io-client 4.6.1 - WebSocket客户端
- Vite 4.4.9 - 构建工具

### 后端
- Python Flask - Web框架
- SQLAlchemy - ORM框架
- Flasgger - Swagger API文档

## 文档

- [接口文档](./API_DOCUMENTATION.md) - 查看所有API接口定义、开发状态和联调指南

## 团队分工

- **人员A** - 前端UI与页面开发
- **人员B** - 前端组件与接口层
- **人员C** - 后端鉴权与用户管理
- **人员D** - 后端CV推理管线
- **人员E** - 后端告警与通知服务
- **人员F** - CI/CD与质量保障
