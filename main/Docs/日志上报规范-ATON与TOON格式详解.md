# 日志上报规范 · ATON 与 TOON 格式详解

**依赖**：`aton-format >= 2.0.0`，`toon-formatter >= 1.0.0`  
**上级文档**：[日志上报规范 · 总览](./日志上报规范-总览.md)

---

## 目录

- [ATON 格式](#aton-格式)
  - [语法结构](#语法结构)
  - [组成元素](#组成元素)
  - [示例](#aton-示例)
- [TOON 格式](#toon-格式)
  - [语法结构](#语法结构-1)
  - [组成元素](#组成元素-1)
  - [示例](#toon-示例)
- [Webhook JSON 封装](#webhook-json-封装)
- [格式对比与选型](#格式对比与选型)

---

## ATON 格式

ATON（Annotated Tabular Object Notation）是一种带类型注解的表格式文本格式，适用于需要明确字段类型的结构化日志。

### 语法结构

```
@schema[字段名:类型, 字段名:类型, ...]
[@defaults{字段名:"默认值", ...}]
容器名(N):
  值1, 值2, ...
  值1, 值2, ...
```

**识别规则**：文本首行以 `@schema` 或 `@defaults` 开头。

### 组成元素

#### `@schema` 指令

声明数据字段的名称与类型，为必填项。字段按声明顺序与数据行一一对应。

```
@schema[id:int, level:str, message:str, timestamp:str]
```

支持的字段类型：

| 类型 | 说明 |
|------|------|
| `str` | 字符串，值可用双引号包裹 |
| `int` | 整数 |
| `float` | 浮点数 |
| `bool` | 布尔值（`true` / `false`） |

#### `@defaults` 指令

可选。声明字段的默认填充值，当数据行中对应字段缺省时自动补全。

```
@defaults{source:"unknown", env:"production"}
```

#### 容器块

格式为 `容器名(N):` + 缩进数据行，`N` 为数据行数量（整数）。

- 容器名支持 `events`、`logs`、`records`、`data`、`items` 等（感知器优先识别这些名称）
- 数据行缩进两个空格
- 字符串值建议用双引号包裹；数值和布尔值无需引号
- 字段间以逗号 `,` 分隔

### ATON 示例

#### 最小上报

仅包含感知决策所需的必要字段：

```
@schema[id:int, level:str, message:str]
events(2):
  1, "error", "Database connection timeout after 30s"
  2, "warn",  "Memory usage at 85%"
```

**感知结果**：命中事件 1（`error`），触发 `error_triggers`，默认决策 `find_user`。

---

#### 完整上报

包含扩展字段，提供更丰富的上下文信息：

```
@schema[id:int, level:str, message:str, source:str, timestamp:str]
@defaults{source:"backend"}
events(4):
  1, "error", "Disk I/O failure on /dev/sda1", "disk-monitor", "2026-02-28T08:00:00Z"
  2, "warn",  "CPU usage at 92% for 5 minutes", "backend",      "2026-02-28T08:01:00Z"
  3, "info",  "Health check passed",             "backend",      "2026-02-28T08:02:00Z"
  4, "debug", "Cache hit ratio: 0.97",           "cache",        "2026-02-28T08:02:05Z"
```

**感知结果**：命中事件 1（`error`），决策 `find_user`，`reason` 为 `"Detected error level event: Disk I/O failure on /dev/sda1"`。事件 3、4 不触发决策。

---

#### 使用 `@defaults` 补全字段

上报方无需在每行重复填写固定字段：

```
@schema[id:int, level:str, message:str, source:str]
@defaults{source:"payment-service"}
logs(3):
  1, "warn",  "Queue backlog exceeded threshold: 1200 items"
  2, "error", "Transaction rollback: insufficient balance"
  3, "info",  "Scheduled reconciliation completed"
```

> `source` 字段在数据行中省略时，自动填充为 `"payment-service"`。  
> 感知器命中事件 1（`warn`）后立即返回，不再处理事件 2。

---

## TOON 格式

TOON（Tabular Object Notation）是一种轻量级表格式文本格式，无类型注解，适用于字符串型日志的快速上报。

### 语法结构

```
容器名[N]{字段1,字段2,...}:
  值1,值2,...
  值1,值2,...
```

**识别规则**：文本中同时含有 `[`、`{`、`}:` 三个模式。

### 组成元素

#### 表头行

格式为 `容器名[N]{字段列表}:`，三部分连写，末尾必须有冒号。

```
events[3]{id,level,message}:
```

| 部分 | 说明 |
|------|------|
| `容器名` | 事件集合名称，同 ATON 容器名规范 |
| `[N]` | 数据行数量，`N` 为整数 |
| `{字段1,字段2,...}` | 字段名列表，逗号分隔，无空格 |
| `:` | 表头结束符，必填 |

#### 数据行

- 缩进两个空格
- 逗号 `,` 分隔字段值
- 所有值均为字符串类型，**无需引号**
- 若字段值本身含逗号，需由上层编码处理

**与 ATON 的主要差异**：

| 特性 | ATON | TOON |
|------|:----:|:----:|
| 类型声明 | ✅ | ✗ |
| 默认值（`@defaults`） | ✅ | ✗ |
| 字符串引号 | 建议加 | 无需加 |
| 语法复杂度 | 较高 | 较低 |

### TOON 示例

#### 最小上报

```
events[2]{id,level,message}:
  1,error,Connection refused to 10.0.0.5:5432
  2,info,Service started successfully
```

**感知结果**：命中事件 1（`error`），决策 `find_user`。

---

#### 完整上报

```
events[4]{id,level,message,source,timestamp}:
  1,error,Out of memory: kill process 1234,kernel,2026-02-28T08:00:00Z
  2,warn,Slow query detected: 4200ms,db,2026-02-28T08:01:10Z
  3,info,Deployment completed,deploy,2026-02-28T08:02:00Z
  4,debug,GC pause 120ms,jvm,2026-02-28T08:02:05Z
```

**感知结果**：命中事件 1（`error`），决策 `find_user`。

---

#### 多容器块

单次上报可包含多个容器块。感知器按 `events` → `logs` → `records` → `data` → `items` 顺序查找第一个可用容器：

```
meta[1]{env,version}:
  production,v2.3.1

logs[2]{id,level,message}:
  1,warn,Retry attempt 3 of 5
  2,info,Request completed in 230ms
```

> 本例中 `meta` 不在优先键名列表内，感知器取 `logs` 作为事件容器。  
> 命中事件 1（`warn`），决策 `find_user`。

---

## Webhook JSON 封装

通过 Webhook 推送时，将日志内容包装在 JSON payload 中。感知器支持两种传入方式。

### 方式一：传入原始文本

感知器自动检测并解析文本格式：

```json
{
  "log": "events[2]{id,level,message}:\n  1,error,Connection refused\n  2,info,OK",
  "source": "my-service",
  "timestamp": "2026-02-28T10:00:00Z"
}
```

payload 字段解释：

| 字段 | 必填 | 说明 |
|------|:----:|------|
| `log` | ✅ | ATON 或 TOON 格式文本（与 `raw` 二选一） |
| `raw` | — | 同 `log`，备用字段名 |
| `source` | 可选 | 上报来源标识，不参与决策 |
| `timestamp` | 可选 | 上报时间，不参与决策 |

### 方式二：传入已解析结构

跳过解析步骤，直接传入符合[事件字段规范](./日志上报规范-总览.md#事件字段规范)的结构化数据：

```json
{
  "data": {
    "events": [
      {"id": 1, "level": "error", "message": "Connection refused"},
      {"id": 2, "level": "info",  "message": "OK"}
    ]
  }
}
```

> 使用 `data` 字段时，值须为包含事件列表的 dict 或直接为事件 list。感知器检测到 `data` 为 dict 时跳过解析，直接进入感知流程。

---

## 格式对比与选型

| 场景 | 推荐格式 | 理由 |
|------|---------|------|
| 字段含 `int` / `float` / `bool` 类型 | ATON | 支持类型声明，解析后保留原生类型 |
| 纯字符串日志，追求语法简洁 | TOON | 无需引号，表头即文档，可读性强 |
| 跨服务 HTTP 推送 | Webhook JSON | 原生结构化，无格式转换成本 |
| Agent 工具链内部传递 | 已解析 `dict` | 省去 `parse_log` 步骤，直接调用 `perceive` |
| 日志文件轮询（混合来源） | ATON 或 TOON | 搭配 `filter_rules.level` 预过滤，降低处理量 |
