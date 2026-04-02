# 配置服务

## 自定义模型

如前文在 [启动服务](start_the_service.zh.md) 中所述，X-Talk 实例可以通过 JSON 配置创建，该配置用于自定义所使用的模型。

对于模型配置，配置内容应与模型 Python 类名及其初始化参数一致。

> 查看支持的模型：
> ```python
> from xtalk import Xtalk
> print(Xtalk.MODEL_REGISTRY)
> # 类似这样
> #{
> #     "asr": ["xtalk.speech.asr"],
> #     "llm_agent": ["xtalk.llm_agent"],
> #     "tts": ["xtalk.speech.tts"],
> #     "embeddings": ["xtalk.embeddings"],
> #  "speaker_encoder": ["xtalk.speech.speaker_encoder"],
> #     "captioner": ["xtalk.speech.captioner"],
> #     "caption_rewriter": ["xtalk.rewriter"],
> #     "thought_rewriter": ["xtalk.rewriter"],
> #     "vad": ["xtalk.speech.vad"],
> #     "speech_enhancer": ["xtalk.speech.speech_enhancer"],
> #     "speech_speed_controller": ["xtalk.speech.speech_speed_controller"],
> #     "turn_detector": ["xtalk.speech.turn_detector"],
> # }
> ```

例如，`DefaultAgent` 的定义位于 `src/xtalk/llm_agent/default.py`：
```python
class DefaultAgent(Agent):
    def __init__(
            self,
            model: BaseChatModel | dict,
            system_prompt: str = _BASE_PROMPT,
            voice_names: Optional[List[str]] = None,
            emotions: Optional[List[str]] = None,
            tools: Optional[List[Union[BaseTool, Callable[[], BaseTool]]]] = None,
        ):
    ...
```

为了与初始化参数匹配，配置项应写成这样：
```
"llm_agent": {
    "type": "DefaultAgent",
    "params": {
      "model": {
        "api_key": "none",
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "cpatonn/Qwen3-30B-A3B-Instruct-2507-AWQ-4bit"
      },
      "voice_names": [
        "Man",
        "Woman",
        "Child"
      ],
      "emotions": [
        "happy",
        "angry",
        "sad",
        "fear",
        "disgust",
        "depressed",
        "surprised",
        "calm",
        "normal"
      ]
    }
  },
```

像 `voice_names`、`emotions` 和 `tools`（目前尚不支持在配置中使用）这样的可选键可以省略。

完整的模型类型、对应的可选依赖以及其在源码中的适配位置，请参阅[支持的模型](../docs/supported_models.zh.md)。
> **Note**
> 大多数模型实现都是客户端适配器。您可能还需要按照相应说明启动模型实例本身。

## 自定义服务行为

此外，您还可以通过以下配置自定义服务行为，例如是否将会话音频保存到 `logs/` 下、是否将会话音频发送到客户端：
```json
    "service_config": {
        "recording": true,
        "send_full_audio_to_client": true
    }
```

完整的服务配置项列表，请参阅[所有服务配置](../docs/service_config.zh.md)。
