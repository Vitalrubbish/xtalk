from ..interfaces import (
    TurnDetector,
    TurnDetectionAction,
    TurnDetectionResult,
    TurnDetectionSemantic,
)
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from typing import Optional
import asyncio


class LLMTurnDetector(TurnDetector):
    STOP_SPEAKING_PROMPT = """Classify the user's input. Output `backchannel` or `interrupt`. Apply the following rules in order:

If the user's input is a backchannel expression, such as “mm-hmm” or “okay,” or "嗯嗯" or "对对" then output `backchannel`. Backchannel can only be very short, and semantically meaningless.

If the user's input is semantically complete, or the intent is to interrupt someone else's response, then output `interrupt`.

"""
    START_GENERATION_PROMPT = """Classify the user's input. Output `finished` or `incomplete`. Apply the following rules in order:

If the user's input is semantically incomplete, as if they stopped halfway through speaking, for example ending with hesitation words or fillers, then output `incomplete`.

Otherwise output finished.

If you find the input abnormal, for example containing ASR misrecognized characters, also output finished.

"""

    def __init__(self, model: dict | BaseChatModel) -> None:
        super().__init__()
        if isinstance(model, dict):
            model = ChatOpenAI(**model)
        self._model = model
        # If AI is listening, try to determine whether to start generation and toggle state;
        # else determine whether to stop speaking and toggle state
        self._listening = True
        # FIXED: lock listening
        self._listening_lock = asyncio.Lock()
        self._incomplete_cache_text = ""

    def clone(self) -> "TurnDetector":
        return LLMTurnDetector(self._model)

    def detect(
        self,
        audio: Optional[bytes] = None,
        text: Optional[str] = None,
        speech_pause: Optional[bool] = None,
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        return asyncio.run(self.async_detect(audio, text, speech_pause))

    async def async_detect(
        self,
        audio: Optional[bytes] = None,
        text: Optional[str] = None,
        speech_pause: Optional[bool] = None,
    ) -> TurnDetectionResult | list[TurnDetectionResult]:
        if text == None:
            return TurnDetectionResult(
                action=TurnDetectionAction.DO_NOTHING,
                semantic=TurnDetectionSemantic.IDLE,
            )
        async with self.listening_lock():
            if self.listening:
                if speech_pause:
                    # Cut down prefix to avoid misclassfication
                    text_to_judge = text
                    if text.startswith(self._incomplete_cache_text):
                        text_to_judge = text_to_judge[
                            len(self._incomplete_cache_text) :
                        ]
                    messages = [
                        SystemMessage(content=self.START_GENERATION_PROMPT),
                        HumanMessage(content=text_to_judge),
                    ]
                    response = (await self._model.ainvoke(messages)).content
                    if "finished" in response.lower():
                        self._incomplete_cache_text = ""
                        return TurnDetectionResult(
                            action=TurnDetectionAction.START_GENERATION,
                            semantic=TurnDetectionSemantic.COMPLETE,
                        )
                    # Cache current text to get cut down in the future to avoid misclassification
                    self._incomplete_cache_text = text
                    return TurnDetectionResult(
                        action=TurnDetectionAction.DO_NOTHING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )
            else:
                messages = [
                    SystemMessage(content=self.STOP_SPEAKING_PROMPT),
                    HumanMessage(content=text),
                ]
                response = (await self._model.ainvoke(messages)).content
                if "backchannel" in response.lower():
                    return TurnDetectionResult(
                        action=TurnDetectionAction.DO_NOTHING,
                        semantic=TurnDetectionSemantic.BACKCHANNEL,
                    )
                if "interrupt" in response.lower():
                    result = TurnDetectionResult(
                        action=TurnDetectionAction.STOP_SPEAKING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )

                    # Need to additional check for start generation if meet speech paused (indicating a potential end of speech)
                    if speech_pause:
                        messages = [
                            SystemMessage(content=self.START_GENERATION_PROMPT),
                            HumanMessage(content=text),
                        ]
                        response = (await self._model.ainvoke(messages)).content
                        if "complete" in response.lower():
                            result = [
                                TurnDetectionResult(
                                    action=TurnDetectionAction.STOP_SPEAKING,
                                    semantic=TurnDetectionSemantic.COMPLETE,
                                ),
                                TurnDetectionResult(
                                    action=TurnDetectionAction.START_GENERATION,
                                    semantic=TurnDetectionSemantic.COMPLETE,
                                ),
                            ]
                    return result
            return TurnDetectionResult(
                action=TurnDetectionAction.DO_NOTHING,
                semantic=TurnDetectionSemantic.IDLE,
            )
