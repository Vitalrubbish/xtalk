"""Behavioral regressions for official micro-turn scheduling and execution."""

import asyncio
import unittest
from types import SimpleNamespace

from xtalk.duplex_control.micro_turn import MicroTurnAssembler
from xtalk.duplex_control.model_client import GenerationEnd
from xtalk.duplex_control.protocol import WireControl, WireMicroTurnParser, WireText
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
from xtalk.serving.modules.asr_manager import ASRManager
from xtalk.serving.modules.direct_audio_manager import DirectAudioManager
from xtalk.serving.modules.llm_agent_context_manager import LLMAgentContextManager
from xtalk.serving.modules.llm_agent_generation_manager import LLMAgentConsumptionManager
from xtalk.serving.modules.multi_speaker_turn_context_manager import MultiSpeakerTurnContextManager
from xtalk.serving.modules.tts_manager import TTSManager
from xtalk.serving.modules.tts_playback_manager import TTSPlaybackManager
from xtalk.serving.modules.turn_detector_manager import TurnDetectorManager
from xtalk.serving.modules.turn_taking_manager import TurnTakingManager
from xtalk.serving.modules.vad_manager import VADManager


class ScriptedClient:
    """Supply raw official output fragments and capture exact inference history."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts = []
        self.active = 0
        self.max_active = 0
        self.entered = asyncio.Event()
        self.release = None

    async def stream(self, history):
        """Yield one scripted result with optional blocked inference."""
        self.prompts.append(history)
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
            # The real service always reports the generated ids it decoded.
            if not any(isinstance(fragment, GenerationEnd) for fragment in output):
                yield GenerationEnd('stop', (151645,))
        finally:
            self.active -= 1


class WireParserTests(unittest.TestCase):
    """Validate released token spelling and official-tolerant wire output."""

    @staticmethod
    def _text(events):
        """Concatenate answer text from ordered wire events."""
        return ''.join(event.text for event in events if isinstance(event, WireText))

    def test_every_character_split_and_continuation(self):
        """Never leak markers to speech across arbitrary transport boundaries."""
        raw = '<|user finish talking|>Hello world.<|im_end|>'
        for split in range(len(raw) + 1):
            parser = WireMicroTurnParser()
            events = parser.feed(raw[:split]) + parser.feed(raw[split:])
            self.assertEqual(self._text(events), 'Hello world.')
            self.assertTrue(parser.ended)
        parser = WireMicroTurnParser()
        self.assertEqual(self._text(parser.feed(' more<|im_end|>')), ' more')
        parser.finish()
        self.assertIsNone(parser.control)

    def test_control_only_and_repeated_markers_are_tolerated(self):
        """Wait states carry no speech and repeats apply in order, never as errors."""
        for token in ('user is talking', 'user interruption', 'user backchannel', 'user is thinking'):
            parser = WireMicroTurnParser()
            events = parser.feed(f'<|{token}|><|im_end|>')
            self.assertEqual(self._text(events), '')
            self.assertTrue(parser.ended)
        parser = WireMicroTurnParser()
        events = parser.feed('<|user finish talking|><|user finish talking|>')
        self.assertEqual(
            [event.wire_token for event in events if isinstance(event, WireControl)],
            ['<|user finish talking|>', '<|user finish talking|>'],
        )
        self.assertEqual(self._text(events), '')

    def test_unknown_marker_and_missing_eos_are_plain_text(self):
        """Unknown spellings and unfinished turns are text, matching the release."""
        parser = WireMicroTurnParser()
        self.assertEqual(
            self._text(parser.feed('<|assistant_backchannel|>')), '<|assistant_backchannel|>')
        parser = WireMicroTurnParser()
        events = parser.feed('<|user backchannel|>oops<|im_end|>')
        self.assertEqual(self._text(events), 'oops')
        parser = WireMicroTurnParser()
        parser.feed('<|user is talking|>')
        parser.finish()
        self.assertFalse(parser.ended)

    def test_budget_limit_preserves_answer_only(self):
        """Official max-token cuts continue history without invented EOS."""
        parser = WireMicroTurnParser()
        events = parser.feed('<|user finish talking|>unfinished')
        parser.finish('length')
        self.assertEqual(self._text(events), 'unfinished')
        self.assertFalse(parser.ended)
        parser = WireMicroTurnParser()
        events = parser.feed('<|user is talking|>')
        parser.finish('length')
        self.assertEqual(self._text(events), '')
        self.assertFalse(parser.ended)


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
        users = [x['text'] for x in adapter.history if x['role'] == 'user']
        self.assertEqual(users, ['Hi', ' there', '', ''])
        self.assertEqual(client.prompts[0], [{'role': 'user', 'text': 'Hi'}])
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
        self.assertEqual(client.prompts[1][-1], {'role': 'user', 'text': 'BC'})

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
        last_history = client.prompts[-1]
        user_text = ''.join(turn['text'] for turn in last_history if turn['role'] == 'user')
        self.assertNotIn('Monday', user_text)
        self.assertIn('Meet Tuesday', user_text)
        self.assertEqual(len([x for x in adapter.history if x['role'] == 'assistant']), 2)
        await self.send('Meet Tuesday at noon')
        await self.assembler.flush()
        self.assertEqual(client.prompts[-1][-1], {'role': 'user', 'text': ' at noon'})

    async def test_unknown_marker_is_spoken_without_stopping_audio(self):
        """An unknown spelling is plain answer text, matching the released server."""
        adapter, _ = self.adapter(['<|user finish talking|>Hello<|im_end|>'],
                                   ['<|assistant_backchannel|><|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        await self.assembler.flush()
        self.assertFalse(self.events(DuplexProtocolError))
        self.assertEqual([x.text for x in self.events(TurnTTSTextAppendRequested)],
                         ['Hello', '<|assistant_backchannel|>'])
        self.assertFalse(self.events(TurnTTSStopRequested))

    async def test_repeated_control_tokens_apply_without_protocol_error(self):
        """Every released marker is applied in order instead of aborting the turn."""
        adapter, _ = self.adapter(['<|user finish talking|>Hello<|im_end|>'],
                                   ['<|user finish talking|><|user finish talking|>more<|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        await self.assembler.flush()
        parsed = [x for x in self.events(DuplexProtocolParsed)
                  if x.state_token == '<|user finish talking|>']
        self.assertEqual(len(parsed), 3)
        self.assertFalse(self.events(DuplexProtocolError))
        self.assertEqual([x.text for x in self.events(TurnTTSTextAppendRequested)],
                         ['Hello', 'more'])

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

    async def test_duplex_mode_removes_every_bypass_manager(self):
        """Every native semantic or direct-audio bypass is dropped in duplex mode."""
        retained = [ASRManager, TTSManager, TTSPlaybackManager, VADManager]
        bypass = [
            DirectAudioManager,
            LLMAgentContextManager,
            LLMAgentConsumptionManager,
            TurnTakingManager,
            TurnDetectorManager,
            MultiSpeakerTurnContextManager,
        ]
        filtered = duplex_manager_classes(retained + bypass)
        self.assertIn(MicroTurnAssembler, filtered)
        self.assertIn(DuplexRuntimeAdapter, filtered)
        for manager in bypass:
            self.assertNotIn(manager, filtered)
        for manager in retained:
            self.assertIn(manager, filtered)
        self.assertEqual(duplex_manager_classes(filtered), filtered)

    async def test_service_disables_native_semantic_paths(self):
        """The service filters native semantic triggers and retains its TTS owner."""
        classes = [
            ASRManager, TTSManager, TTSPlaybackManager, VADManager,
            DirectAudioManager, LLMAgentContextManager, LLMAgentConsumptionManager,
            TurnTakingManager, TurnDetectorManager, MultiSpeakerTurnContextManager,
        ]
        prototype = DefaultService(
            models=Models(),
            service_config={'duplex_enabled': True},
            manager_classes=list(classes),
        )
        registered = prototype._manager_classes
        self.assertIn(MicroTurnAssembler, registered)
        self.assertIn(DuplexRuntimeAdapter, registered)
        self.assertIn(TTSPlaybackManager, registered)
        for manager in (
            DirectAudioManager, LLMAgentContextManager, LLMAgentConsumptionManager,
            TurnTakingManager, TurnDetectorManager, MultiSpeakerTurnContextManager,
        ):
            self.assertNotIn(manager, registered)
        self.assertEqual(duplex_manager_classes(registered), registered)
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

    async def test_interruption_resets_audio_and_consumes_the_full_stream(self):
        """An interruption resets audio while the official decode continues to EOS."""
        adapter, client = self.adapter(
            ['<|user finish talking|>Hello<|im_end|>',
             GenerationEnd('stop', (151648, 9707, 151645))],
            ['<|user interruption|>', '<|im_end|>',
             GenerationEnd('stop', (151650, 151645))],
        )
        await self.send('q')
        await self.assembler.flush()
        response_id = adapter._response_id
        self.assertTrue(response_id)
        await self.assembler.flush()
        stops = self.events(TurnTTSStopRequested)
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0].response_id, response_id)
        self.assertFalse(self.events(DuplexProtocolError))
        parsed = self.events(DuplexProtocolParsed)[-1]
        self.assertEqual(parsed.state_token, '<|user interruption|>')
        self.assertEqual(parsed.reason, 'interruption')
        # The stream was consumed to EOS instead of being aborted at the marker.
        self.assertEqual(adapter.history[-1], {
            'role': 'assistant',
            'token_ids': [151650, 151645],
            'text': '<|user interruption|><|im_end|>',
        })
        # Released ids travel verbatim; the text is never re-encoded into the prompt.
        self.assertEqual(client.prompts[-1][1], {
            'role': 'assistant', 'token_ids': [151648, 9707, 151645]})

    async def test_interruption_before_finish_talking_does_not_stop_audio(self):
        """The released speaking window must be open before a reset is honored."""
        adapter, _ = self.adapter(['Hello<|im_end|>'], ['<|user interruption|><|im_end|>'])
        await self.send('q')
        await self.assembler.flush()
        self.assertTrue(adapter._response_id)
        await self.assembler.flush()
        self.assertFalse(self.events(TurnTTSStopRequested))

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
