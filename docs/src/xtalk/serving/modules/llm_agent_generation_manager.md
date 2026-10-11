# llm_agent_generation_manager.py

## Purpose, classes, and core methods

Each asynchronous stream stores independent response state and correlation. The first text uses a reserved response_id or a new ID; first chunk, generated updates, TTS requests, flush, and finish share request, turn, segment, and prefix. Completion copies metadata before cleanup to prevent cross-response leakage. Stop retains session-wide and persistent-stream behavior.

## State and core methods

_ResponseOutputState contains accumulated text, response_id, first-chunk/TTS flags, and correlation per stream. _handle_generation_request binds the source; _consume_stream_item publishes first chunk, updates, and TTS start/append. _finish_response_locked copies completion state before reset and flush/finish. _wait_for_pre_tool_playback_locked retains the played-settlement barrier. shutdown cancels stream/tool tasks. Persistent-stream metadata describes its creation source; later micro-turn correlation updates belong to A3.
