# Service Configuration

`service_config` is the optional top-level config object passed into `DefaultService`.
It is shared with all session-scoped managers and gateways.

Example:

```json
{
  "service_config": {
    "enable_persistence": true,
    "recording": true,
    "send_full_audio_to_client": false,
    "data_dir": "data"
  }
}
```

## Reference

| Key | Type | Default | Used by | Effect |
| --- | --- | --- | --- | --- |
| `enable_persistence` | `bool` | `true` | `Xtalk`, `ServiceManager`, `PersistenceManager` | Enables session history persistence in `<data_dir>/chat_history.sqlite3` together with session listing and restoration. When disabled, the built-in auth and websocket attach flow still work, but chat history is kept in memory only for the current live connection. |
| `data_dir` | `str` | `"data"` | `Service`, `EmbeddingsManager` | Root directory for session-scoped embedding data. Embeddings are persisted under `<data_dir>/sessions/<session_id>/embeddings` and the session directory is removed on shutdown. |
| `recording` | `bool` | `false` | `RecordingManager` | Enables session recording to a stereo WAV file. Left channel is raw user audio, right channel is played TTS audio. Default output path is `logs/session_audio/<timestamp>.wav`. |
| `send_full_audio_to_client` | `bool` | `false` | `RecordingManager`, `OutputGateway`, frontend | Sends assembled full-conversation stereo PCM chunks to the client as `full_audio_frame` messages. The payload is 48 kHz, 16-bit, 2-channel PCM encoded as base64. |
