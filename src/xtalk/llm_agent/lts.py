"""Long-term-state agent scaffold.

Implementation plan
-------------------
- Start one LLM inference task for every ``ASRPartial`` event. The design may
  later be extended to other event types.
- Each partial-path inference uses the slow model and must produce structured
  output with three fields: reasoning content, whether the agent should start
  replying early, and the reply content itself.
- Partial-path inference takes the current partial ASR text, the dialogue
  history, and the latest completed assistant reply as input.
- When ``ASRResultFinal`` arrives, aggregate partial-path results to generate
  the final reply. The current strategy is to use the latest completed partial
  result for the same turn.
- Final-path generation uses the fast model and takes the dialogue history, the
  final ASR text, and the selected partial reply draft as input.
- A partial-path inference may decide to start replying early. When that
  happens, emit the partial reply content immediately and discard the next
  ``ASRResultFinal`` for the same turn.
- Every committed final reply, including early-start replies, must be injected
  into ``messages`` so later turns can see the updated conversation history.
- All generation paths use streaming generation internally.
- This version does not support tools.
- Logging and tests are intentionally deferred for now.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import json
from typing import Any, AsyncIterator, Callable, Iterable, TypeVar

from langchain.chat_models.base import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from ..log_utils import logger
from .default import AgentSession
from .interfaces import Agent, AgentContext, AgentOutput

T = TypeVar("T")


@dataclass
class PartialInferenceResult:
    """Structured output returned by the slow-model partial inference."""

    reasoning_content: str
    should_start_reply: bool
    reply_content: str


@dataclass
class PartialInferenceState:
    """Track one slow-model inference task launched from an ASR partial."""

    partial_id: int
    turn_id: int
    text: str
    task: asyncio.Task[PartialInferenceResult] | None = None
    result: PartialInferenceResult | None = None
    emitted_early: bool = False


@dataclass
class LTSRuntimeState:
    """Mutable runtime state for concurrent partial/final generation."""

    next_partial_id: int = 1
    partials: dict[int, PartialInferenceState] = field(default_factory=dict)
    discard_final_turn_ids: set[int] = field(default_factory=set)


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
    slow_model : BaseChatModel | dict[str, Any]
        Backing slow chat model instance or deferred model configuration.
    fast_model : BaseChatModel | dict[str, Any]
        Backing fast chat model instance or deferred model configuration.
    system_prompt : str, optional
        Base system prompt for future LTS interactions.
    """

    BASE_PROMPT: str = ""
    PARTIAL_INFERENCE_PROMPT_TEMPLATE: str = (
        "You are assisting a streaming speech agent.\n"
        "Given the dialogue history, the newest partial ASR text, "
        "and the latest completed partial-draft reply, decide whether the agent should start "
        "replying early to the partial ASR text, and create reply to the dialogue history and partial ASR text regardless of the reply decision.\n"
        "Return exactly one JSON object and nothing else.\n"
        'The JSON object must contain keys "reasoning_content", '
        '"should_start_reply", and "reply_content".\n'
        '"reasoning_content" must be a string.\n'
        '"should_start_reply" must be a boolean.\n'
        '"reply_content" must be a string.\n\n'
        "Dialogue history:\n{history}\n\n"
        "Current partial ASR:\n{partial_text}\n\n"
        "Latest completed partial-draft reply:\n{latest_partial_reply}\n"
    )
    FINAL_RESPONSE_PROMPT_TEMPLATE: str = (
        "You are assisting a streaming speech agent.\n"
        "Generate the final assistant reply for the current user turn.\n"
        "Use the dialogue history, the final ASR text, and the partial-reply "
        "draft when it is helpful.\n"
        "Return plain text only.\n\n"
        "Dialogue history:\n{history}\n\n"
        "Latest partial reply draft:\n{partial_draft}\n\n"
        "Final ASR:\n{final_text}\n"
    )

    def __init__(
        self,
        slow_model: BaseChatModel | dict[str, Any],
        fast_model: BaseChatModel | dict[str, Any],
        system_prompt: str = BASE_PROMPT,
    ) -> None:
        """Initialize the LTS agent scaffold."""

        self.slow_model = self._coerce_model(slow_model)
        self.fast_model = self._coerce_model(fast_model)
        self.system_prompt = system_prompt
        self._session = AgentSession()
        self._runtime = LTSRuntimeState()
        self._state_lock = asyncio.Lock()

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

    def _append_final_reply(self, user_text: str, reply_text: str) -> None:
        """Append one committed user/assistant turn into session history."""

        self._set_system_prompt()
        self._session.messages.append(HumanMessage(content=user_text))
        self._session.messages.append(AIMessage(content=reply_text))

    def _get_chat_messages_snapshot(self) -> list[BaseMessage]:
        """Return one detached snapshot of the current chat messages.

        Returns
        -------
        list[BaseMessage]
            Chat history snapshot with the current system prompt normalized into
            the first message.
        """

        messages = deepcopy(self._session.messages)
        if messages and isinstance(messages[0], SystemMessage):
            messages[0].content = self.system_prompt
            return messages
        return [SystemMessage(content=self.system_prompt), *messages]

    def _get_latest_completed_partial_reply(self) -> str | None:
        """Return the latest completed partial-draft reply content."""

        completed = [
            state
            for state in self._runtime.partials.values()
            if state.result is not None and state.result.reply_content.strip()
        ]
        if not completed:
            return None
        latest_state = max(completed, key=lambda state: state.partial_id)
        result = latest_state.result
        if result is None:
            return None
        return result.reply_content

    def _build_partial_prompt(
        self,
        *,
        history_text: str | None,
        latest_partial_reply: str | None,
        partial_text: str,
    ) -> str:
        """Build the slow-model prompt for one partial ASR update."""

        history = history_text or "<empty>"
        latest_partial_reply_text = latest_partial_reply or "<none>"
        return self.PARTIAL_INFERENCE_PROMPT_TEMPLATE.format(
            history=history,
            latest_partial_reply=latest_partial_reply_text,
            partial_text=partial_text,
        )

    def _build_partial_messages(
        self,
        *,
        history_text: str | None,
        latest_partial_reply: str | None,
        partial_text: str,
    ) -> list[BaseMessage]:
        """Build the slow-model messages for one partial ASR update.

        Parameters
        ----------
        history_text : str | None
            Serialized chat history without the current partial text.
        latest_partial_reply : str | None
            Latest completed partial-draft reply, if any.
        partial_text : str
            Current partial ASR text.

        Returns
        -------
        list[BaseMessage]
            Messages sent to the slow model.
        """

        prompt = self._build_partial_prompt(
            history_text=history_text,
            latest_partial_reply=latest_partial_reply,
            partial_text=partial_text,
        )
        return [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=prompt),
        ]

    def _build_final_prompt(
        self,
        *,
        history_text: str | None,
        final_text: str,
        partial_reply: str | None,
    ) -> str:
        """Build the fast-model prompt for final response generation."""

        history = history_text or "<empty>"
        partial_draft = partial_reply or "<none>"
        return self.FINAL_RESPONSE_PROMPT_TEMPLATE.format(
            history=history,
            partial_draft=partial_draft,
            final_text=final_text,
        )

    def _build_final_messages(
        self,
        *,
        history_text: str | None,
        final_text: str,
        partial_reply: str | None,
    ) -> list[BaseMessage]:
        """Build the fast-model messages for one final ASR update.

        Parameters
        ----------
        history_text : str | None
            Serialized chat history without the current final text.
        final_text : str
            Final ASR text for the current turn.
        partial_reply : str | None
            Latest completed partial-draft reply for the current turn.

        Returns
        -------
        list[BaseMessage]
            Messages sent to the fast model.
        """

        if partial_reply and partial_reply.strip():
            prompt = self._build_final_prompt(
                history_text=history_text,
                final_text=final_text,
                partial_reply=partial_reply,
            )
            return [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt),
            ]

        messages = self._get_chat_messages_snapshot()
        messages.append(HumanMessage(content=final_text))
        return messages

    def _extract_json_text(self, text: str) -> str:
        """Extract one JSON object from model text output."""

        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        return stripped

    def _parse_partial_result(self, text: str) -> PartialInferenceResult:
        """Parse the slow-model JSON output into a typed partial result."""

        payload = json.loads(self._extract_json_text(text))
        if not isinstance(payload, dict):
            raise ValueError("Partial inference output must be a JSON object.")
        reasoning_content = payload.get("reasoning_content", "")
        should_start_reply = payload.get("should_start_reply", False)
        reply_content = payload.get("reply_content", "")
        if isinstance(should_start_reply, str):
            should_start_reply = should_start_reply.strip().lower() in {
                "1",
                "true",
                "yes",
            }
        return PartialInferenceResult(
            reasoning_content=str(reasoning_content),
            should_start_reply=bool(should_start_reply),
            reply_content=str(reply_content),
        )

    def _select_latest_completed_partial(
        self,
        turn_id: int,
    ) -> PartialInferenceState | None:
        """Return the latest completed partial state for one turn."""

        completed = [
            state
            for state in self._runtime.partials.values()
            if state.turn_id == turn_id and state.result is not None
        ]
        if not completed:
            return None
        return max(completed, key=lambda state: state.partial_id)

    def _drop_turn_partials(self, turn_id: int) -> None:
        """Drop all cached partial states belonging to one turn."""

        self._runtime.partials = {
            partial_id: state
            for partial_id, state in self._runtime.partials.items()
            if state.turn_id != turn_id
        }

    async def _run_partial_inference(
        self,
        *,
        history_text: str | None,
        latest_partial_reply: str | None,
        partial_text: str,
    ) -> PartialInferenceResult:
        """Run one slow-model partial inference to completion."""

        messages = self._build_partial_messages(
            history_text=history_text,
            latest_partial_reply=latest_partial_reply,
            partial_text=partial_text,
        )
        chunks: list[str] = []
        async for chunk in self.slow_model.astream(messages):
            text = str(chunk.content or "")
            if text:
                chunks.append(text)
        return self._parse_partial_result("".join(chunks))

    async def _stream_final_response(
        self,
        *,
        history_text: str | None,
        final_text: str,
        partial_reply: str | None,
    ) -> AsyncIterator[str]:
        """Stream the fast-model final reply text for one final ASR."""

        messages = self._build_final_messages(
            history_text=history_text,
            final_text=final_text,
            partial_reply=partial_reply,
        )
        async for chunk in self.fast_model.astream(messages):
            text = str(chunk.content or "")
            if text:
                yield text

    async def _handle_asr_partial(
        self,
        payload: dict[str, Any],
    ) -> AsyncIterator[AgentOutput]:
        """Handle one partial ASR update."""

        partial_text = str(payload.get("text", "") or "").strip()
        if not partial_text:
            return
        turn_id = int(payload.get("turn_id", 0) or 0)
        history_text = self.get_chat_history(with_system=False)

        async with self._state_lock:
            latest_partial_reply = self._get_latest_completed_partial_reply()
            partial_id = self._runtime.next_partial_id
            self._runtime.next_partial_id += 1
            state = PartialInferenceState(
                partial_id=partial_id,
                turn_id=turn_id,
                text=partial_text,
            )
            state.task = asyncio.create_task(
                self._run_partial_inference(
                    history_text=history_text,
                    latest_partial_reply=latest_partial_reply,
                    partial_text=partial_text,
                )
            )
            self._runtime.partials[partial_id] = state

        task = state.task
        if task is None:
            return
        result = await task

        emit_reply = False
        async with self._state_lock:
            current_state = self._runtime.partials.get(partial_id)
            if current_state is None:
                return
            current_state.result = result
            if (
                result.should_start_reply
                and turn_id not in self._runtime.discard_final_turn_ids
            ):
                current_state.emitted_early = True
                self._runtime.discard_final_turn_ids.add(turn_id)
                self._append_final_reply(partial_text, result.reply_content)
                emit_reply = True

        if emit_reply and result.reply_content:
            yield result.reply_content

    async def _handle_asr_final(
        self,
        payload: dict[str, Any],
    ) -> AsyncIterator[AgentOutput]:
        """Handle one final ASR update."""

        final_text = str(payload.get("text", "") or "").strip()
        if not final_text:
            return
        turn_id = int(payload.get("turn_id", 0) or 0)

        async with self._state_lock:
            if turn_id in self._runtime.discard_final_turn_ids:
                self._runtime.discard_final_turn_ids.discard(turn_id)
                self._drop_turn_partials(turn_id)
                return
            latest_partial = self._select_latest_completed_partial(turn_id)

        history_text = self.get_chat_history(with_system=False)
        partial_reply = latest_partial.result.reply_content if latest_partial else None
        chunks: list[str] = []
        async for text in self._stream_final_response(
            history_text=history_text,
            final_text=final_text,
            partial_reply=partial_reply,
        ):
            chunks.append(text)
            yield text

        reply_text = "".join(chunks)
        async with self._state_lock:
            self._append_final_reply(final_text, reply_text)
            self._drop_turn_partials(turn_id)

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

        payload = context.get("data") or {}
        if not isinstance(payload, dict):
            return
        context_type = str(context.get("type", "") or "")
        if context_type == "asr_partial":
            async for item in self._handle_asr_partial(payload):
                yield item
            return
        if context_type == "asr_final":
            async for item in self._handle_asr_final(payload):
                yield item
            return
        return

    def clone(self) -> "Agent":
        """Clone the agent for a new session.

        Returns
        -------
        Agent
            Session-safe LTS agent instance.
        """

        return type(self)(
            slow_model=self.slow_model,
            fast_model=self.fast_model,
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

        del tools
        return None
