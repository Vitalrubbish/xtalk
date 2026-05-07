"""Long-term-state agent scaffold."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, AsyncIterator, Callable, Iterable, TypeVar

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from ..log_utils import logger
from .default import AgentSession
from .interfaces import Agent, AgentContext, AgentOutput

T = TypeVar("T")


def _format_chat_history(
    messages: list[BaseMessage],
    *,
    with_system: bool = False,
) -> str | None:
    """Render plain-text chat history from LangChain messages.

    Parameters
    ----------
    messages : list[BaseMessage]
        Chat messages to serialize.
    with_system : bool, optional
        Whether to include system messages in the serialized output.

    Returns
    -------
    str | None
        Rendered history string, or ``None`` when no messages are available.
    """

    if not messages:
        return None
    lines: list[str] = []
    for message in messages:
        role = "System"
        if isinstance(message, HumanMessage):
            role = "User"
        elif isinstance(message, AIMessage):
            role = "Assistant"
        if role == "System" and not with_system:
            continue
        content = message.content
        lines.append(f"{role}: {content if isinstance(content, str) else str(content)}")
    return "\n".join(lines)


class LTSAgent(Agent):
    """Scaffold for an agent with long-term state support.

    Parameters
    ----------
    big_model : BaseChatModel | dict[str, Any]
        Backing large chat model instance or deferred model configuration.
    small_model : BaseChatModel | dict[str, Any]
        Backing small chat model instance or deferred model configuration.
    system_prompt : str, optional
        Base system prompt for future LTS interactions.
    tools : list[BaseTool | Callable[[], BaseTool]] | None, optional
        Initial tool instances or factories to attach to the agent.
    """

    BASE_PROMPT: str = ""

    def __init__(
        self,
        big_model: BaseChatModel | dict[str, Any],
        small_model: BaseChatModel | dict[str, Any],
        system_prompt: str = BASE_PROMPT,
    ) -> None:
        """Initialize the LTS agent scaffold."""

        self.big_model = self._coerce_model(big_model)
        self.small_model = self._coerce_model(small_model)
        self.system_prompt = system_prompt
        self._session = AgentSession()

    @staticmethod
    def _coerce_model(model: BaseChatModel | dict[str, Any]) -> BaseChatModel:
        """Coerce model configuration into a concrete chat model.

        Parameters
        ----------
        model : BaseChatModel | dict[str, Any]
            Chat model instance or ``ChatOpenAI`` configuration dict.

        Returns
        -------
        BaseChatModel
            Concrete chat model instance.
        """

        if isinstance(model, dict):
            return ChatOpenAI(**model)
        return model

    @contextmanager
    def _temporary_event_loop(self) -> Iterable[asyncio.AbstractEventLoop]:
        """Create a temporary event loop and clean it up on exit."""

        loop = asyncio.new_event_loop()
        try:
            yield loop
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            try:
                loop.run_until_complete(loop.shutdown_default_executor())
            except Exception:
                pass
            loop.close()

    def _sync_iter_from_async(self, async_iter: AsyncIterator[T]) -> Iterable[T]:
        """Convert an async iterator into a synchronous generator."""

        with self._temporary_event_loop() as loop:
            try:
                while True:
                    try:
                        item = loop.run_until_complete(async_iter.__anext__())
                    except StopAsyncIteration:
                        break
                    yield item
            finally:
                aclose = getattr(async_iter, "aclose", None)
                if callable(aclose):
                    try:
                        loop.run_until_complete(aclose())
                    except Exception:
                        pass

    def _set_system_prompt(self) -> None:
        """Ensure the first session message contains the current system prompt."""

        if self._session.messages and isinstance(
            self._session.messages[0], SystemMessage
        ):
            self._session.messages[0].content = self.system_prompt
            return
        self._session.messages.insert(0, SystemMessage(content=self.system_prompt))

    def accept(self, context: AgentContext) -> Iterable[AgentOutput]:
        """Accept an incremental context update.

        Parameters
        ----------
        context : AgentContext
            Context payload forwarded from serving-layer events.

        Returns
        -------
        Iterable[AgentOutput]
            Streamed response items produced for the accepted context.
        """

        yield from self._sync_iter_from_async(self.async_accept(context))

    async def async_accept(
        self,
        context: AgentContext,
    ) -> AsyncIterator[AgentOutput]:
        """Asynchronously accept an incremental context update.

        Parameters
        ----------
        context : AgentContext
            Context payload forwarded from serving-layer events.

        Yields
        ------
        AgentOutput
            Streamed response items produced for the accepted context.
        """

        del context
        if False:
            yield ""
        raise NotImplementedError("LTSAgent.async_accept is not implemented yet.")

    def clone(self) -> "Agent":
        """Clone the agent for a new session.

        Returns
        -------
        Agent
            Session-safe LTS agent instance.
        """

        return type(self)(
            big_model=self.big_model,
            small_model=self.small_model,
            system_prompt=self.system_prompt,
        )

    def restore_history(self, messages: list[dict[str, Any]]) -> None:
        """Restore persisted conversation messages into agent state.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            Persisted chat messages ordered by session history.
        """

        restored: list[BaseMessage] = []
        for message in messages:
            role = message.get("role")
            content = str(message.get("content", ""))
            if role == "user":
                restored.append(HumanMessage(content=content))
            elif role == "assistant":
                restored.append(AIMessage(content=content))

        self._session.messages = restored
        self._set_system_prompt()

    def get_chat_history(self, with_system: bool = False) -> str | None:
        """Return the serialized conversation history when available.

        Parameters
        ----------
        with_system : bool, optional
            Whether the serialized history should include system messages.

        Returns
        -------
        str | None
            Serialized history when implemented.
        """

        try:
            return _format_chat_history(self._session.messages, with_system=with_system)
        except Exception as exc:
            logger.warning("Failed to build chat history: %s", exc)
            return None

    def add_tools(self, tools: list[BaseTool | Callable[[], BaseTool]]) -> None:
        """Attach tools to the agent.

        Parameters
        ----------
        tools : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or factories to attach.
        """

        return
