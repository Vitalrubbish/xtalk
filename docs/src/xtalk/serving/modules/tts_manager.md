# tts_manager.py

## Purpose, classes, and core methods

TTSManager snapshots correlation during preparation and publishes TTSStarted only after a delivery request. A1 carries metadata into first-sentence, TTSStarted, TTSChunkReady, TTSFinished, and stop events. reset_tts clears old fields so the next response cannot inherit them. Audio queues and backpressure remain unchanged.

## Core methods

_handle_turn_tts_start snapshots preparation; _handle_delivery_start opens delivery; _correlation_kwargs copies metadata; append/flush handlers feed and finish text. _handle_turn_tts_stop retains metadata before reset and uses the stop request reason. reset_tts clears tasks, queues, and identifiers. Regular and StreamingTextTTS retain the shared delivery chain.
