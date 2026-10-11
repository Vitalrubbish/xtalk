# tts_playback_manager.py

## Purpose, classes, and core methods

Maps confirmed playback progress to cumulative played text. A1 caches response correlation and carries it into ResponseUpdate, ResponseFinish, and TTSResponseClosed. TTSStarted opens playback tracking; early stops still settle from client acknowledgements and heard text cannot be withdrawn.

## Core methods

_cache_response_update/finish caches text and initial correlation. _activate_response starts tracking at TTSStarted. _emit_response_update publishes cumulative played prefixes; _commit_playback_text publishes final played text. _close_response snapshots correlation before cleanup and closure. shutdown cancels alignment and stop timeout tasks. Internal audio segments and alignment rules retain their behavior.
