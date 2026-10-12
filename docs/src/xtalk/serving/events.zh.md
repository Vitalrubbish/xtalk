# events.py

## 功能、类与核心方法

扩展全局事件 dataclass。Event 同时记录墙上时间和进程单调时间。A1 为 ASR、LLM、TTS 请求、交付和已播事件补充 request、response、turn、segment、prefix、state 和 reason 字段，并新增 DuplexProtocolParsed 与 DuplexProtocolError。字段保持兼容，实际传递由 manager 负责。

## 类设计与事实边界

Event.__post_init__ 初始化两类时间，event_type 返回 TYPE，create_event_class 创建兼容事件子类。ASRResultPartial/Final 表示输入前缀；LLMAgentResponseUpdate/Finish 表示生成文本；TTSStarted 是客户端交付门打开；ResponseUpdate/Finish 是确认已播文本。DuplexProtocolParsed/Error 表示协议观测，不发出播放或语义动作。所有新增字段提供默认值供原生发布者兼容使用。

## A2/A3 更新

新增 DuplexMicroTurnReady 事件，保留不可变输入窗口的 prefix/turn/segment/request、delta 和修订信息。
