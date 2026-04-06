# Service Configuration

`service_config` is the optional top-level config object passed into `DefaultService`.
It is shared with all session-scoped managers and gateways.

Example:

```json
{
  "service_config": {
    "recording": true,
    "send_full_audio_to_client": false,
    "data_dir": "data",
    "vad_sample_rate": 16000,
    "vad_frame_samples": 512,
    "vad_min_speech_ms": 250,
    "vad_redemption_ms": 500,
    "similarity_threshold": 0.4,
    "min_audio_length_sec": 0.5,
    "embedding_update_alpha": 0.05,
    "debug_log_dir": "logs/speaker_debug"
  }
}
```

## Reference

| Key | Type | Default | Used by | Effect |
| --- | --- | --- | --- | --- |
| `data_dir` | `str` | `"data"` | `Service`, `EmbeddingsManager` | Root directory for session-scoped embedding data. Embeddings are persisted under `<data_dir>/sessions/<session_id>/embeddings` and the session directory is removed on shutdown. |
| `recording` | `bool` | `false` | `RecordingManager` | Enables session recording to a stereo WAV file. Left channel is raw user audio, right channel is played TTS audio. Default output path is `logs/session_audio/<timestamp>.wav`. |
| `send_full_audio_to_client` | `bool` | `false` | `RecordingManager`, `OutputGateway`, frontend | Sends assembled full-conversation stereo PCM chunks to the client as `full_audio_frame` messages. The payload is 48 kHz, 16-bit, 2-channel PCM encoded as base64. |
| `vad_sample_rate` | `int` | `16000` | `VADManager` | Backend VAD sample rate used to compute frame timing. Only matters when a backend VAD model is configured in the pipeline. |
| `vad_frame_samples` | `int` | `512` | `VADManager` | Backend VAD frame size in samples. Together with `vad_sample_rate`, this determines frame duration. |
| `vad_min_speech_ms` | `int` | `250` | `VADManager` | Minimum accumulated speech duration before emitting `VADSpeechStart`. |
| `vad_redemption_ms` | `int` | `500` | `VADManager` | Required silence duration before emitting `VADSpeechEnd`. |
| `similarity_threshold` | `float` | `0.4` | `SpeakerManager` | Cosine similarity threshold for matching the current turn against an existing speaker profile. Below this threshold, a new speaker is registered. |
| `min_audio_length_sec` | `float` | `0.5` | `SpeakerManager` | Minimum buffered speech duration required before speaker identification runs for a turn. Shorter turns are reported as `too_short`. |
| `embedding_update_alpha` | `float` | `0.05` | `SpeakerManager` | Exponential moving average weight used when updating an already matched speaker embedding. |
| `debug_log_dir` | `str` | `"logs/speaker_debug"` | `SpeakerManager` | Intended output directory for speaker debug artifacts. In the current codebase, debug persistence is disabled, so changing this path has no visible effect unless that code is re-enabled. |

## Notes

- `service_config` keys are currently flat. There is no per-module namespacing yet.
- Unknown keys are ignored unless custom managers read them.
- `data_dir` is auto-filled to `"data"` by `Service` when omitted.
- `recording` and `send_full_audio_to_client` are independent. You can enable either one or both.

## Not In `service_config`

`recording_path` is not part of the static JSON `service_config`.
It is a per-session runtime option sent by the client as a WebSocket `session_config`
message and is consumed by `RecordingManager` when recording is enabled.
