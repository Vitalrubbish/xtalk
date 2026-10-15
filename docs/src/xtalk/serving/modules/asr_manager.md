# Continuous ASR lifecycle

AudioConsumer keeps continuous_audio adapters running across acoustic pauses. Actual end drains async_finish_stream before the final event; shutdown releases the remote session. Other adapters keep their existing pause and finalization behavior.
