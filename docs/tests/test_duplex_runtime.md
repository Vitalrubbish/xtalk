# test_duplex_runtime.py

## Purpose, classes, and core methods

WireMicroTurnParser and DuplexRuntimeTests cover arbitrary marker splits, control semantics, continuation, token-budget termination, first-text clock start, silence, deltas, final deduplication, slow inference, rewrites, heard facts on interruption, errors, shutdown cancellation, stale-version rejection, native TTS/playback settlement and the single service control path. Uses a real EventBus and deterministic model service.

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_runtime -v
~~~

A split interruption test confirms the marker stops playback, closes the model stream and completes the micro-turn immediately while EOS remains unavailable. It also checks that the protocol observation keeps the raw marker while prompt history receives the required ChatML closure.

Adds user backchannel plus same-micro-turn continuation, including fragmented markers and one response/TTS stream. Waiting controls still reject missing EOS during an active answer.
