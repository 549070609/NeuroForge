# GLM Provider Backend

临时的 GLM 模型后端服务，用于测试 PyAgentForge 功能。

## 快速开始

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 配置环境变量:
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 GLM API Key
```

3. 启动服务:
```bash
python server.py
```

服务将在 http://localhost:8100 启动。

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/api/models` | GET | 列出可用模型 |
| `/api/sessions` | POST | 创建会话 |
| `/api/sessions/{id}` | GET | 获取会话详情 |
| `/api/sessions/{id}/messages` | POST | 发送消息 |
| `/ws/{session_id}` | WebSocket | 流式通信 |

## 获取 GLM API Key

1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/)
2. 注册/登录账号
3. 在控制台获取 API Key

## 支持的模型

- `glm-4-flash` - 快速响应（默认）
- `glm-4-plus` - 增强能力
- `glm-4-air` - 性价比高
- `glm-4-long` - 长上下文
