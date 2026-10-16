# Continuous ASR lifecycle

AudioConsumer keeps continuous_audio adapters running across acoustic pauses. Actual end drains async_finish_stream before the final event; shutdown releases the remote session. Other adapters keep their existing pause and finalization behavior.

`TurnASRReadRequested` invokes `AudioConsumer.read_latest` for active continuous streams. A recognition lock serializes input submission, empty-input reads and result publication; the prefix update completes before the micro-turn snapshot. Partial audio chunks remain queued. Abort/shutdown invalidate late results and reset waits for in-flight HTTP outside the event loop. No receiver task or polling clock is added; other ASR adapters are not read.
