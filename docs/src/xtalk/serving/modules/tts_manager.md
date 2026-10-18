# tts_manager.py

## Purpose, classes, and core methods

TTSManager snapshots correlation during preparation and publishes TTSStarted only after a delivery request. A1 carries metadata into first-sentence, TTSStarted, TTSChunkReady, TTSFinished, and stop events. reset_tts clears old fields so the next response cannot inherit them. Audio queues and backpressure remain unchanged.

## Core methods

_handle_turn_tts_start snapshots preparation; _handle_delivery_start opens delivery; _correlation_kwargs copies metadata; append/flush handlers feed and finish text. _handle_turn_tts_stop retains metadata before reset and uses the stop request reason. reset_tts clears tasks, queues, and identifiers. Regular and StreamingTextTTS retain the shared delivery chain.


2026-10-18：StreamingTextTTS 增加默认 cancel（兼容现有 stop）；TTSManager 的 reset/插话路径调用 cancel，正常 flush/stop 仍排空。Kokoro 重写 cancel 使旧代际 PCM 立即失效，取消不等待正常 finish。唯一播放队列及响应所有权保持不变。
