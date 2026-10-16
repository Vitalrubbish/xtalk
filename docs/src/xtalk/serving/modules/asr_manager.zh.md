# ASRManager 连续流扩展

`AudioConsumer.pause` 对 continuous_audio 实现保持消费，不关闭流或释放尾部；其他 ASR 保留原逻辑。`end` 对连续流调用 async_finish_stream 再发布 final，保证结束与声学暂停不同。shutdown 在线程中 reset，释放服务会话，避免下一样本冲突。音频队列、事件总线及会话重置仍由原 manager 管理。

F1：`ASRManager` 响应 `TurnASRReadRequested`，调用 `AudioConsumer.read_latest`。仅连续流在活动期间读取已有结果；空音频读取与音频提交共享识别锁，结果发布完成后才返回，因此同拍快照已包含新文本。队列中不足一块的音频保留，不因读取而提交或丢弃。abort/shutdown 使旧结果失效，reset 在线程中等待在途 HTTP 完成；没有新增接收任务或时钟，非连续 ASR 不增加读取。
