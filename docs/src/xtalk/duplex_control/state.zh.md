# state.py

## 功能、类与核心方法

定义不可变 DuplexCorrelation 关联快照，保存 session、turn、segment、prefix、request 和 response 字段。A1 原样传递已存在的前缀版本；PrefixSnapshot 和版本递增属于 A2。

## 类设计

DuplexCorrelation 使用 frozen dataclass。session_id 必填；turn_id、segment_id、prefix_version 默认 None，request_id 与 response_id 默认空字符串。构造函数保存调用方提供的值，调用方负责 ID 分配与有效性检查。
