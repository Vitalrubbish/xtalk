# turn_detector_manager.py

## Purpose, classes, and core methods

Moves the listening boundary from TTSChunkReady to TTSStarted. Generated audio no longer closes listening; delivery opening sets False, and playback completion or stop restores True. Only early stop reports assistant_interrupted while low-level audio reception continues.

## Core methods

_on_audio_frame/_on_asr_partial drives detection; _on_assistant_text forwards played facts; _on_tts_started sets listening=False. Completion and stop handlers restore listening; early stop also reports interruption. Listening=False selects interruption detection while audio input continues. Native semantic bypasses are handled when A3 integrates Duplex mode.
