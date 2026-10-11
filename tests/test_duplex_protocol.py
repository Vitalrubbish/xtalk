"""Tests for the DuplexCascade A protocol and timeline recorder."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from typing import AsyncIterator
from xtalk.duplex_control.protocol import (
    EOS,
    ControlToken,
    ProtocolParseError,
    observe_system_micro_turn,
    parse_system_micro_turn,
    serialize_user_micro_turn,
)
from xtalk.duplex_control.state import DuplexCorrelation
from xtalk.duplex_control.timeline import DuplexTimelineRecorder
from xtalk.serving.event_bus import EventBus, EventDispatchMode
from xtalk.serving.events import (
    ConsumeLLMAgentGenerationRequested,
    DuplexProtocolError,
    DuplexProtocolParsed,
    LLMAgentResponseFinish,
    LLMAgentResponseUpdate,
    LLMFirstChunk,
    TTSChunkReady,
    TTSResponseClosed,
    TTSStarted,
    TurnTTSFlushRequested,
    TurnTTSStartRequested,
    TurnTTSTextAppendRequested,
)
from xtalk.models import Models
from xtalk.models.agents.interfaces import AgentOutput
from xtalk.serving.modules.llm_agent_generation_manager import (
    LLMAgentConsumptionManager,
)
from xtalk.serving.modules.tts_playback_manager import TTSPlaybackManager


class DuplexProtocolTests(unittest.TestCase):
    """Verify exact token boundaries and safe parser failures."""

    def test_serializes_silence_and_text_with_eos(self) -> None:
        self.assertEqual(serialize_user_micro_turn(""), "<no voice><EOS>")
        self.assertEqual(serialize_user_micro_turn("hello"), "hello<EOS>")

    def test_finish_speaking_carries_answer_text(self) -> None:
        parsed = parse_system_micro_turn(
            "<user finish speaking>Hello there<EOS>"
        )
        self.assertIs(parsed.control_token, ControlToken.USER_FINISH_SPEAKING)
        self.assertEqual(parsed.response_text, "Hello there")

    def test_wait_states_end_immediately(self) -> None:
        for token in ControlToken:
            suffix = "answer" if token is ControlToken.USER_FINISH_SPEAKING else ""
            parsed = parse_system_micro_turn(f"{token.value}{suffix}{EOS}")
            self.assertEqual(parsed.control_token, token)

    def test_rejects_missing_eos_unknown_and_extra_text(self) -> None:
        cases = (
            ("<user is thinking>", "missing_eos"),
            ("<unknown><EOS>", "unknown_control_token"),
            ("<user backchannel>okay<EOS>", "unexpected_response_text"),
            ("<user finish speaking><EOS>", "missing_response_text"),
            ("answer<EOS>", "missing_control_token"),
            ("<system backchannel><EOS>", "unknown_control_token"),
            ("<user is speaking><user is thinking><EOS>", "unexpected_token"),
            ("<user is speaking><EOS><EOS>", "unexpected_token"),
            ("<user is thinking><EOS>tail", "missing_eos"),
        )
        for raw, code in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(ProtocolParseError) as ctx:
                    parse_system_micro_turn(raw)
                self.assertEqual(ctx.exception.code, code)
                self.assertEqual(ctx.exception.raw_output, raw)


class DuplexTimelineTests(unittest.IsolatedAsyncioTestCase):
    """Verify the recorder keeps raw protocol facts and delivery boundaries."""

    async def test_records_protocol_and_tts_events_without_audio_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event_bus = EventBus()
            recorder = DuplexTimelineRecorder(
                event_bus,
                "session",
                {"duplex_timeline_dir": directory},
            )
            await event_bus.publish(
                DuplexProtocolParsed(
                    session_id="session",
                    request_id="request-1",
                    turn_id=4,
                    segment_id=2,
                    prefix_version=3,
                    state_token="<user finish speaking>",
                    response_text="answer",
                    raw_output="<user finish speaking>answer<EOS>",
                ),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
            )
            await event_bus.publish(
                TTSChunkReady(
                    session_id="session",
                    response_id="response-1",
                    audio_chunk=b"audio",
                ),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
            )
            await event_bus.publish(
                TTSStarted(session_id="session", response_id="response-1"),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
            )
            await recorder.shutdown()
            await event_bus.shutdown()

            lines = Path(recorder.path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 3)
            records = [json.loads(line) for line in lines]
            self.assertEqual(records[0]["raw_output"], "<user finish speaking>answer<EOS>")
            self.assertEqual(records[0]["prefix_version"], 3)
            self.assertEqual(records[0]["error_code"], "")
            self.assertEqual(records[0]["sequence"], 1)
            self.assertEqual(records[1]["response_id"], "response-1")
            self.assertNotIn("audio_chunk", records[1])
            self.assertEqual(records[2]["event_type"], TTSStarted.TYPE)
            self.assertTrue(all(record["monotonic_timestamp"] >= 0 for record in records))

    async def test_records_protocol_error_code_and_unsubscribes_on_shutdown(self) -> None:
        """Persist protocol error categories and make shutdown idempotent."""

        with tempfile.TemporaryDirectory() as directory:
            event_bus = EventBus()
            recorder = DuplexTimelineRecorder(
                event_bus,
                "session",
                {"duplex_timeline_dir": directory},
            )
            await event_bus.publish(
                DuplexProtocolError(
                    session_id="session",
                    request_id="request-1",
                    error_code="missing_eos",
                    raw_output="<user is thinking>",
                ),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
            )
            await recorder.shutdown()
            await recorder.shutdown()
            await event_bus.publish(
                DuplexProtocolError(
                    session_id="session",
                    request_id="request-2",
                    error_code="unknown_control_token",
                    raw_output="<unknown><EOS>",
                ),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
            )
            await event_bus.shutdown()

            records = [
                json.loads(line)
                for line in Path(recorder.path).read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(records[0]["error_code"], "missing_eos")
            self.assertEqual(records[0]["sequence"], 1)

    async def test_generation_and_playback_keep_one_correlation(self) -> None:
        """Carry one request correlation through generation and settlement."""

        async def stream() -> AsyncIterator[AgentOutput]:
            yield "hello"

        event_bus = EventBus(enable_history=True)
        manager = LLMAgentConsumptionManager(event_bus, "session", Models())
        await manager._handle_generation_request(
            ConsumeLLMAgentGenerationRequested(
                session_id="session",
                stream=stream(),
                request_id="request-1",
                turn_id=4,
                segment_id=2,
                prefix_version=3,
                state_token="<user finish speaking>",
            )
        )
        for _ in range(20):
            if event_bus.get_history(event_type=LLMAgentResponseFinish.TYPE):
                break
            await asyncio.sleep(0)

        first_chunk = event_bus.get_history(event_type=LLMFirstChunk.TYPE)[0]
        update = event_bus.get_history(event_type=LLMAgentResponseUpdate.TYPE)[0]
        start = event_bus.get_history(event_type=TurnTTSStartRequested.TYPE)[0]
        append = event_bus.get_history(event_type=TurnTTSTextAppendRequested.TYPE)[0]
        flush = event_bus.get_history(event_type=TurnTTSFlushRequested.TYPE)[0]
        finish = event_bus.get_history(event_type=LLMAgentResponseFinish.TYPE)[0]
        self.assertTrue(first_chunk.response_id)
        self.assertEqual(
            [
                event.request_id
                for event in (first_chunk, update, start, append, flush, finish)
            ],
            ["request-1"] * 6,
        )
        self.assertEqual(
            [event.response_id for event in (update, start, append, flush, finish)],
            [update.response_id] * 5,
        )
        await manager.shutdown()
        await event_bus.shutdown()

    async def test_playback_update_and_close_keep_correlation(self) -> None:
        """Carry generation metadata into playback-confirmed events."""

        event_bus = EventBus(enable_history=True)
        manager = TTSPlaybackManager(event_bus, "session")
        metadata = {
            "request_id": "request-1",
            "turn_id": 4,
            "segment_id": 2,
            "prefix_version": 3,
            "state_token": "<user finish speaking>",
            "reason": "test",
        }
        await event_bus.publish(
            LLMAgentResponseUpdate(
                session_id="session",
                response_id="response-1",
                text="hello",
                **metadata,
            ),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
        )
        await event_bus.publish(
            TTSStarted(
                session_id="session",
                response_id="response-1",
                **metadata,
            ),
            mode=EventDispatchMode.WAIT_UNTIL_COMPLETE,
        )
        await manager._emit_response_update("hello")
        await manager._close_response("response-1")
        response_update = event_bus.get_history(event_type="response.update")[0]
        response_closed = event_bus.get_history(event_type=TTSResponseClosed.TYPE)[0]
        for event in (response_update, response_closed):
            self.assertEqual(event.request_id, "request-1")
            self.assertEqual(event.prefix_version, 3)
            self.assertEqual(event.state_token, "<user finish speaking>")
        await manager.shutdown()
        await event_bus.shutdown()

    async def test_observer_publishes_parsed_and_error_with_same_correlation(self) -> None:
        """Preserve source identifiers and raw output in both outcomes."""
        bus = EventBus(enable_history=True)
        correlation = DuplexCorrelation(
            session_id="session", turn_id=4, segment_id=2,
            prefix_version=3, request_id="request-1", response_id="response-1",
        )
        parsed = await observe_system_micro_turn(
            bus, correlation, "<user is thinking><EOS>",
        )
        rejected = await observe_system_micro_turn(
            bus, correlation, "<unknown><EOS>",
        )
        self.assertIsNotNone(parsed)
        self.assertIsNone(rejected)
        success = bus.get_history(event_type=DuplexProtocolParsed.TYPE)[0]
        failure = bus.get_history(event_type=DuplexProtocolError.TYPE)[0]
        self.assertEqual(success.request_id, failure.request_id)
        self.assertEqual(success.prefix_version, failure.prefix_version)
        self.assertEqual(failure.error_code, "unknown_control_token")
        self.assertEqual(failure.raw_output, "<unknown><EOS>")
        await bus.shutdown()


if __name__ == "__main__":
    unittest.main()
