# timeline.py

## 功能、类与核心方法

定义 TimelineRecord 和 DuplexTimelineRecorder。记录器订阅 ASR、协议、生成、TTS、播放和已播结算事件，保存关联字段、原始输出、错误码、ASR 暂停标记（释放解码器扣住尾巴的片段边界）、事件时间、记录时间和 session 内序号到 JSONL。配置支持 duplex_timeline_dir 与 duplex_timeline_history。shutdown 取消订阅并可重复调用。记录器不猜测缺失 ID，也不保存音频字节。

## 方法与配置

TimelineRecord.from_event 从事件创建不可变快照，排除 stream、模型对象和音频载荷。DuplexTimelineRecorder._record_event 过滤 session、增加 sequence、追加 JSONL 并 flush；shutdown 取消订阅和关闭文件。

目录默认 data_dir/duplex_timeline，文件名为 session_id.jsonl。duplex_timeline_dir 可覆盖目录，duplex_timeline_history 默认 1000、下限 1，只限制内存记录。文件使用追加模式；重建记录器从 sequence=1 开始，分析时应区分记录器实例。monotonic_timestamp 是事件创建时间，recorded_monotonic 和 sequence 是处理顺序；嵌套事件可能先于外层事件写入。单调时间只在同一进程内比较。逐事件磁盘写入同步执行，其延迟和长会话开销需要远端验证。

## 双工更新

新增订阅 DuplexMicroTurnReady，把输入窗口及其 ID 纳入同一时间线。
