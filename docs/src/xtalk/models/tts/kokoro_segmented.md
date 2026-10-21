# Segmented Kokoro client

## Purpose and types

KokoroSegmented implements TTS/StreamingTextTTS and serially synthesizes actual text increments. Defaults are max_wait_ms=300 for the first segment and independent continuation_wait_ms=1200 for later segments, with 12/160 character thresholds. clone preserves both deadlines. The user accepted a small naturalness tradeoff against 600ms and selected the current defaults.

## Core methods

_take selects a segment at a sentence boundary, size limit, deadline, or finish while retaining each remaining character's arrival time. Expired text uses complete-word boundaries; unfinished words await more input or finish. A 160-character hard limit bounds unusually long words. The deadline measures aggregation; unfinished words and first audible speech can exceed 300ms.

_produce validates generation/sequence and PCM format, records aggregation/request/compute time and raw/delivered duration, then sends 40ms packets through the existing TTSManager. bind_response adds diagnostic session/response identity. trim_segment_padding finds outer activity with 10ms RMS at -60dBFS, retains 30ms leading guards and 30/80/150ms trailing guards by punctuation, and preserves interior samples and pauses. Silent segments remain auditable.

start/clone isolate generations; append backlog is limited to 8192 characters, timeline to 4096 events, and the audio queue to 50 packets. flush closes text input and stop drains audio. cancel invalidates old PCM and clears transport/queues; underlying GPU computation may continue. Playback ownership remains unchanged.
