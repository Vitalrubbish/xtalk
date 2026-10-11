# DuplexCascade A1: protocol and observability

A1 provides complete-output protocol parsing, raw success/error observations, request/response correlation propagation, a JSONL timeline, and the TTSStarted delivery boundary. LLM/TTS/playback reuse native managers. The protocol observer awaits online stream integration. A2 scheduling/version allocation, A3 online token execution, and A4 remote acceptance remain future stages.

## Configuration and timeline

~~~json
{
  "service_config": {
    "duplex_timeline_enabled": true,
    "duplex_timeline_dir": "data/duplex_timeline",
    "duplex_timeline_history": 1000
  }
}
~~~

Use Boolean true to enable automatic registration. Live sessions create session_id.jsonl. Memory is bounded; files append with synchronous flush per event, and a new recorder restarts sequence at 1. sequence describes recording order; monotonic_timestamp describes event creation. Nested events may be recorded first. Empty IDs remain unchanged; client playback acknowledgements can contain only response_id, and analysis joins explicit identifiers. ResponseUpdate/ResponseFinish confirm played text; TTSStarted opens delivery and does not prove audio was heard.

## File mapping

| Implementation | Mirrored documentation |
| --- | --- |
| src/xtalk/duplex_control/__init__.py | [__init__](../src/xtalk/duplex_control/__init__.md) |
| src/xtalk/duplex_control/protocol.py | [protocol](../src/xtalk/duplex_control/protocol.md) |
| src/xtalk/duplex_control/state.py | [state](../src/xtalk/duplex_control/state.md) |
| src/xtalk/duplex_control/timeline.py | [timeline](../src/xtalk/duplex_control/timeline.md) |
| src/xtalk/serving/events.py | [events](../src/xtalk/serving/events.md) |
| src/xtalk/serving/service.py | [service](../src/xtalk/serving/service.md) |
| src/xtalk/serving/modules/llm_agent_context_manager.py | [llm_agent_context_manager](../src/xtalk/serving/modules/llm_agent_context_manager.md) |
| src/xtalk/serving/modules/llm_agent_generation_manager.py | [llm_agent_generation_manager](../src/xtalk/serving/modules/llm_agent_generation_manager.md) |
| src/xtalk/serving/modules/tts_manager.py | [tts_manager](../src/xtalk/serving/modules/tts_manager.md) |
| src/xtalk/serving/modules/tts_response_coordinator.py | [tts_response_coordinator](../src/xtalk/serving/modules/tts_response_coordinator.md) |
| src/xtalk/serving/modules/tts_playback_manager.py | [tts_playback_manager](../src/xtalk/serving/modules/tts_playback_manager.md) |
| src/xtalk/serving/modules/turn_detector_manager.py | [turn_detector_manager](../src/xtalk/serving/modules/turn_detector_manager.md) |
| tests/test_duplex_protocol.py | [test_duplex_protocol](../tests/test_duplex_protocol.md) |
| tests/test_duplex_observability.py | [test_duplex_observability](../tests/test_duplex_observability.md) |
| tests/test_turn_detector_manager.py | [test_turn_detector_manager](../tests/test_turn_detector_manager.md) |

## Validation

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_protocol tests.test_duplex_observability tests.test_turn_detector_manager tests.test_llm_agent_persistent_stream tests.test_response_identity tests.test_tool_call_playback_barrier tests.test_tts_streaming_playback_alignment -q
~~~

On 2026-10-12, 35/35 targeted tests passed in the existing local paratalker-dev conda environment (Python 3.11.16). Fake generation and PCM TTS exercise actual dispatch, concurrent response isolation, reserved IDs, preemption, played settlement, and shutdown logging. Compilation and whitespace checks passed. Real models, audio quality, synchronous disk overhead, FDB, and long sessions require separate remote conda acceptance.
