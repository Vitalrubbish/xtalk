# ASRManager 连续流扩展

`AudioConsumer.pause` 对 continuous_audio 实现保持消费，不关闭流或释放尾部；其他 ASR 保留原逻辑。`end` 对连续流调用 async_finish_stream 再发布 final，保证结束与声学暂停不同。shutdown 在线程中 reset，释放服务会话，避免下一样本冲突。音频队列、事件总线及会话重置仍由原 manager 管理。
