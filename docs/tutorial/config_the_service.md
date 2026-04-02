# Configure the service

## Customize models

As mentioned [before](tutorial/start_the_service.md), X-Talk instance can be created from a JSON config, which customizes models used.
    
For model config, config should match model Python class name and init args. 

> Inspect models supported:
> ```python
> from xtalk import Xtalk
> print(Xtalk.MODEL_REGISTRY)
> # Something like
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

For example, the definition of `DefaultAgent` lies in `src/xtalk/llm_agent/default.py`:
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
    
In order to match with the init args, the config item should look like:
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

Optional keys like `voice_names`, `emotions` and `tools`(not supported in config yet) can be ignored.
    
See [supported models](docs/supported_models.md) for the full list of model types, their optional dependencies, and their adapting location in source code.
> **Note**
> Most model implementations are client-side adaptors. You may need to start the model instance following coresponding instructions.

## Customize service behavior

Also, you can customize service behavior (whether save session audio under `logs/`, whether send session audio to client...) through:
```json
    "service_config": {
        "recording": true,
        "send_full_audio_to_client": true
    }
```

See [all service config](docs/service_config.md) for full list of services cofiguration.