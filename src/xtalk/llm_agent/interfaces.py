import asyncio
from abc import ABC, abstractmethod
from typing import Iterable, Union, TypedDict, List, AsyncIterator, Callable, Any
from langchain.chat_models.base import BaseChatModel
from ..pipelines.context import PipelineContext
from langchain_core.messages import ToolCall
from langchain_core.tools import BaseTool


class AgentInput(TypedDict):
    """Structured payload for agent generation input.

    Notes
    -----
    ``content`` stores the raw user text and ``context`` carries the current
    ``PipelineContext``.
    """

    content: str
    context: PipelineContext


class Agent(ABC):
    """Abstract interface for conversational agents used by Xtalk."""

    @abstractmethod
    def generate(
        self, input: Union[str, AgentInput]
    ) -> Union[str, tuple[str, List[ToolCall]]]:
        """Generate a complete response for the input.

        Parameters
        ----------
        input : str | AgentInput
            Raw user text or a structured payload containing both text and
            pipeline context.

        Returns
        -------
        str | tuple[str, List[ToolCall]]
            Plain response text, or a ``(text, tool_calls)`` tuple when tool
            calls should be surfaced alongside the final text.
        """
        pass

    def generate_stream(
        self, input: Union[str, AgentInput]
    ) -> Iterable[Union[str, ToolCall]]:
        """Stream response chunks for the input.

        Parameters
        ----------
        input : str | AgentInput
            Raw user text or structured agent input.

        Yields
        ------
        str | ToolCall
            Tool calls followed by text chunks. The default implementation
            delegates to ``generate()`` and yields its result in streaming form.
        """
        result = self.generate(input)
        if isinstance(result, tuple):
            text, tool_calls = result
            # Yield tool calls first so upstream can react early
            for tc in tool_calls:
                yield tc
            yield text
        else:
            yield result

    async def async_generate(
        self, input: Union[str, AgentInput]
    ) -> Union[str, tuple[str, List[ToolCall]]]:
        """Asynchronously generate a complete response.

        Parameters
        ----------
        input : str | AgentInput
            Raw user text or structured agent input.

        Returns
        -------
        str | tuple[str, List[ToolCall]]
            Same result contract as ``generate()``.
        """

        loop = asyncio.get_running_loop()

        def _invoke():
            return self.generate(input)

        return await loop.run_in_executor(None, _invoke)

    async def async_generate_stream(
        self, input: Union[str, AgentInput]
    ) -> AsyncIterator[Union[str, ToolCall]]:
        """Asynchronously stream agent outputs.

        Parameters
        ----------
        input : str | AgentInput
            Raw user text or structured agent input.

        Yields
        ------
        str | ToolCall
            Streamed outputs from ``generate_stream()``.
        """

        loop = asyncio.get_running_loop()
        iterator = iter(self.generate_stream(input))
        sentinel = object()

        try:
            while True:

                def _next_item():
                    try:
                        return next(iterator)
                    except StopIteration:
                        return sentinel

                item = await loop.run_in_executor(None, _next_item)
                if item is sentinel:
                    break
                yield item
        finally:
            close = getattr(iterator, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    @abstractmethod
    def clone(self) -> "Agent":
        """Clone the agent for a new session.

        Returns
        -------
        Agent
            Session-safe agent instance.
        """
        pass

    @abstractmethod
    def restore_history(self, messages: list[dict[str, Any]]) -> None:
        """Restore persisted conversation messages into the agent state.

        Parameters
        ----------
        messages : list[dict[str, Any]]
            Persisted chat messages ordered by session history.
        """
        pass

    def get_llm(self) -> BaseChatModel | None:
        """Return the backing chat model when the agent exposes one.

        Returns
        -------
        BaseChatModel | None
            Underlying chat model or ``None``.
        """
        return None

    def get_chat_history(self) -> str | None:
        """Return the serialized conversation history when available.

        Returns
        -------
        str | None
            Conversation history or ``None``.
        """
        return None

    def add_tools(self, tools: list[BaseTool | Callable[[], BaseTool]]):
        """Attach tools to the agent.

        Parameters
        ----------
        tools : list[BaseTool | Callable[[], BaseTool]]
            Tool instances or factories that produce tool instances.
        """
        pass
