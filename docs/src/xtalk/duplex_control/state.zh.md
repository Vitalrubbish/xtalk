# state.py

## 功能、类与核心方法

定义不可变 DuplexCorrelation 关联快照，保存 session、turn、segment、prefix、request 和 response 字段。A1 原样传递已存在的前缀版本；A2 的 PrefixSnapshot 与版本递增现已实现。

## 类设计

DuplexCorrelation 使用 frozen dataclass。session_id 必填；turn_id、segment_id、prefix_version 默认 None，request_id 与 response_id 默认空字符串。构造函数保存调用方提供的值，调用方负责 ID 分配与有效性检查。

## A2/A3 更新

新增 frozen PrefixSnapshot，保存当前和上次发送前缀、新增后缀、revision_kind、speech_state、原始接收时间与 request ID。版本由 assembler 维护，不依赖语义轮次判断。
