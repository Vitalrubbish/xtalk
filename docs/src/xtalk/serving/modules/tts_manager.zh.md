# tts_manager.py

## 功能、类与核心方法

TTSManager 保存准备阶段的关联快照，只有交付请求到达才发布 TTSStarted。A1 将关联字段带入首句、TTSStarted、TTSChunkReady、TTSFinished 和停止事件；reset_tts 清理旧字段，防止下一响应继承来源。音频队列和背压逻辑保持原样。

## 核心方法

_handle_turn_tts_start 保存准备响应；_handle_delivery_start 打开交付门；_correlation_kwargs 返回关联字段副本；_handle_turn_tts_append/flush 推送和结束文本；_handle_turn_tts_stop 在 reset 前保存关联并使用停止请求的 reason；reset_tts 清理任务、队列与字段。regular 与 StreamingTextTTS 继续共用交付链。
