# Server API

This section hosts the internal Python reference for `xtalk.serving`.

The pages in this directory are generated automatically from the source tree by
`mkdocs-autoapi` and rendered with `mkdocstrings`. Update the Python
docstrings in `src/xtalk/serving/` to improve this documentation.

## Modules used by `examples/sample_app`

The sample applications under `examples/sample_app` directly use these Xtalk
modules:

- `xtalk`:
  top-level exports used by the examples, including `Xtalk`,
  `DefaultPipeline`, `DefaultService`, `create_event_class`, `Manager`,
  `EventBus`, and `Pipeline`.
- `xtalk.api`:
  implementation entry point for `Xtalk`, used by `Xtalk.from_config()`,
  `Xtalk.create_pipeline_from_config()`, and
  `Xtalk.register_model_search_spec()`.
- `xtalk.pipelines` and `xtalk.pipelines.default`:
  provide `Pipeline` and `DefaultPipeline`, used by the custom pipeline example.
- `xtalk.serving`:
  top-level serving exports used by the custom service example, including
  `DefaultService`, `Manager`, `EventBus`, and `create_event_class`.
- `xtalk.serving.module_types`:
  built-in manager and gateway classes used when rewiring service behavior, such
  as `OutputGateway`.
- `xtalk.events`:
  re-export of serving events used by the custom service example, such as
  `LLMAgentResponseFinish`.
- `xtalk.model_types`:
  model interfaces used by the examples, including `Agent`, `ASR`, `TTS`,
  `Captioner`, `PuntRestorer`, `Rewriter`, `VAD`, `SpeechEnhancer`,
  `SpeakerEncoder`, `SpeechSpeedController`, and `Embeddings`.
- `xtalk.log_utils`:
  logging helpers used by the examples via `mute_other_logging()`.
