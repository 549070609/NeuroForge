# ATON 与 TOON 格式介绍

**文档类型**：格式背景 · 概念说明  
**相关文档**：[日志上报规范 · 总览](./日志上报规范-总览.md) · [日志上报规范 · ATON 与 TOON 格式详解](./日志上报规范-ATON与TOON格式详解.md)

---

## 目录

- [背景：为什么需要新格式](#背景为什么需要新格式)
- [ATON](#aton)
  - [设计目标](#设计目标)
  - [核心语法](#aton-核心语法)
  - [类型系统](#类型系统)
  - [高级特性](#高级特性)
- [TOON](#toon)
  - [设计目标](#设计目标-1)
  - [核心语法](#toon-核心语法)
  - [引号规则](#引号规则)
- [ATON 与 TOON 对比](#aton-与-toon-对比)
- [与 JSON 的对比](#与-json-的对比)
- [在 NeuroForge 中的使用](#在-neuroforge-中的使用)
- [参考资料](#参考资料)

---

## 背景：为什么需要新格式

JSON 是目前最通用的数据交换格式，但在 AI / LLM 应用场景下存在明显缺陷：

- **冗余 token 多**：每个对象都要重复写 key，数组中 100 条记录就有 100 次 key 重复
- **上下文窗口浪费**：LLM 按 token 计费，格式冗余直接转化为成本和延迟
- **无原生类型声明**：JSON 的类型需要靠 schema 文件额外约定，不能内联表达

ATON 和 TOON 均是为解决上述问题而设计的**面向 LLM 的紧凑型文本序列化格式**，都以 JSON 数据模型为基础，但大幅减少了结构噪声。

---

## ATON

**全称**：Adaptive Token-Oriented Notation（自适应令牌导向记法）  
**版本**：v2.0.1（2025 年 11 月）  
**作者**：Stefano D'Agostino  
**安装**：`pip install aton-format`（Python）· `npm install aton-format`（JS/TS）  
**开源协议**：MIT

### 设计目标

ATON 的核心设计目标是在保持与 JSON 完全等价的前提下，通过以下机制最大化压缩 token：

- **消除 key 重复**：同类记录的字段名只声明一次（`@schema`）
- **内联类型系统**：字段类型随 schema 一同声明，无需外部 schema 文件
- **默认值提取**：相同的字段值用 `@defaults` 统一声明，数据行无需重复填写
- **原生关系表达**：支持实体间引用（`→` 语法），适用于图结构数据

实测结果：在电商、医疗、服务器日志等数据集上，与 JSON 相比平均减少 **56%** 的 token，LLM 解析准确率 **96.3%**（JSON 为 96.8%），几乎无损。

### ATON 核心语法

#### 基本结构

```
@schema[字段名:类型, 字段名:类型, ...]
[@defaults{字段名:"默认值", ...}]

实体名(记录数):
  值1, 值2, 值3
  值1, 值2, 值3
```

#### JSON 对比示例

**JSON**（原始形式，67 token）：

```json
{
  "users": [
    {"id": 1, "name": "Alice", "role": "admin"},
    {"id": 2, "name": "Bob",   "role": "user"},
    {"id": 3, "name": "Carol", "role": "user"}
  ]
}
```

**ATON**（等价形式，~29 token）：

```
@schema[id:int, name:str, role:str]
@defaults{role:"user"}

users(3):
  1, "Alice", "admin"
  2, "Bob"
  3, "Carol"
```

> `role` 字段在 `@defaults` 中声明默认值 `"user"`，Bob 和 Carol 的数据行无需重复填写。

### 类型系统

ATON 在 `@schema` 中内联声明字段类型，解码后自动转换为对应原生类型：

| 类型标识 | 说明 | 示例值 |
|---------|------|--------|
| `str` | 字符串 | `"hello"` |
| `int` | 整数 | `42` |
| `float` | 浮点数 | `3.14` |
| `bool` | 布尔值 | `true` · `false` |
| `arr` | 数组 | `[1,2,3]` |
| `obj` | 对象 | `{key:val}` |
| `datetime` | ISO 8601 时间戳 | `2025-11-18T10:30Z` |
| `ref` | 实体引用 | `-entity[id]` |

### 高级特性

#### `@defaults` — 默认值声明

对所有记录共享的字段值提取为默认值，数据行中省略该字段时自动补全：

```
@schema[id:int, level:str, source:str, env:str]
@defaults{env:"production", source:"backend"}

events(3):
  1, "error", _, _          ← source 和 env 使用默认值
  2, "warn",  "frontend"    ← 仅 source 覆盖，env 仍用默认值
  3, "info",  _, "staging"  ← 仅 env 覆盖
```

#### 原生关系（Native Relationships）

使用 `-实体名[id]` 语法声明实体引用，支持表达关联数据和图结构：

```
@schema[id:str, name:str, manager:ref]

employees(3):
  "E001", "Alice", null
  "E002", "Bob",   -employees["E001"]
  "E003", "Carol", -employees["E001"]
```

#### 压缩模式（V2）

| 模式 | 处理速度 | 压缩率 | 适用场景 |
|------|---------|--------|---------|
| `FAST` | ~50K 条/秒 | 40–45% | 实时 API、低延迟 |
| `BALANCED` | ~30K 条/秒 | 50–55% | 通用（默认） |
| `ULTRA` | ~10K 条/秒 | 55–60% | 批处理、存储 |
| `ADAPTIVE` | 自动 | 最优 | 混合负载 |

---

## TOON

**全称**：Token-Oriented Object Notation（令牌导向对象记法）  
**版本**：v3.0（2025 年 11 月 24 日，稳定工作草案）  
**规范维护**：[github.com/toon-format/spec](https://github.com/toon-format/spec)（含完整 ABNF 语法 + 358 个测试夹具）  
**安装**：`pip install toon-formatter`（Python）· `npm install @toon-format/toon`（JS/TS）

### 设计目标

TOON 以 JSON 的数据模型（对象、数组、基础类型）为基础，将 YAML 风格的缩进结构与 CSV 风格的表格布局结合，提供了一种**无需类型注解、语法极简**的紧凑格式。

实测结果：与 JSON 相比平均减少 **39.6%** 的 token，LLM 测试准确率 73.9%（JSON 为 69.7%）。

### TOON 核心语法

#### 对象

以 `key: value` 形式表示，缩进替代花括号：

```
id: 123
name: Ada
active: true
```

等价 JSON：`{"id": 123, "name": "Ada", "active": true}`

#### 基础类型数组（内联）

```
tags[3]: admin,ops,dev
```

等价 JSON：`{"tags": ["admin", "ops", "dev"]}`

#### 对象数组（表格形式）—— 最常用于日志上报

当数组内所有对象拥有相同字段集时，使用表头 + 数据行的表格布局，**这是 TOON 最核心的语法特性**：
 
```
items[2]{id,qty,price}:
  1,5,9.99
  2,3,14.50
```

等价 JSON：

```json
{
  "items": [
    {"id": "1", "qty": "5", "price": "9.99"},
    {"id": "2", "qty": "3", "price": "14.50"}
  ]
}
```

> **注意**：TOON 无类型声明，所有值解码后均为字符串（或自动推断为 number / boolean / null）。

#### 嵌套对象

```
user:
  id: 123
  name: Ada
  address:
    city: Beijing
    zip: "100000"
```

#### 混合 / 非均匀数组

当数组内各元素结构不同，使用列表标记 `-`：

```
items[3]:
  - 1
  - name: Alice
  - text
```

#### 分隔符选项

表头中可声明非默认分隔符，用于 value 中含逗号的场景：

| 分隔符 | 声明方式 | 示例头 |
|--------|---------|--------|
| 逗号（默认） | 不声明 | `items[2]{id,name}:` |
| Tab | `[\t]` | `items[2\t]{id\tname}:` |
| 管道符 | `[\|]` | `items[2\|]{id\|name}:` |

#### Key Folding（可选）

将多层单字段嵌套折叠为点分路径，进一步节省 token：

```
# 标准写法
data:
  metadata:
    count: 42

# Key Folding 后
data.metadata.count: 42
```

### 引号规则

TOON 只在**必要时**加引号（最大化 token 效率）。以下情况须加引号：

- 值看起来像数字（如 `"42"`、`"3.14"`）
- 值为 `true`、`false`、`null`（区分大小写）
- 值包含分隔符、冒号、引号、反斜杠、方括号/花括号
- 值有前导或尾随空格
- 值为空字符串 `""`

其余情况可不加引号，包括 Unicode 字符和内部空格：

```
message: Hello 世界 👋
note: This has inner spaces
```

---

## ATON 与 TOON 对比

| 维度 | ATON | TOON |
|------|:----:|:----:|
| **全称** | Adaptive Token-Oriented Notation | Token-Oriented Object Notation |
| **规范版本** | v2.0.1（2025-11） | v3.0（2025-11-24） |
| **token 压缩率** | ~56%（vs JSON） | ~40%（vs JSON） |
| **类型声明** | ✅ `@schema` 内联声明 | ✗ 无（自动推断） |
| **默认值支持** | ✅ `@defaults` | ✗ |
| **原生关系** | ✅ `-entity[id]` 引用 | ✗ |
| **对象表格语法** | `entity(N):` + 缩进数据行 | `key[N]{fields}:` + 缩进数据行 |
| **字符串引号** | 建议加（明确类型边界） | 按需加（最小化） |
| **数据模型** | ATON 自有数据模型 | 与 JSON 完全对齐 |
| **嵌套结构** | ✅ | ✅ |
| **适合场景** | 有类型要求、需要关系图 | 纯字符串日志、追求极简语法 |

---

## 与 JSON 的对比

以一组服务器日志（4 条事件）为例直观对比三种格式：

**JSON**：

```json
{
  "events": [
    {"id": 1, "level": "error",   "message": "DB timeout",      "source": "backend"},
    {"id": 2, "level": "warn",    "message": "High memory",      "source": "backend"},
    {"id": 3, "level": "info",    "message": "Deploy complete",  "source": "deploy"},
    {"id": 4, "level": "debug",   "message": "Cache ratio 0.97", "source": "cache"}
  ]
}
```

**ATON**（相同数据，~56% token 压缩）：

```
@schema[id:int, level:str, message:str, source:str]
@defaults{source:"backend"}

events(4):
  1, "error", "DB timeout"
  2, "warn",  "High memory"
  3, "info",  "Deploy complete",  "deploy"
  4, "debug", "Cache ratio 0.97", "cache"
```

**TOON**（相同数据，~40% token 压缩）：

```
events[4]{id,level,message,source}:
  1,error,DB timeout,backend
  2,warn,High memory,backend
  3,info,Deploy complete,deploy
  4,debug,Cache ratio 0.97,cache
```

三种格式解码后均可得到完全相同的 Python/JSON 数据结构。

---

## 在 NeuroForge 中的使用

主动感知插件（`main/perception`）使用 ATON 和 TOON 作为日志上报的标准格式：

```
上报方（服务 / Agent）
    │
    ├─ 文件轮询 ──→ ATON / TOON 文本文件
    ├─ Webhook  ──→ JSON payload（内含 ATON/TOON 文本 或 已解析结构）
    └─ EventBus ──→ log.written 事件（payload.log 或 payload.data）
                         │
                    detector.py
                    检测格式（ATON / TOON / JSON）
                         │
                    parser.py
                    解析为 Python dict/list
                         │
                    perception.py
                    感知 → 决策（find_user / execute / call_agent）
```

感知插件通过 `aton-format` 和 `toon-formatter` 两个库完成解析，格式识别和处理对上报方完全透明。上报方只需按格式规范写入日志，感知器自动完成后续流程。

---

## 参考资料

| 资源 | 地址 |
|------|------|
| ATON 官方白皮书 | https://www.atonformat.com/whitepaper.html |
| ATON GitHub | https://github.com/dagoSte/aton-format |
| ATON PyPI | `pip install aton-format` |
| TOON 官方文档 | https://toonformat.dev |
| TOON 规范（ABNF + 测试） | https://github.com/toon-format/spec |
| TOON 语法速查 | https://toonformat.dev/reference/syntax-cheatsheet.html |
| TOON PyPI | `pip install toon-formatter` |
