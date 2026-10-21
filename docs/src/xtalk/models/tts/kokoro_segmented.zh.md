# Kokoro文本分段客户端

## 功能与类

KokoroSegmented实现TTS/StreamingTextTTS接口，接收真实增量文本并串行提交Kokoro。默认首段max_wait_ms=300、后续独立continuation_wait_ms=1200，最小12/最大160字符；clone保留这两个独立期限。用户已接受300ms自然度略逊600ms但整体差异不大，选择当前默认路线。

## 核心方法

_take在句界、长度上限、期限或finish时取段，保留剩余字符的实际到达计时；超时优先完整词，残词等后续增量或finish，异常长词仍受160字符硬限。期限表示聚合等待，不能保证残词或首可听在300ms内完成。

_produce校验generation/sequence及PCM格式，按段记录聚合/请求/计算耗时和原始/交付时长，再切40ms包交既有TTSManager。bind_response仅绑定session/response诊断身份。trim_segment_padding以10ms RMS、-60dBFS定位首尾活动区，前保留30ms、后按句读保留30/80/150ms；原段内部样本与停顿保留，全静音段保持可审计。

start/clone隔离代际，append积压限制8192字符；timeline最多4096事件、音频队列最多50包。flush结束文本、stop排空；cancel失效旧代际并清理队列和传输，底层GPU计算可能继续。唯一播放所有权不变。
