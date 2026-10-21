# tts_manager.py

## Purpose and types

TTSManager snapshots correlation during response preparation and publishes TTSStarted after a delivery request. Request/response metadata accompanies first-sentence, audio-chunk, finish, and stop events. Regular and StreamingTextTTS share the existing delivery queue and backpressure with one playback owner.

## Core methods

_handle_turn_tts_start prepares a response. _start_streaming_tts calls Kokoro bind_response before startup to attach diagnostic session/response identity. _handle_delivery_start opens delivery. _correlation_kwargs copies metadata; append/flush handlers feed and close text. _handle_turn_tts_stop retains stop reason and identity before reset.

reset_tts clears tasks, queues, and old fields. Interruption/reset calls cancel; normal flush/stop drains audio. Kokoro cancellation immediately isolates old generations. Stopping underlying service computation remains a separate measurement.
