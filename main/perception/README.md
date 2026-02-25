# 主动感知器插件

基于 ATON/TOON 日志的主动感知与决策，可作为 PyAgentForge 插件加载。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行解析验证（从 perception 目录）
python test_parser.py

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
