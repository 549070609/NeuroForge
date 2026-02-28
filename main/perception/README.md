# 主动感知器插件

基于 ATON/TOON 日志的主动感知与决策，可作为 PyAgentForge 插件加载。

## 快速开始

```bash
# 安装依赖（aton-format / toon-formatter 为内部私有包，需通过内部 PyPI 安装）
pip install --index-url <PRIVATE_PYPI_URL> aton-format toon-formatter

# 本地源码开发模式安装
pip install -e path/to/aton-format -e path/to/toon-formatter

# 运行单元测试（无需外部包，覆盖 detector / perceive / executor）
py -m pytest tests/ -v

# 验证插件加载（从 main 目录，需先 pip install -e agentforge-engine）
cd .. && python -m perception.test_plugin_load
```

## 模块说明

| 文件 | 说明 |
|------|------|
| `detector.py` | `detect_format(raw)` — 检测 ATON/TOON 格式 |
| `parser.py` | `parse_log(raw, fmt?)` — 解析为 Python dict/list |
| `perception.py` | `perceive(data, rules?)` — 感知与决策 |
| `tools.py` | ParseLogTool, PerceiveTool, ReadLogsTool |
| `PLUGIN.py` | 插件入口 |
| `plugin_config.yaml` | 配置示例 |

## 插件配置

在 Engine/Service 的 plugin_config 中：

```yaml
enabled:
  - integration.perception
plugin_dirs:
  - "."   # 相对于 Agent-Learn/main，插件位于 main/perception/
config:
  integration.perception:
    log_path: "./logs"
    cron_expr: "*/5 * * * *"
    filter_rules:
      level: ["error", "warn"]
```

## 使用示例

```python
from perception import detect_format, parse_log, perceive

# 解析
raw = "events[2]{id,level,message}:\n  1,error,Connection timeout\n  2,info,User login"
data = parse_log(raw)

# 感知与决策
result = perceive(data, {"error_triggers": "find_user"})
# result.decision: find_user | execute | call_agent | none
```

## 依赖

- aton-format >= 2.0.0
- toon-formatter >= 1.0.0
- pyagentforge >= 3.0.0

---

## 日志上报采集说明规范

### 一、采集方式

| 方式 | 说明 | 配置 |
|------|------|------|
| **文件轮询** | Cron 定时从 `log_path` 读取文件 | `cron_expr`、`log_path` |
| **Webhook** | HTTP POST 推送日志到 `/perception/webhook` | `webhook.path`、`webhook.secret` |
| **EventBus** | 订阅 `log.written` 等事件，携带 `log` 或 `data` | `event_triggers` |
| **Agent 工具** | Agent 主动调用 `read_logs`、`parse_log`、`perceive` | 无需额外配置 |

### 二、日志格式要求

感知器支持以下格式，并按优先级识别：

| 格式 | 识别规则 | 示例 |
|------|----------|------|
| **ATON** | 以 `@schema` 或 `@defaults` 开头 | 见下方 ATON 示例 |
| **TOON** | 含 `{fields}:` 且 `[N]` 模式 | 见下方 TOON 示例 |
| **JSON** | Webhook 中 `log`/`data` 为 dict 时直接使用 | `{"events": [...]}` |
| **纯文本** | 需先由上层解析为 ATON/TOON 后再传入 | — |

### 三、事件结构规范

每条日志事件需满足以下约束，方可被正确感知与决策：

| 字段 | 必选 | 类型 | 说明 |
|------|------|------|------|
| `level` | ✅ | str | 日志级别：`error`、`warn`/`warning`、`info`、`debug` |
| `message` | 推荐 | str | 事件描述，用于决策原因展示 |
| `severity` | 可选 | str | 与 `level` 等价，二选一 |
| `log_level` | 可选 | str | 与 `level` 等价，二选一 |
| `type` | 可选 | str | 与 `level` 等价，二选一 |
| `id`、`timestamp`、`source` 等 | 可选 | any | 扩展字段，不影响决策 |

**容器键名**（顶层数组或 dict 的 key，二选一即可）：
`events`、`logs`、`records`、`data`、`items`，或任意首个列表类型值。

### 四、日志级别语义

| 级别 | 决策行为（默认） | 可配置 |
|------|------------------|--------|
| `error` | 触发 `error_triggers` | find_user / execute / call_agent |
| `warn`、`warning` | 触发 `warn_triggers` | find_user / execute / call_agent |
| `info`、`debug` | 不触发 | 可加入 `levels` 扩展 |

### 五、上报示例

**ATON 格式（文本）**:

```
@schema[id:int, level:str, message:str]
events(3):
  1, "error", "Database connection timeout after 30s"
  2, "info", "User login successful"
  3, "warn", "Memory usage at 85%"
```

**TOON 格式（文本）**:

```
events[3]{id,level,message}:
  1,error,Database connection timeout after 30s
  2,info,User login successful
  3,warn,Memory usage at 85%
```

**Webhook JSON 示例**:

```json
{
  "log": "events[2]{id,level,message}:\n  1,error,Connection refused\n  2,info,OK",
  "source": "my-service",
  "timestamp": "2026-02-25T10:00:00Z"
}
```

或直接传已解析结构：

```json
{
  "data": {
    "events": [
      {"id": 1, "level": "error", "message": "Connection refused"},
      {"id": 2, "level": "info", "message": "OK"}
    ]
  }
}
```

**文件日志（ReadLogsTool 读取）**:

- 支持单文件或目录 + `pattern` 通配
- `level_filter` 为正则，如 `ERROR|WARN` 用于按行过滤
- 建议配合 ATON/TOON 或结构化 JSON 行，便于 `parse_log` 解析后 `perceive`

### 六、不符合规范的处理

| 情况 | 行为 |
|------|------|
| 无 `level`/`severity`/`log_level`/`type` | 事件被跳过，不参与决策 |
| 格式无法识别（非 ATON/TOON） | `parse_log` 抛出 `ValueError` |
| 所有事件均为 info/debug | 决策为 `none`，不执行 |
| Webhook 无 `log`、`data`、`raw` | 返回 `{"status": "skipped", "reason": "no log data in payload"}` |
