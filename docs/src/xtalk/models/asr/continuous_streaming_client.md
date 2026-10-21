# ContinuousStreamingASRClient

The HTTP adapter forwards 80 ms PCM chunks and returns online text directly. Pause hints preserve the decoder; finish_stream closes input and drains the online tail. Clone, reset and close manage independent sessions. No revision filter is applied.

At each micro-turn, `recognize_stream(b"", is_final=False)` reads `GET /v1/session/{id}/result` without submitting audio. Before allocation it returns empty text without creating a session. Input, reads and reset/close share a thread lock so cancelled executor calls cannot race session deletion. There is no independent polling clock.
