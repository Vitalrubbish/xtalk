"""Execute official DuplexCascade model micro-turns on the native TTS chain."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import aiohttp
from contextlib import aclosing
from typing import Any
from uuid import uuid4

from xtalk.serving.event_bus import EventBus, EventDispatchMode
from xtalk.serving.events import (
    DuplexMicroTurnReady, DuplexProtocolError, DuplexProtocolParsed,
    LLMAgentResponseFinish, LLMAgentResponseUpdate, LLMFirstChunk,
    ResponseFinish, ResponseUpdate, TTSResponseClosed, TTSStarted,
    TurnTTSFlushRequested, TurnTTSStartRequested, TurnTTSStopRequested,
    TurnTTSTextAppendRequested,
)
from xtalk.serving.interfaces import Manager
from .model_client import DuplexModelClient, GenerationEnd
from .protocol import ControlToken, ProtocolParseError, WireControl, WireMicroTurnParser


class DuplexRuntimeAdapter(Manager):
    """Serialize model inference and execute its raw conversational decisions.

    Parameters
    ----------
    event_bus : EventBus
        Session event bus owning the existing synthesis and playback chain.
    session_id : str
        Owning session.
    config : dict | None
        duplex_model_url, max tokens, timeout and optional injected model client.
    """

    def __init__(self, event_bus: EventBus, session_id: str, config: dict[str, Any] | None = None) -> None:
        self.event_bus = event_bus
        self.session_id = session_id
        self.config = config or {}
        self.client = self.config.get("duplex_model_client") or DuplexModelClient(
            self.config.get("duplex_model_url", "http://127.0.0.1:8006"),
            int(self.config.get("duplex_max_new_tokens", 64)),
            float(self.config.get("duplex_timeout_seconds", 30)),
            session_id=session_id, use_cache=bool(self.config.get("duplex_kv_cache_enabled", True)),
        )
        self.history: list[dict[str, Any]] = []
        self.heard: dict[str, str] = {}
        self._response_id = ""
        self._response_text = ""
        self._response_meta: dict[str, Any] = {}
        self._delivering = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._seen_requests: set[str] = set()
        self._last_prefix_version = -1
        self._tasks: set[asyncio.Task] = set()
        self._playback_response_id = ""
        self._playback_meta: dict[str, Any] = {}
        # Official ``tts_speaking_flag``: `<|user finish talking|>` opens the
        # window in which speaking/interruption markers may reset audio.
        self._speaking = False

    @Manager.event_handler(DuplexMicroTurnReady)
    async def _handle_micro_turn(self, event: DuplexMicroTurnReady) -> None:
        """Run one official system micro-turn, applying every control token it emits."""
        if event.session_id != self.session_id or self._closed:
            return
        task = asyncio.current_task()
        if task is not None:
            self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    return
                if event.request_id in self._seen_requests:
                    await self._error(event, "duplicate_request", "", "request already consumed")
                    return
                # Bound duplicate tracking; only live recent transport requests matter.
                if len(self._seen_requests) >= 4096:
                    self._seen_requests.clear()
                if event.prefix_version < self._last_prefix_version:
                    await self._error(event, "stale_prefix", "", "prefix version precedes the last consumed snapshot")
                    return
                self._last_prefix_version = event.prefix_version
                self._seen_requests.add(event.request_id)
                self._append_user(event)
                parser = WireMicroTurnParser()
                finish_reason = "stop"
                token_ids: tuple[int, ...] = ()
                observed_response_id = self._response_id or self._playback_response_id
                try:
                    stream = (self.client.stream(self._request_history(), request_id=event.request_id)
                              if isinstance(self.client, DuplexModelClient)
                              else self.client.stream(self._request_history()))
                    async with aclosing(stream):
                        async for chunk in stream:
                            if isinstance(chunk, GenerationEnd):
                                finish_reason = chunk.reason
                                token_ids = chunk.token_ids
                                continue
                            if not parser.raw_output:
                                await self._publish(LLMFirstChunk, event, response_id=self._response_id)
                            for item in parser.feed(chunk):
                                if isinstance(item, WireControl):
                                    await self._apply_control(event, parser, item, observed_response_id)
                                else:
                                    await self._append_answer(event, item.text, item.wire_token)
                    parser.finish(finish_reason)
                    # The released server decodes until <|im_end|> and appends the
                    # generated ids verbatim; it never truncates on interruption.
                    if not token_ids:
                        raise ProtocolParseError("missing_generation", parser.raw_output,
                                                 "model service ended without generated token ids")
                    self.history.append({"role": "assistant", "token_ids": list(token_ids),
                                         "text": parser.raw_output})
                except ProtocolParseError as exc:
                    await self._error(event, exc.code, exc.raw_output, str(exc))
                    await self._stop_answer("protocol_error")
                except (OSError, RuntimeError, asyncio.TimeoutError, aiohttp.ClientError) as exc:
                    await self._error(event, "model_service_error", parser.raw_output, str(exc))
                    await self._stop_answer("model_service_error")
        except asyncio.CancelledError:
            await self._stop_answer("cancelled")
            raise
        finally:
            if task is not None:
                self._tasks.discard(task)

    async def _apply_control(
        self,
        event: DuplexMicroTurnReady,
        parser: WireMicroTurnParser,
        item: WireControl,
        observed_response_id: str,
    ) -> None:
        """Execute one control token in arrival order and observe it.

        Every control token the official weights emit is executed, matching the
        released server that reacts to each marker it decodes.

        Parameters
        ----------
        event : DuplexMicroTurnReady
            Originating micro-turn identity.
        parser : WireMicroTurnParser
            Parser holding the raw output observed so far.
        item : WireControl
            Control token to execute.
        observed_response_id : str
            Response identity captured before this action, for observation only.
        """

        response_id = self._response_id or self._playback_response_id or observed_response_id
        reason = "control"
        if item.control is ControlToken.USER_FINISH_SPEAKING:
            self._speaking = True
        elif item.control is ControlToken.USER_IS_INTERRUPTING:
            reason = "interruption"
            await self._reset_speaking(item.wire_token)
        elif item.control is ControlToken.USER_IS_SPEAKING:
            await self._reset_speaking(item.wire_token)
        elif item.control is ControlToken.USER_IS_THINKING:
            await self._finish_answer()
        await self._publish(DuplexProtocolParsed, event,
            response_id=response_id, state_token=item.wire_token,
            response_text="", raw_output=parser.raw_output, reason=reason)

    async def _reset_speaking(self, reason: str) -> None:
        """Reset audio only while the official speaking window is open.

        The released server gates `<|user is talking|>` and
        `<|user interruption|>` on ``tts_speaking_flag``, which only
        `<|user finish talking|>` opens. Interruptions that arrive before the
        model has taken its turn therefore leave playback untouched.

        Parameters
        ----------
        reason : str
            Wire token that triggered the reset.
        """
        if not self._speaking:
            return
        self._speaking = False
        await self._stop_answer(reason)

    def _append_user(self, event: DuplexMicroTurnReady) -> None:
        """Preserve delta inputs; repair already emitted user prefixes on ASR rewrite.

        Only the user text is stored: the model service renders the official
        headers, end-of-message ids and silence marker from its own tokenizer.
        """
        scope = (event.turn_id, event.segment_id)
        delta = event.delta_text
        if event.revision_kind == "REWRITE":
            entries = [item for item in self.history if item.get("scope") == scope and item.get("source_text")]
            remaining = event.text
            for index, item in enumerate(entries):
                count = len(item["source_text"]) if index < len(entries) - 1 else len(remaining)
                replacement, remaining = remaining[:count], remaining[count:]
                item["source_text"] = replacement
                item["text"] = replacement
            # Old emitted content has been repaired; current window contains any remainder.
            delta = remaining
        self.history.append({"role": "user", "text": delta,
                             "scope": scope, "source_text": delta})

    def _request_history(self) -> list[dict[str, Any]]:
        """Return the wire history: user text and assistant generated token ids."""
        history: list[dict[str, Any]] = []
        for item in self.history:
            if item["role"] == "user":
                history.append({"role": "user", "text": item.get("text", "")})
            else:
                history.append({"role": "assistant", "token_ids": list(item.get("token_ids") or [])})
        return history

    @staticmethod
    def _filter_for_tts(text: str) -> str:
        """Return the spoken form of answer text.

        The released server removes periods from speech while keeping them for
        the frontend transcript.
        """
        return text.replace(".", "")

    async def _append_answer(self, event: DuplexMicroTurnReady, text: str, token: str) -> None:
        """Continue a response across micro-turn boundaries without restarting TTS."""
        if not self._response_id:
            self._response_id = uuid4().hex
            self._response_text = ""
            self._response_meta = dict(request_id=event.request_id, turn_id=event.turn_id,
                segment_id=event.segment_id, prefix_version=event.prefix_version,
                state_token=token, reason="duplex_answer")
            self._delivering = False
            self._playback_response_id = self._response_id
            self._playback_meta = dict(self._response_meta)
            await self.event_bus.publish(TurnTTSStartRequested(session_id=self.session_id,
                response_id=self._response_id, **self._response_meta), mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        logging.getLogger(__name__).info("latency_answer %s", json.dumps({
            "session_id": self.session_id, "request_id": event.request_id,
            "response_id": self._response_id, "at_monotonic": time.monotonic(), "text": text}))
        self._response_text += text
        await self.event_bus.publish(LLMAgentResponseUpdate(session_id=self.session_id,
            response_id=self._response_id, text=self._response_text, **self._response_meta),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        await self.event_bus.publish(TurnTTSTextAppendRequested(session_id=self.session_id,
            response_id=self._response_id, text=self._filter_for_tts(text), **self._response_meta),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

    async def _finish_answer(self) -> None:
        """Close text input once when the model enters thinking, preserving playback."""
        if not self._response_id:
            return
        response_id, text, meta = self._response_id, self._response_text, dict(self._response_meta)
        self._response_id = ""
        self._response_text = ""
        await self.event_bus.publish(LLMAgentResponseFinish(session_id=self.session_id,
            response_id=response_id, text=text, **meta), mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        await self.event_bus.publish(TurnTTSFlushRequested(session_id=self.session_id,
            response_id=response_id, **meta), mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

    async def _stop_answer(self, reason: str) -> None:
        """Stop unplayed output and preserve confirmed heard text as a separate fact."""
        response_id = self._response_id or self._playback_response_id
        if not response_id:
            return
        meta = dict(self._response_meta if self._response_id else self._playback_meta)
        self._response_id = ""
        self._response_text = ""
        self._playback_response_id = ""
        meta["reason"] = reason
        await self.event_bus.publish(TurnTTSStopRequested(session_id=self.session_id,
            response_id=response_id, **meta), mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

    @Manager.event_handler(TTSStarted)
    async def _started(self, event: TTSStarted) -> None:
        """Record the existing playback manager's delivery boundary."""
        if event.session_id == self.session_id and event.response_id == self._response_id:
            self._delivering = True

    @Manager.event_handler(ResponseUpdate)
    @Manager.event_handler(ResponseFinish)
    async def _heard(self, event: ResponseUpdate | ResponseFinish) -> None:
        """Keep playback confirmations without reinserting them as new model inputs."""
        if event.session_id == self.session_id:
            previous = self.heard.get(event.response_id, "")
            if event.text.startswith(previous):
                self.heard[event.response_id] = event.text

    @Manager.event_handler(TTSResponseClosed)
    async def _closed_response(self, event: TTSResponseClosed) -> None:
        """Release an unexpectedly closed active answer without fabricating heard text."""
        if event.session_id != self.session_id:
            return
        if event.response_id == self._playback_response_id:
            self._playback_response_id = ""
        if event.response_id == self._response_id:
            self._response_id = ""
            self._response_text = ""

    async def _publish(self, event_type: type, event: DuplexMicroTurnReady, **payload: Any) -> None:
        """Publish protocol observations with the current micro-turn identity."""
        await self.event_bus.publish(event_type(session_id=self.session_id,
            request_id=event.request_id, turn_id=event.turn_id, segment_id=event.segment_id,
            prefix_version=event.prefix_version, **payload), mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

    async def _error(self, event: DuplexMicroTurnReady, code: str, raw: str, reason: str) -> None:
        """Expose protocol and service failures without selecting a substitute state."""
        await self._publish(DuplexProtocolError, event, response_id=self._response_id,
                            error_code=code, raw_output=raw, reason=reason)

    async def shutdown(self) -> None:
        """Cancel inference before stopping remaining audio through native managers."""
        self._closed = True
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._stop_answer("shutdown")
        if isinstance(self.client, DuplexModelClient):
            await self.client.release()
