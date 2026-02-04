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


# TODO: re-implement
class LLMTurnDetector(TurnDetector):
    STOP_SPEAKING_PROMPT = """You are a classifier. Given a user utterance that is a *text transcription* from a live speech conversation (ASR output), decide whether it is:

* **backchannel**: short acknowledgements / continuer signals that do **not** take the floor or change the topic.
* **wait**: explicit request for the assistant to pause/hold or “one moment”.
* **interrupt**: user is cutting in to take the floor, correct/redirect, ask a question, or stop/modify what the assistant is saying.

**Output exactly one label from:** `["backchannel", "wait", "interrupt"]`

## Decision rules (use the first matching rule)

### 1) **wait**

Label as **wait** if the utterance explicitly asks to pause or hold, e.g.:

* “wait”, “hold on”, “one sec/second”, “a moment”, “give me a second”
* “stop for a bit”, “pause”, “hang on”, “let me think”
* “等一下/等等/稍等/先别说/先停一下/给我一分钟”

### 2) **backchannel**

Label as **backchannel** if it's primarily a continuer/acknowledgement and **does not** introduce new content or a request, e.g.:

* “uh-huh”, “mm-hmm”, “yeah”, “yep”, “ok”, “right”, “I see”, “got it”
* “嗯/啊哈/对/好/行/懂了/明白/是的”
* brief laughter tokens like “haha” when used as acknowledgement

**Heuristic:** typically ≤ 3-4 words, no question, no directive verbs (stop/pause/repeat), no new task/topic.

### 3) **interrupt**

Label as **interrupt** otherwise, including:

* asking a question mid-stream: “but why...?”, “what about...?”
* correcting/redirecting: “no, I meant...”, “actually...”, “not that...”
* stopping/modifying assistant speech without asking to “wait”: “stop”, “don't say that”, “let's switch”
* adding substantial info: names, numbers, constraints, new topic, instructions

## Tie-breakers / ASR noise handling

* If it contains both acknowledgement and a new request/topic (e.g., “yeah but...”, “ok so do X”), choose **interrupt**.
* If it contains “wait/hold on/等一下” anywhere and it's a genuine pause request, choose **wait** even if there's also an acknowledgement.
* If it's unclear but longer than a simple acknowledgement or includes content words beyond agreement, choose **interrupt**.

## Output format

Return **only** the label string.
"""
    START_GENERATION_PROMPT = """You are a real-time speech-UI classifier. Given an ASR transcript of what the user just said (may be partial, noisy, or cut off), classify whether the user's utterance is:

* **incomplete**: the user is still speaking / the thought is unfinished, or ASR looks truncated.
* **complete**: the user finished a coherent utterance (question/command/statement) and is yielding the floor.
* **wait**: the user explicitly asks the assistant to pause/hold while they think or do something.

**Output exactly one label from:** `["incomplete", "complete", "wait"]`

## Decision rules (apply in order)

### 1) **wait**

Choose **wait** if the transcript contains an explicit pause/hold request, e.g.:

* English: “wait”, “hold on”, “hang on”, “one sec/second”, “a moment”, “give me a second”, “pause”, “let me think”
* Chinese: “等一下/等等/稍等/先别说/先停一下/给我一分钟/我想一下”
* Any variant like “stop, wait” where the intent is to pause the assistant

If “wait” is present but clearly means something else (rare), follow the other rules.

### 2) **incomplete**

Choose **incomplete** if **any** of these are true:

**A. Truncation / cut-off indicators**

* Transcript ends with unfinished connectors: “and”, “so”, “but”, “because”, “if”, “then”, “like”, “which”, “that...”
* Ends with filler or restart signals: “uh”, “um”, “er”, “I mean”, “well...”, “你知道”, “就是”, “然后...”
* Ends with a dangling preposition/article: “to”, “with”, “for”, “a/an/the”, “的/了/在/把” (when clearly hanging)

**B. Mid-thought structure**

* Starts a clause but doesn't complete it: “I want to...”, “Can you...”, “Let's...”, “Could we...”, “我想.../能不能.../我们...”
* Contains self-correction or continuation cues without finishing: “no—”, “actually—”, “wait— I mean—”, “不是...我是说...”

**C. ASR partialness signs**

* Very short fragment that looks like a partial start (1-3 content words) and not a full intent, e.g. “so the...”, “about the...”, “那个...”, “就是...”
* Strong repetition/restarts: “I I I...”, “we we...”, “我我我...”

### 3) **complete**

Choose **complete** if neither of the above applies and the utterance forms a complete communicative unit, e.g.:

* A full question: ends naturally or with “?”, has an interrogative (“what/why/how/能不能/怎么”)
* A full command/request: “Open X”, “Explain Y”, “帮我把...”
* A complete statement: “I'm done”, “That's fine”, “We should do A first”
* Even if short, it clearly conveys a finished intent: “yes”, “no”, “okay”, “got it”, “不用了”, “可以”

## Tie-breakers

* If the transcript ends with a period-like finality (or clear completion) vs. a dangling connector, prefer **complete**.
* If it includes both acknowledgement and a new clause starter (e.g., “yeah but...”, “好的然后...”), choose **incomplete** unless it clearly finishes.
* When uncertain, prefer **incomplete** (safer for turn-taking) unless it's an explicit pause request (**wait**).

## Output format

Return only the label string with no extra text.    
"""
    CHECK_COMPLETION_PROMPT = """You are a real-time speech-UI classifier. Given an ASR transcript of what the user just said (may be partial, noisy, or cut off), classify whether the user's utterance is:

* **incomplete**: the user is still speaking / the thought is unfinished, or ASR looks truncated.
* **complete**: the user finished a coherent utterance (question/command/statement) and is yielding the floor.

### 1) **incomplete**

Choose **incomplete** if **any** of these are true:

**A. Truncation / cut-off indicators**

* Transcript ends with unfinished connectors: “and”, “so”, “but”, “because”, “if”, “then”, “like”, “which”, “that...”
* Ends with filler or restart signals: “uh”, “um”, “er”, “I mean”, “well...”, “你知道”, “就是”, “然后...”
* Ends with a dangling preposition/article: “to”, “with”, “for”, “a/an/the”, “的/了/在/把” (when clearly hanging)

**B. Mid-thought structure**

* Starts a clause but doesn't complete it: “I want to...”, “Can you...”, “Let's...”, “Could we...”, “我想.../能不能.../我们...”
* Contains self-correction or continuation cues without finishing: “no—”, “actually—”, “wait— I mean—”, “不是...我是说...”

**C. ASR partialness signs**

* Very short fragment that looks like a partial start (1-3 content words) and not a full intent, e.g. “so the...”, “about the...”, “那个...”, “就是...”
* Strong repetition/restarts: “I I I...”, “we we...”, “我我我...”

### 2) **complete**

Choose **complete** if neither of the above applies and the utterance forms a complete communicative unit, e.g.:

* A full question: ends naturally or with “?”, has an interrogative (“what/why/how/能不能/怎么”)
* A full command/request: “Open X”, “Explain Y”, “帮我把...”
* A complete statement: “I'm done”, “That's fine”, “We should do A first”
* Even if short, it clearly conveys a finished intent: “yes”, “no”, “okay”, “got it”, “不用了”, “可以”

## Tie-breakers

* If the transcript ends with a period-like finality (or clear completion) vs. a dangling connector, prefer **complete**.
* If it includes both acknowledgement and a new clause starter (e.g., “yeah but...”, “好的然后...”), choose **incomplete** unless it clearly finishes.

## Output format

Return only the label string with no extra text.
"""

    def __init__(self, model: dict | BaseChatModel) -> None:
        if isinstance(model, dict):
            model = ChatOpenAI(**model)
        self._model = model
        # If AI is listening, try to determine whether to start generation and toggle state;
        # else determine whether to stop speaking and toggle state
        self._listening = True
        # FIXED: lock listening
        self._listening_lock = asyncio.Lock()

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
        async with self._listening_lock:
            if self._listening:
                messages = [
                    SystemMessage(content=self.START_GENERATION_PROMPT),
                    HumanMessage(content=text),
                ]
                response = (await self._model.ainvoke(messages)).content
                if speech_pause and "complete" in response.lower():
                    self._listening = False
                    return TurnDetectionResult(
                        action=TurnDetectionAction.START_GENERATION,
                        semantic=TurnDetectionSemantic.COMPLETE,
                    )
                if "incomplete" in response.lower():
                    return TurnDetectionResult(
                        action=TurnDetectionAction.DO_NOTHING,
                        semantic=TurnDetectionSemantic.INCOMPLETE,
                    )
                if "wait" in response.lower():
                    return TurnDetectionResult(
                        action=TurnDetectionAction.DO_NOTHING,
                        semantic=TurnDetectionSemantic.WAIT,
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
                if "wait" in response.lower():
                    self._listening = True
                    return TurnDetectionResult(
                        action=TurnDetectionAction.STOP_SPEAKING,
                        semantic=TurnDetectionSemantic.WAIT,
                    )
                if "interrupt" in response.lower():
                    self._listening = True
                    result = [
                        TurnDetectionResult(
                            action=TurnDetectionAction.STOP_SPEAKING,
                            semantic=TurnDetectionSemantic.INCOMPLETE,
                        )
                    ]
                    # Need to additional check for start generation if meet speech paused (indicating a potential end of speech)
                    if speech_pause:
                        messages = [
                            SystemMessage(content=self.CHECK_COMPLETION_PROMPT),
                            HumanMessage(content=text),
                        ]
                        response = (await self._model.ainvoke(messages)).content
                        if "complete" in response.lower():
                            result[0].semantic = TurnDetectionSemantic.COMPLETE
                            result.append(
                                TurnDetectionResult(
                                    action=TurnDetectionAction.START_GENERATION,
                                    semantic=TurnDetectionSemantic.COMPLETE,
                                )
                            )
                    return result
            return TurnDetectionResult(
                action=TurnDetectionAction.DO_NOTHING,
                semantic=TurnDetectionSemantic.IDLE,
            )
