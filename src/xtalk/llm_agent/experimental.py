from . import Agent, AgentContext, AgentOutput
from langchain.chat_models.base import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from typing import Any, Iterable, AsyncIterator
from dataclasses import dataclass, field
import asyncio


@dataclass
class TextCollector:
    # TODO: able to collect tool result
    parts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.parts)


class ExperimentalAgent(Agent):
    BASE_SYSTEM_PROMPT = "你的回复应贴近日常对话，保持简要但信息丰富。你的回复不能出现TTS无法合成的内容，例如* - （） ()。"
    BASE_GREETING_GEN_PROMPT = "根据以下角色设定/角色设定，生成一句该角色可能会发出的问候语。角色设定/系统提示："

    def __init__(
        self, model: BaseChatModel | dict[str, Any], system_prompt: str = ""
    ) -> None:
        self.model = model if isinstance(model, BaseChatModel) else ChatOpenAI(**model)
        self._additional_system_prompt = system_prompt
        self.system_prompt = self.BASE_SYSTEM_PROMPT + system_prompt
        self.messages = [SystemMessage(content=self.system_prompt)]

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

    def clone(self) -> "ExperimentalAgent":
        return ExperimentalAgent(
            model=self.model, system_prompt=self._additional_system_prompt
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

    async def _stream_greeting(self) -> AsyncIterator[str]:
        prompt = self.BASE_GREETING_GEN_PROMPT + self.system_prompt
        messages = [SystemMessage(content=prompt)]
        async for chunk in self.model.astream(messages):
            yield chunk.content

    async def _stream_messages(self) -> AsyncIterator[AgentOutput]:
        # TODO: handle tool calling and tool result
        async for chunk in self.model.astream(self.messages):
            yield chunk.content
