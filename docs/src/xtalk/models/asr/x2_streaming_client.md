# X2StreamingClient

The HTTP adapter forwards 80 ms PCM chunks and returns online text directly. Pause hints preserve the decoder; finish_stream closes input and drains the online tail. Clone, reset and close manage independent sessions. No revision filter is applied.
