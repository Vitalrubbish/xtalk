# Kokoro 文本分段客户端

`KokoroSegmented` 同时实现 TTS 与 StreamingTextTTS，将真实增量按最少 12 字符、最多 160 字符、250ms 聚合等待分段。`_take` 优先完整词和句界、保护小数点；过期残段可以短于最小长度，超长单词按上限切分并保留全文。等待从首字符开始，合成/排队时间另记。`_produce` 串行提交，校验 generation、sequence 与格式，再按 40ms 分包。

start 创建独立代际，append_text 有 8192 字符积压上限；flush 表示输入完成并拒绝后续 append，stop 排空已 flush 输入；cancel 立即失效代际、丢弃队列、取消请求并释放传输。底层服务计算可能继续，不能宣称立即释放 GPU。audio_stream 唯一交付给现有 TTSManager，PCM 为 48kHz mono PCM16。clone 不共享任何响应状态，标准 synthesize 使用独立客户端。timeline 保存分段等待、PCM 和取消时间，最多 4096 事件。audio_queue 最多 50 个 40ms 块。


真实增量分段修复：按字符区间保留每次append的实际到达时间，取走一段后以剩余首字符真实到达时刻计时；超时允许短于12字符的完整词，避免残词继承旧计时立即被切开。新增please/con/firm增量回归；没有后续字符且等待耗尽时仍强制当前残段并保留时间线。
