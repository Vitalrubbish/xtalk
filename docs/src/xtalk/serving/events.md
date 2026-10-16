# events.py

## Purpose, classes, and core methods

Extends the global event dataclasses. Event records wall-clock and process-monotonic timestamps. A1 adds request, response, turn, segment, prefix, state, and reason fields to ASR, LLM, TTS request, delivery, and played-text events, and adds DuplexProtocolParsed and DuplexProtocolError. Fields remain compatible; managers propagate them.

## Class design and fact boundaries

Event.__post_init__ initializes both clocks, event_type returns TYPE, and create_event_class creates compatible subclasses. ASRResultPartial/Final represent input prefixes; LLMAgentResponseUpdate/Finish represent generated text; TTSStarted opens client delivery; ResponseUpdate/Finish represent confirmed played text. DuplexProtocolParsed/Error are protocol observations without playback or semantic actions. New fields provide defaults for native publishers.

## A2/A3 update

Adds DuplexMicroTurnReady carrying immutable prefix/turn/segment/request identity, delta and revision metadata.

`TurnASRReadRequested` reads existing ASR output before the current snapshot. It submits no audio and does not pause or end input. Awaited dispatch ensures the prefix update completes before the snapshot.
