# PyAgentForge Test Frontend

用于测试 PyAgentForge 功能的 TypeScript 前端页面。

## 技术栈

- React 18
- TypeScript
- Vite
- WebSocket (流式通信)

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动后端服务

在 `demo/glm-provider` 目录下：

```bash
cd ../glm-provider
pip install -r requirements.txt
cp .env.example .env  # 配置 GLM_API_KEY
python server.py
```

### 3. 启动前端

```bash
npm run dev
```

访问 http://localhost:3000

## 功能特性

- 创建/管理多个会话
- WebSocket 流式响应
- HTTP REST API 回退
- 工具调用显示
- 模型选择

## 项目结构

```
test-frontend/
├── src/
│   ├── main.tsx       # 入口
│   ├── App.tsx        # 主应用
│   ├── api.ts         # API 客户端
│   └── index.css      # 样式
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

## API 代理配置

Vite 开发服务器自动代理以下请求到后端：

- `/api/*` → http://localhost:8100
- `/ws/*` → ws://localhost:8100

生产环境需要配置 Nginx 或其他反向代理。

## 构建生产版本

```bash
npm run build
```

输出到 `dist/` 目录。
