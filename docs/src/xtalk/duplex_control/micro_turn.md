# micro_turn.py

## Purpose, classes, and core methods

MicroTurnAssembler stores cumulative and emitted prefixes and starts its clock after first nonblank text. _accept_asr updates prefix state/version; flush creates an immutable snapshot, sends the delta and awaits inference while reception continues. _clock follows the official serialized tick; shutdown cancels pending work. LLMAgentLoop starts continuous ASR; an acoustic VADSpeechEnd asks the ASR to finalize the current user segment (`TurnASRPauseRequested`, ASR state preserved) and VADSpeechStart resumes it, because this module replaces the released `TurnTakingManager`, the only other publisher of those boundaries.

## Usage and boundaries

Registered by the Boolean duplex_enabled service switch. Native mode keeps its configuration; official weights, long sessions, audio quality and FDB require remote conda acceptance.
