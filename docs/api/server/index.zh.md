# 服务端 API

本节用于展示 `xtalk.serving` 的内部 Python 参考文档。

该目录下的页面由 `mkdocs-autoapi` 自动从源码生成，并由
`mkdocstrings` 渲染。若需完善这部分文档，应直接更新
`src/xtalk/serving/` 中的 Python docstring。

## `examples/sample_app` 使用到的模块

`examples/sample_app` 下的示例会直接使用以下 Xtalk 模块：

- `xtalk`：
  示例直接使用的顶层导出，包括 `Xtalk`、`DefaultPipeline`、
  `DefaultService`、`create_event_class`、`Manager`、`EventBus` 和
  `Pipeline`。
- `xtalk.api`：
  `Xtalk` 的实现入口，示例通过它调用 `Xtalk.from_config()`、
  `Xtalk.create_pipeline_from_config()` 和
  `Xtalk.register_model_search_spec()`。
- `xtalk.pipelines` 和 `xtalk.pipelines.default`：
  提供 `Pipeline` 和 `DefaultPipeline`，用于自定义 pipeline 示例。
- `xtalk.serving`：
  自定义 service 示例使用到的服务层顶层导出，包括 `DefaultService`、
  `Manager`、`EventBus` 和 `create_event_class`。
- `xtalk.serving.module_types`：
  在重写服务行为时用到的内置 manager / gateway 类型，例如
  `OutputGateway`。
- `xtalk.events`：
  对 serving 事件的再导出，自定义 service 示例会使用其中的
  `LLMAgentResponseFinish` 等事件。
- `xtalk.model_types`：
  示例使用到的模型接口定义，包括 `Agent`、`ASR`、`TTS`、`Captioner`、
  `PuntRestorer`、`Rewriter`、`VAD`、`SpeechEnhancer`、
  `SpeakerEncoder`、`SpeechSpeedController` 和 `Embeddings`。
- `xtalk.log_utils`：
  示例通过 `mute_other_logging()` 使用的日志辅助模块。
