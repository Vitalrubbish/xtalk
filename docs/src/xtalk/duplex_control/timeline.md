# timeline.py

## Purpose, classes, and core methods

Defines TimelineRecord and DuplexTimelineRecorder. The recorder observes ASR, protocol, generation, TTS, playback, and played-text settlement events, writing correlation, raw output, error codes, the ASR pause flag (the segment boundary that releases the decoder's held-back tail), event and recording timestamps, and a session sequence to JSONL. Configuration supports duplex_timeline_dir and duplex_timeline_history. shutdown unsubscribes idempotently. Missing IDs are never inferred and audio bytes are excluded.

## Methods and configuration

TimelineRecord.from_event creates an immutable snapshot excluding streams, models, and audio payloads. DuplexTimelineRecorder._record_event filters sessions, increments sequence, appends JSONL, and flushes. shutdown unsubscribes and closes the file.

The default directory is data_dir/duplex_timeline with a session_id.jsonl file. duplex_timeline_dir overrides the directory. duplex_timeline_history defaults to 1000 with a minimum of 1 and bounds memory only. Files append; a new recorder starts sequence at 1, so analysis must distinguish recorder instances. monotonic_timestamp is event creation time; recorded_monotonic and sequence describe handling order. Nested events may be recorded before outer events. Compare monotonic timestamps only within one process. Disk writes are synchronous and require remote latency and long-session validation.

## A2/A3 update

Subscribes to DuplexMicroTurnReady and records input windows and their identifiers on the same timeline.
