# Kokoro 分段及取消测试

`KokoroSegmentedTests` 启动真实 aiohttp 假合成服务。测试超时提交发生在 finish 前、真实增量拼接与日期时间保留、长度与序号、flush 后拒绝输入，以及阻塞请求取消后新响应只收到新 PCM。接口测试不代表真实 Kokoro 延迟或听感。使用 conda 和 PYTHONPATH=src 执行 unittest。


真实增量分段修复：按字符区间保留每次append的实际到达时间，取走一段后以剩余首字符真实到达时刻计时；超时允许短于12字符的完整词，避免残词继承旧计时立即被切开。新增please/con/firm增量回归；没有后续字符且等待耗尽时仍强制当前残段并保留时间线。
