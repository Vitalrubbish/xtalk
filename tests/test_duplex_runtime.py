"""Behavioral regressions for official micro-turn scheduling and execution."""

import asyncio
import unittest
from types import SimpleNamespace

from xtalk.duplex_control.micro_turn import MicroTurnAssembler
from xtalk.duplex_control.model_client import GenerationEnd
from xtalk.duplex_control.protocol import WIRE_EOS, WireMicroTurnParser, ProtocolParseError
from xtalk.duplex_control.runtime_adapter import DuplexRuntimeAdapter
from xtalk.duplex_control.service import duplex_manager_classes
from xtalk.models import Models, TTS
from xtalk.serving.event_bus import EventBus, EventDispatchMode
from xtalk.serving.events import (
    ASRResultFinal, ASRResultPartial, DuplexMicroTurnReady, DuplexProtocolError, DuplexProtocolParsed,
    LLMAgentResponseFinish, LLMAgentResponseUpdate, ResponseUpdate, ResponseFinish,
    TurnTTSStartRequested, TurnTTSStopRequested, TurnTTSTextAppendRequested,
    TurnTTSFlushRequested, VADSpeechStart, TurnDetectorStopSpeaking,
    TTSChunkPlayed, TTSChunkReady, TTSFinished, TTSPlaybackFinished,
)
from xtalk.serving.service import DefaultService, Service
from xtalk.serving.modules.llm_agent_context_manager import LLMAgentContextManager
from xtalk.serving.modules.turn_taking_manager import TurnTakingManager


class ScriptedClient:
    """Supply raw official output fragments and capture exact inference prompts."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts = []
        self.active = 0
        self.max_active = 0
        self.entered = asyncio.Event()
        self.release = None

    async def stream(self, prompt):
        """Yield one scripted result with optional blocked inference."""
        self.prompts.append(prompt)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.entered.set()
        try:
            if self.release:
                await self.release.wait()
            output = self.outputs.pop(0)
            if isinstance(output, BaseException):
                raise output
            for fragment in output:
                yield fragment
                await asyncio.sleep(0)
        finally:
            self.active -= 1


class WireParserTests(unittest.TestCase):
    """Validate actual released token spelling and fragmented wire output."""

    def test_every_character_split_and_continuation(self):
        """Never leak markers to speech across arbitrary transport boundaries."""
        raw = '<|user finish talking|>Hello world.<|im_end|>'
        for split in range(len(raw) + 1):
            parser = WireMicroTurnParser()
            self.assertEqual(parser.feed(raw[:split]) + parser.feed(raw[split:]), 'Hello world.')
            parser.finish()
        parser = WireMicroTurnParser(True)
        self.assertEqual(parser.feed(' more<|im_end|>'), ' more')
        parser.finish()
        self.assertIsNone(parser.control)

    def test_control_only_and_forbidden_outputs(self):
        """Wait states contain no speech; beta and missing EOS are rejected."""
        for token in ('user is talking', 'user interruption', 'user backchannel', 'user is thinking'):
            parser = WireMicroTurnParser()
            self.assertEqual(parser.feed(f'<|{token}|><|im_end|>'), '')
            parser.finish()
        for raw in ('<|assistant_backchannel|><|im_end|>', 'Hello<|im_end|>',
                    '<|user backchannel|>oops<|im_end|>', '<|user finish talking|><|im_end|>'):
            with self.assertRaises(ProtocolParseError):
                parser = WireMicroTurnParser()
                parser.feed(raw)
                parser.finish()
        parser = WireMicroTurnParser()
        parser.feed('<|user is talking|>')
        with self.assertRaises(ProtocolParseError):
            parser.finish()

    def test_budget_limit_preserves_answer_only(self):
        """Official max-token cuts continue history without invented EOS."""
        parser = WireMicroTurnParser()
        parser.feed('<|user finish talking|>unfinished')
        parser.finish('length')
        self.assertFalse(parser.ended)
        for active in (False, True):
            parser = WireMicroTurnParser(active)
            parser.feed('<|user is talking|>')
            with self.assertRaises(ProtocolParseError):
                parser.finish('length')


class DuplexRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """Exercise real event dispatch while replacing only model inference."""

    def setUp(self):
        self.bus = EventBus(enable_history=True, max_history=10000)
        self.addAsyncCleanup(self.bus.shutdown)
        self.assembler = MicroTurnAssembler(self.bus, 'session', {'duplex_auto_tick': False})
        self.addAsyncCleanup(self.assembler.shutdown)

    def adapter(self, *outputs):
        """Register an adapter with a scripted official model service."""
        client = ScriptedClient(*outputs)
        adapter = DuplexRuntimeAdapter(self.bus, 'session', {'duplex_model_client': client})
        self.addAsyncCleanup(adapter.shutdown)
        return adapter, client

    async def send(self, text, final=False, **kwargs):
        """Publish cumulative input without an implicit inference flush."""
        cls = ASRResultFinal if final else ASRResultPartial
        await self.bus.publish(cls(session_id='session', text=text, **kwargs),
                               mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

    def events(self, cls):
        """Return currently recorded events of one type."""
        return self.bus.get_history(event_type=cls.TYPE)

    async def test_first_text_deltas_silence_and_final_dedup(self):
        """Only scheduled windows reach LLM; final never repeats the prefix."""
        adapter, client = self.adapter(*[['<|user is talking|><|im_end|>']] * 4)
        self.assertIsNone(await self.assembler.flush())
        await self.send('Hi')
        self.assertFalse(client.prompts)
        await self.assembler.flush()
        await self.send('Hi there')
        await self.assembler.flush()
        await self.send('Hi there', final=True)
        await self.assembler.flush()
        await self.assembler.flush()
        users = [x['content'] for x in adapter.history if x['role'] == 'user']
        self.assertEqual(users, ['Hi<|im_end|>\n', ' there<|im_end|>\n',
                                 '<|no voice|><|im_end|>\n', '<|no voice|><|im_end|>\n'])
        self.assertEqual(client.prompts[0], '<|im_start|>user\nHi<|im_end|>\n<|im_start|>assistant\n')
        self.assertEqual(len(self.events(DuplexMicroTurnReady)), 4)

    async def test_clock_starts_after_text_and_does_not_event_flush(self):
        """The real clock waits one configured interval after first nonblank ASR."""
        await self.assembler.shutdown()
        self.assembler = MicroTurnAssembler(self.bus, 'session', {
            'duplex_micro_turn_seconds': 0.05})
        self.addAsyncCleanup(self.assembler.shutdown)
        ready = asyncio.Event()
        self.bus.subscribe(DuplexMicroTurnReady, lambda event: ready.set())
        await asyncio.sleep(0.06)
        self.assertFalse(ready.is_set())
        await self.send('hello')
        await asyncio.sleep(0.01)
        self.assertFalse(ready.is_set())
        await asyncio.wait_for(ready.wait(), 0.2)

    async def test_slow_model_aggregates_input_without_parallel_calls(self):
        """Incoming revisions remain available while previous inference is running."""
        adapter, client = self.adapter(['<|user is talking|><|im_end|>'],
                                       ['<|user is talking|><|im_end|>'])
        client.release = asyncio.Event()
        await self.send('A')
        first = asyncio.create_task(self.assembler.flush())
        await client.entered.wait()
        await self.send('ABC')
        second = asyncio.create_task(self.assembler.flush())
        await asyncio.sleep(0)
        self.assertEqual(len(client.prompts), 1)
        client.release.set()
        await asyncio.gather(first, second)
        self.assertEqual(client.max_active, 1)
        self.assertIn('BC<|im_end|>', client.prompts[1])
        self.assertNotIn('ABC<|im_end|>', client.prompts[1])

    async def test_response_continues_and_backchannel_does_not_restart_tts(self):
        """One response and one synthesis stream span answer and user backchannel."""
        adapter, client = self.adapter(['<|user finish talking|>Hello<|im_end|>'],
            [' world<|im_end|>'], ['<|user backchannel|><|im_end|>'],
            ['!<|im_end|>'], ['<|user is thinking|><|im_end|>'])
        await self.send('question')
        for _ in range(5):
            await self.assembler.flush()
        self.assertEqual(len(self.events(TurnTTSStartRequested)), 1)
        self.assertEqual([x.text for x in self.events(TurnTTSTextAppendRequested)], ['Hello', ' world', '!'])
        self.assertEqual(self.events(LLMAgentResponseFinish)[0].text, 'Hello world!')
        self.assertEqual(len(self.events(TurnTTSFlushRequested)), 1)
        self.assertFalse(self.events(TurnTTSStopRequested))
        ids = {x.response_id for x in self.events(LLMAgentResponseUpdate)}
        self.assertEqual(len(ids), 1)
        self.assertFalse(adapter._response_id)

    async def test_interrupt_after_thinking_still_stops_pending_audio(self):
        """Closing text input does not lose ownership of unplayed remaining audio."""
        adapter, _ = self.adapter(['<|user finish talking|>Hello<|im_end|>'],
            ['<|user is thinking|><|im_end|>'], ['<|user interruption|><|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        response_id = adapter._response_id
        await self.bus.publish(ResponseUpdate(session_id='session', response_id=response_id, text='Hel'),
                               mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        await self.assembler.flush()
        await self.assembler.flush()
        self.assertEqual(self.events(TurnTTSStopRequested)[0].response_id, response_id)
        self.assertEqual(adapter.heard[response_id], 'Hel')

    async def test_rewrite_repairs_user_history_and_keeps_system_history(self):
        """Cumulative ASR replacement changes its input, never the assistant facts."""
        adapter, client = self.adapter(*[['<|user is talking|><|im_end|>']] * 3)
        await self.send('Meet Monday')
        await self.assembler.flush()
        await self.send('Meet Tuesday')
        snapshot = await self.assembler.flush()
        self.assertEqual(snapshot.revision_kind, 'REWRITE')
        self.assertNotIn('Monday', client.prompts[-1])
        self.assertIn('Meet Tuesday', client.prompts[-1])
        self.assertEqual(len([x for x in adapter.history if x['role'] == 'assistant']), 2)
        await self.send('Meet Tuesday at noon')
        await self.assembler.flush()
        self.assertIn(' at noon<|im_end|>', client.prompts[-1])

    async def test_malformed_output_stops_unplayed_audio(self):
        """Malformed output exposes raw evidence and creates no substitute decision."""
        adapter, _ = self.adapter(['<|user finish talking|>Hello<|im_end|>'],
                                   ['<|assistant_backchannel|><|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        await self.assembler.flush()
        self.assertEqual(self.events(DuplexProtocolError)[0].error_code, 'unknown_control_token')
        self.assertEqual(len(self.events(TurnTTSStopRequested)), 1)
        self.assertEqual(len(self.events(TurnTTSStartRequested)), 1)

    async def test_duplicate_request_and_shutdown_cancel_generation(self):
        """Duplicate inputs do not infer twice and shutdown releases blocked inference."""
        adapter, client = self.adapter(['<|user is talking|><|im_end|>'],
                                       ['<|user is talking|><|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        event = self.events(DuplexMicroTurnReady)[0]
        await self.bus.publish(event, mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        self.assertEqual(len(client.prompts), 1)
        self.assertEqual(self.events(DuplexProtocolError)[0].error_code, 'duplicate_request')
        client.entered.clear()
        client.release = asyncio.Event()
        pending = asyncio.create_task(self.assembler.flush())
        await client.entered.wait()
        await adapter.shutdown()
        self.assertTrue(pending.cancelled())
        self.assertEqual(client.active, 0)

    async def test_service_disables_native_semantic_paths(self):
        """The service filters native semantic triggers and retains its TTS owner."""
        prototype = DefaultService(models=Models(), service_config={'duplex_enabled': True})
        classes = prototype._manager_classes
        self.assertIn(MicroTurnAssembler, classes)
        self.assertIn(DuplexRuntimeAdapter, classes)
        self.assertNotIn(LLMAgentContextManager, classes)
        self.assertNotIn(TurnTakingManager, classes)
        self.assertEqual(duplex_manager_classes(classes), classes)
        original = DefaultService(models=Models())
        self.assertIn(LLMAgentContextManager, original._manager_classes)

    async def test_native_tts_playback_chain_keeps_answer_identity(self):
        """Run native synthesis/coordinator/playback across two model micro-turns."""
        from xtalk.serving.modules.tts_manager import TTSManager
        from xtalk.serving.modules.tts_response_coordinator import TTSResponseCoordinator
        from xtalk.serving.modules.tts_playback_manager import TTSPlaybackManager

        class PCMModel:
            """Return deterministic audio for native sentence synthesis."""

            async def async_synthesize_stream(self, text):
                """Yield 200 ms of PCM per accepted text segment."""
                yield b'\x00\x00' * 9600

        models = Models({TTS: PCMModel()})
        synthesis = TTSManager(self.bus, 'session', models)
        coordinator = TTSResponseCoordinator(self.bus, 'session')
        playback = TTSPlaybackManager(self.bus, 'session')
        self.addAsyncCleanup(synthesis.shutdown)
        self.addAsyncCleanup(coordinator.shutdown)
        self.addAsyncCleanup(playback.shutdown)
        adapter, _ = self.adapter(['<|user finish talking|>你好。<|im_end|>'],
            ['再见。<|im_end|>'], ['<|user is thinking|><|im_end|>'])
        finished = asyncio.Event()

        async def acknowledge(event):
            """Confirm actual delivered chunks through the native playback bus."""
            await self.bus.publish(TTSChunkPlayed(session_id='session', response_id=event.response_id),
                                   mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)

        self.bus.subscribe(TTSChunkReady, acknowledge, priority=-20)
        self.bus.subscribe(TTSFinished, lambda event: finished.set())
        await self.send('hello')
        for _ in range(3):
            await self.assembler.flush()
        await asyncio.wait_for(finished.wait(), 2)
        response_id = self.events(TurnTTSStartRequested)[0].response_id
        await self.bus.publish(TTSPlaybackFinished(session_id='session', response_id=response_id),
                               mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        self.assertEqual(len(self.events(TurnTTSStartRequested)), 1)
        self.assertEqual(self.events(ResponseFinish)[0].text, '你好。再见。')
        self.assertEqual(adapter.heard[response_id], '你好。再见。')
        self.assertEqual(self.bus.get_stats()['errors_occurred'], 0)

    async def test_stale_snapshot_is_rejected_without_a_model_call(self):
        """A delayed obsolete transport event cannot start a fresh answer."""
        from dataclasses import replace
        adapter, client = self.adapter(['<|user is talking|><|im_end|>'])
        await self.send('hello')
        await self.assembler.flush()
        event = self.events(DuplexMicroTurnReady)[0]
        stale = replace(event, prefix_version=event.prefix_version - 1, request_id='stale')
        await self.bus.publish(stale, mode=EventDispatchMode.WAIT_UNTIL_COMPLETE)
        self.assertEqual(len(client.prompts), 1)
        self.assertEqual(self.events(DuplexProtocolError)[0].error_code, 'stale_prefix')

    async def test_interruption_closes_stream_and_micro_turn_without_eos(self):
        """An interruption marker cancels the live stream without waiting for EOS."""
        adapter, _ = self.adapter(['<|user finish talking|>Hello<|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        response_id = adapter._response_id

        class StalledInterruption:
            """Expose whether adapter closure reaches a stream stalled after its marker."""

            def __init__(self):
                self.closed = asyncio.Event()
                self.waiting_after_partial = asyncio.Event()
                self.marker_emitted = asyncio.Event()
                self.release_partial = asyncio.Event()
                self.release_after_marker = asyncio.Event()
                self.resumed_after_marker = False

            def stream(self, prompt):
                """Yield an interruption then wait forever unless the adapter closes it."""
                async def output():
                    try:
                        yield '<|user inter'
                        self.waiting_after_partial.set()
                        await self.release_partial.wait()
                        self.marker_emitted.set()
                        yield 'ruption|>'
                        self.resumed_after_marker = True
                        await self.release_after_marker.wait()
                        yield '<|im_end|>'
                    finally:
                        self.closed.set()

                return output()

        interrupted = StalledInterruption()
        adapter.client = interrupted
        task = asyncio.create_task(self.assembler.flush())
        await asyncio.wait_for(interrupted.waiting_after_partial.wait(), 1)
        self.assertFalse(self.events(TurnTTSStopRequested))
        self.assertFalse(task.done())
        interrupted.release_partial.set()
        await asyncio.wait_for(interrupted.marker_emitted.wait(), 1)
        await asyncio.wait_for(task, 1)
        await asyncio.wait_for(interrupted.closed.wait(), 1)
        self.assertEqual(len(self.events(TurnTTSStopRequested)), 1)
        self.assertEqual(self.events(TurnTTSStopRequested)[0].response_id, response_id)
        self.assertFalse(interrupted.resumed_after_marker)
        self.assertFalse(interrupted.release_after_marker.is_set())
        self.assertFalse(task.cancelled())
        parsed = self.events(DuplexProtocolParsed)[-1]
        self.assertEqual(parsed.raw_output, '<|user interruption|>')
        self.assertEqual(parsed.state_token, '<|user interruption|>')
        self.assertEqual(parsed.response_id, response_id)
        self.assertEqual(parsed.reason, 'interruption')
        self.assertFalse(self.events(DuplexProtocolError))
        self.assertEqual(adapter.history[-1], {
            'role': 'assistant', 'content': '<|user interruption|>' + WIRE_EOS + '\n',
        })
        continuation = ScriptedClient(['<|user is talking|><|im_end|>'])
        adapter.client = continuation
        await self.assembler.flush()
        self.assertIn('<|user interruption|><|im_end|>\n', continuation.prompts[0])

    async def test_user_backchannel_can_include_same_micro_turn_continuation(self):
        """Official backchannel markers preserve and continue the current answer."""
        adapter, _ = self.adapter(['<|user finish talking|>Hello<|im_end|>'],
            ['<|user back', 'channel|> world<|im_', 'end|>'],
            ['<|user is thinking|><|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        await self.send('q okay')
        await self.assembler.flush()
        await self.assembler.flush()
        self.assertEqual(len(self.events(TurnTTSStartRequested)), 1)
        self.assertEqual([x.text for x in self.events(TurnTTSTextAppendRequested)], ['Hello', ' world'])
        self.assertEqual(self.events(LLMAgentResponseFinish)[0].text, 'Hello world')
        self.assertFalse(self.events(TurnTTSStopRequested))
        self.assertFalse(self.events(DuplexProtocolError))
