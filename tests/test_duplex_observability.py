"""Regression tests for A1 correlation and delivery observation."""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import AsyncIterator

from xtalk.duplex_control.timeline import DuplexTimelineRecorder
from xtalk.models import Agent, Models, TTS
from xtalk.models.agents import AgentTurnBoundary
from xtalk.serving.event_bus import EventBus, EventDispatchMode
from xtalk.serving.events import (
    ASRResultFinal, ASRResultPartial, ConsumeLLMAgentGenerationRequested,
    LLMAgentResponseFinish, LLMAgentResponseUpdate, LLMFirstChunk,
    ResponseFinish, ResponseUpdate, TTSChunkPlayed, TTSChunkReady,
    TTSFinished, TTSPlaybackFinished, TTSResponseClosed, TTSStarted,
    TTSStopped, TurnTTSStartRequested, TurnTTSStopRequested,
)
from xtalk.serving.modules.llm_agent_context_manager import LLMAgentContextManager
from xtalk.serving.modules.llm_agent_generation_manager import LLMAgentConsumptionManager
from xtalk.serving.modules.tts_manager import TTSManager
from xtalk.serving.modules.tts_playback_manager import TTSPlaybackManager
from xtalk.serving.modules.tts_response_coordinator import TTSResponseCoordinator
from xtalk.serving.service import Service


class _PCMModel:
    """Return one short deterministic PCM buffer without a model service."""

    async def async_synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Yield 200 milliseconds of mono PCM."""
        yield b'\x00\x00' * 9600


async def _stream(*items):
    """Yield supplied text and response boundaries."""
    for item in items:
        yield item


class DuplexObservabilityTests(unittest.IsolatedAsyncioTestCase):
    """Verify correlation through native managers and service lifecycle."""

    async def test_pcm_delivery_and_playback_settlement_share_correlation(self):
        """Run generation, synthesis and confirmed playback on one event bus."""
        with tempfile.TemporaryDirectory() as directory:
            bus = EventBus(enable_history=True)
            recorder = DuplexTimelineRecorder(bus, 'session', {'duplex_timeline_dir': directory})
            models = Models({TTS: _PCMModel()})
            generation = LLMAgentConsumptionManager(bus, 'session', models)
            synthesis = TTSManager(bus, 'session', models)
            playback = TTSPlaybackManager(bus, 'session')
            coordinator = TTSResponseCoordinator(bus, 'session')
            metadata = dict(request_id='request', response_id='reserved',
                            turn_id=5, segment_id=2, prefix_version=7)
            async def acknowledge(event):
                await bus.publish(TTSChunkPlayed(session_id='session', response_id=event.response_id),
                                  mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
            bus.subscribe(TTSChunkReady, acknowledge, priority=-20)
            await bus.publish(ASRResultPartial(session_id='session', text='hello',
                              **{k: v for k, v in metadata.items() if k != 'response_id'}),
                              mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
            await bus.publish(ConsumeLLMAgentGenerationRequested(
                session_id='session', stream=_stream('你好。'), **metadata),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
            async def wait_finished():
                while not bus.get_history(event_type=TTSFinished.TYPE):
                    await asyncio.sleep(0.001)
            await asyncio.wait_for(wait_finished(), timeout=2)
            await bus.publish(TTSPlaybackFinished(session_id='session', response_id='reserved'),
                              mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
            for event_type in (LLMFirstChunk, LLMAgentResponseUpdate, LLMAgentResponseFinish,
                               TTSStarted, TTSChunkReady, TTSFinished, ResponseUpdate,
                               ResponseFinish, TTSResponseClosed):
                events = bus.get_history(event_type=event_type.TYPE)
                self.assertTrue(events, event_type.TYPE)
                for event in events:
                    for key, value in metadata.items():
                        self.assertEqual(vars(event)[key], value, (event_type.TYPE, key))
            settled = bus.get_history(event_type=ResponseFinish.TYPE)[0]
            self.assertEqual(settled.text, '你好。')
            self.assertFalse(playback._correlation_by_response)
            self.assertFalse(coordinator._correlations)
            self.assertEqual(bus.get_stats()['errors_occurred'], 0)
            await generation.shutdown()
            await synthesis.shutdown()
            await playback.shutdown()
            await coordinator.shutdown()
            await bus.shutdown()
            await recorder.shutdown()
            rows = [json.loads(line) for line in recorder.path.read_text().splitlines()]
            self.assertEqual([row['sequence'] for row in rows], list(range(1, len(rows) + 1)))
            self.assertTrue(any(row['event_type'] == ResponseFinish.TYPE for row in rows))

    async def test_concurrent_streams_and_later_boundary_have_distinct_responses(self):
        """Keep request metadata isolated and consume reserved identity once."""
        bus = EventBus(enable_history=True)
        manager = LLMAgentConsumptionManager(bus, 'session', Models())
        self.addAsyncCleanup(bus.shutdown)
        self.addAsyncCleanup(manager.shutdown)
        for number in (1, 2):
            await manager._handle_generation_request(ConsumeLLMAgentGenerationRequested(
                session_id='session', stream=_stream('first', AgentTurnBoundary(), 'second'),
                request_id=f'request-{number}', response_id=f'reserved-{number}',
                turn_id=number, prefix_version=number + 10))
        await asyncio.gather(*list(manager._active_streams))
        finals = bus.get_history(event_type=LLMAgentResponseFinish.TYPE)
        self.assertEqual(len(finals), 4)
        self.assertEqual(len({event.response_id for event in finals}), 4)
        for number in (1, 2):
            responses = [event for event in finals if event.request_id == f'request-{number}']
            self.assertEqual(responses[0].response_id, f'reserved-{number}')
            self.assertNotEqual(responses[1].response_id, f'reserved-{number}')
            self.assertTrue(all(event.turn_id == number and event.prefix_version == number + 10
                                for event in responses))

    async def test_context_preserves_input_fields_without_reusing_feedback_response(self):
        """Copy input IDs while preserving the published source event."""
        bus = EventBus(enable_history=True)
        contexts = []
        def accept(context):
            contexts.append(context)
            return _stream()
        manager = LLMAgentContextManager(bus, 'session', Models({Agent: SimpleNamespace(async_accept=accept)}))
        await manager._handle_asr_result_final(ASRResultFinal(
            session_id='session', text='question', request_id='input',
            turn_id=3, segment_id=4, prefix_version=5))
        request = bus.get_history(event_type=ConsumeLLMAgentGenerationRequested.TYPE)[0]
        self.assertEqual((request.request_id, request.turn_id, request.segment_id, request.prefix_version),
                         ('input', 3, 4, 5))
        await manager._handle_response_finish(ResponseFinish(
            session_id='session', response_id='heard', text='answer'))
        feedback = bus.get_history(event_type=ConsumeLLMAgentGenerationRequested.TYPE)[-1]
        self.assertEqual(feedback.response_id, '')
        self.assertTrue(feedback.request_id)
        self.assertEqual(contexts[-1]['data']['response_id'], 'heard')
        await bus.shutdown()

    async def test_preemption_uses_each_response_metadata(self):
        """Carry B through preparation while stopping A with A's IDs."""
        bus = EventBus(enable_history=True)
        tts = TTSManager(bus, 'session', Models())
        coordinator = TTSResponseCoordinator(bus, 'session')
        self.addAsyncCleanup(bus.shutdown)
        self.addAsyncCleanup(tts.shutdown)
        self.addAsyncCleanup(coordinator.shutdown)
        for number in (1, 2):
            await bus.publish(TurnTTSStartRequested(
                session_id='session', response_id=f'response-{number}',
                request_id=f'request-{number}', prefix_version=number),
                mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        stopped = bus.get_history(event_type=TTSStopped.TYPE)[0]
        self.assertEqual((stopped.request_id, stopped.prefix_version, stopped.reason),
                         ('request-1', 1, 'response_preempted'))
        await bus.publish(TTSResponseClosed(session_id='session', response_id='response-1'),
                          mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        started = bus.get_history(event_type=TTSStarted.TYPE)[-1]
        self.assertEqual((started.response_id, started.request_id, started.prefix_version),
                         ('response-2', 'request-2', 2))

    async def test_service_switch_and_shutdown_tail(self):
        """Register once and retain background events emitted on shutdown."""
        with tempfile.TemporaryDirectory() as directory:
            disabled = Service(models=Models())
            self.assertNotIn(DuplexTimelineRecorder, disabled._manager_classes)
            enabled = Service(models=Models(), service_config={'duplex_timeline_enabled': True},
                              manager_classes=[DuplexTimelineRecorder])
            self.assertEqual(enabled._manager_classes.count(DuplexTimelineRecorder), 1)
            bus = EventBus()
            recorder = DuplexTimelineRecorder(bus, 'session', {'duplex_timeline_dir': directory})
            async def stop_producer():
                await bus.publish(ResponseFinish(session_id='session', text='heard'))
            enabled.event_bus = bus
            enabled._managers = [recorder, SimpleNamespace(shutdown=stop_producer)]
            await enabled.stop()
            self.assertTrue(recorder._output.closed)
            rows = [json.loads(line) for line in recorder.path.read_text().splitlines()]
            self.assertEqual(rows[0]['text'], 'heard')


if __name__ == '__main__':
    unittest.main()
