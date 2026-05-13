from . import Agent, AgentContext, AgentOutput
from langchain.chat_models.base import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolCall,
)
from typing import Any, Iterable, AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
import asyncio
import json
from uuid import uuid4


@dataclass
class TextCollector:
    # TODO: able to collect tool result
    parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.parts)


class ExperimentalAgent(Agent):
    BASE_SYSTEM_PROMPT = "你的回复应贴近日常对话，保持简要但信息丰富。你的回复不能出现TTS无法合成的内容，例如* - （） ()。"
    GREETING_GEN_PROMPT = "根据以下角色设定/角色设定，生成一句该角色可能会发出的问候语。角色设定/系统提示："
    BACKCHANNEL_JUDGE_PROMPT = """
    附和规则：
    1. 如果用户内容还不完整，不进行附和
    2. 用户内容完整后，如果符合以下情况之一，则进行附和，写入附和类型并选择合适的附和词；否则不进行附和：
    附和类型：维持对话流畅  触发条件：对方在讲故事或叙述经历、在解释或说明某事；内容还未完整表达但当前语义完整
    附和类型：表达共鸣  触发条件：对方在表达情绪、感受、观点等主观内容；内容还未完整表达但当前语义完整
    可选附和词：__BACKCHANNEL_OPTIONS__
    根据以下用户输入与以上规则，判断是否要进行附和，附和的类型是什么，以及附和的内容是什么；仅返回JSON，格式如下：{"reasoning_content": str, "should_backchannel": bool, "backchannel_type": Optional[附和类型], "backchannel_content": Optional[str]}。用户输入："""

    def __init__(
        self,
        model: BaseChatModel | dict[str, Any],
        backchannel_model: BaseChatModel | dict[str, Any],
        backchannel_source_dir: str | Path,
        system_prompt: str = "",
    ) -> None:
        self.model = model if isinstance(model, BaseChatModel) else ChatOpenAI(**model)
        self.backchannel_model = (
            backchannel_model
            if isinstance(backchannel_model, BaseChatModel)
            else ChatOpenAI(**backchannel_model)
        )
        self._additional_system_prompt = system_prompt
        self.system_prompt = self.BASE_SYSTEM_PROMPT + system_prompt
        self.messages = [SystemMessage(content=self.system_prompt)]
        self.backchannel_source_dir = (
            backchannel_source_dir
            if isinstance(backchannel_source_dir, Path)
            else Path(backchannel_source_dir)
        )

        # every time remove this prefix before judging backchannel
        self._already_backchanneled_text = ""

    def accept(self, context: AgentContext) -> Iterable[AgentOutput]:
        yield from self.sync_iter_from_async(self.async_accept(context))

    async def async_accept(self, context: AgentContext) -> AsyncIterator[AgentOutput]:
        context_type = context["type"]
        context_data = context["data"]
        # dispatch context
        if context_type == "loop":
            async for item in self._loop_runner():
                yield item
        if context_type == "asr_final":
            async for item in self._handle_asr_final(context_data["text"]):
                yield item
        if context_type == "asr_partial":
            async for item in self._handle_asr_partial(context_data["text"]):
                yield item

    def clone(self) -> "ExperimentalAgent":
        return ExperimentalAgent(
            model=self.model,
            backchannel_model=self.backchannel_model,
            backchannel_source_dir=self.backchannel_source_dir,
            system_prompt=self._additional_system_prompt,
        )

    def restore_history(self, messages: list[dict[str, Any]]) -> None:
        self.messages = [SystemMessage(content=self.system_prompt)]
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                self._append_message(HumanMessage(content=content))
            elif role == "assistant":
                self._append_message(AIMessage(content=content))

    def get_chat_history(self, with_system: bool = False) -> str | None:
        if not self.messages:
            return None
        start_idx = 0 if with_system else 1
        return "\n".join(
            f"{msg.type}: {msg.content}" for msg in self.messages[start_idx:]
        )

    # global utilities
    def _append_message(self, message: BaseMessage) -> None:
        self.messages.append(message)

    async def _stream_and_collect_text(
        self, stream: AsyncIterator[AgentOutput], collector: TextCollector
    ) -> AsyncIterator[str]:
        async for chunk in stream:
            if isinstance(chunk, str):
                collector.parts.append(chunk)
            yield chunk

    ###

    async def _loop_runner(self) -> AsyncIterator[AgentOutput]:
        while True:
            # greeting: AI take initiative to call user on session start
            if len(self.messages) == 1:
                collector = TextCollector()
                async for item in self._stream_and_collect_text(
                    self._stream_greeting(), collector
                ):
                    yield item
                # append user first
                self._append_message(HumanMessage(content="你好。"))
                self._append_message(AIMessage(content=collector.text))
                # since this should only be triggered once and no other logic in the loop, break temporarily
                break
            # avoid blocking the event loop
            await asyncio.sleep(0.2)

    async def _handle_asr_final(self, asr_text: str) -> AsyncIterator[AgentOutput]:
        self._append_message(HumanMessage(content=asr_text))
        collector = TextCollector()
        async for item in self._stream_and_collect_text(
            self._stream_messages(), collector
        ):
            yield item
        self._append_message(AIMessage(content=collector.text))
        # reset backchannel prefix
        self._already_backchanneled_text = ""

    # backchannel
    async def _handle_asr_partial(self, asr_text: str) -> AsyncIterator[AgentOutput]:
        # remove prefix from asr text to avoid repeated backchannel for the same content
        text_to_judge = asr_text[len(self._already_backchanneled_text) :]
        messages = [
            HumanMessage(
                content=self.BACKCHANNEL_JUDGE_PROMPT.replace(
                    "__BACKCHANNEL_OPTIONS__", "、".join(self._load_backchannel_texts())
                )
                + text_to_judge
            )
        ]
        response_content = (await self.backchannel_model.ainvoke(messages)).content
        structured_content = None
        try:
            structured_content = json.loads(response_content)
            if (
                not isinstance(structured_content, dict)
                or "should_backchannel" not in structured_content
            ):
                return
        except json.JSONDecodeError:
            return
        should_backchannel = bool(structured_content["should_backchannel"])
        if (
            not should_backchannel
            or "backchannel_content" not in structured_content
            or not structured_content["backchannel_content"]
        ):
            return
        audio_bytes = self._load_backchannel_audio(
            structured_content["backchannel_content"]
        )
        if not audio_bytes:
            return
        # update already backchanneled text to avoid repeated backchannel
        self._already_backchanneled_text = asr_text
        yield ToolCall(
            name="direct_audio",
            args={
                "audio": audio_bytes,
                "sample_rate": 48000,
            },
            id=f"direct-audio-{uuid4().hex}",
        )

    async def _stream_greeting(self) -> AsyncIterator[str]:
        prompt = self.GREETING_GEN_PROMPT + self.system_prompt
        messages = [SystemMessage(content=prompt)]
        async for chunk in self.model.astream(messages):
            yield chunk.content

    async def _stream_messages(self) -> AsyncIterator[AgentOutput]:
        # TODO: handle tool calling and tool result
        async for chunk in self.model.astream(self.messages):
            yield chunk.content

    def _load_backchannel_audio(self, backchannel_content: str) -> bytes | None:
        map_path = self.backchannel_source_dir / "map.json"
        if not map_path.is_file():
            return None
        with open(map_path, "r", encoding="utf-8") as f:
            content_map: dict[str, str] = json.load(f)
        filename = content_map.get(backchannel_content)
        if not filename:
            return None
        audio_path = self.backchannel_source_dir / filename
        if not audio_path.is_file():
            return None
        try:
            return audio_path.read_bytes()
        except Exception:
            return None

    def _load_backchannel_texts(self) -> list[str]:
        map_path = self.backchannel_source_dir / "map.json"
        if not map_path.is_file():
            return []
        with open(map_path, "r", encoding="utf-8") as f:
            content_map: dict[str, str] = json.load(f)
        return list(content_map.keys())
