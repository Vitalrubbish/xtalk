# llm_agent_context_manager.py

## Purpose, classes, and core methods

Converts visible session events into AgentContext. A1 preserves or creates request_id at the input boundary and propagates turn, segment, and prefix. A played-feedback response_id remains in context; a new generation request does not reuse it. Persistent loop behavior is unchanged.

## Core methods

_accept_event_context builds context and publishes consumption requests. ASR partial/final handlers handle input; response update/finish handlers forward played facts; the loop handler creates a persistent request; shutdown performs lightweight cleanup. A missing request_id is allocated at the request boundary without changing the source event. Existing multi-speaker gating is retained; A2 integrates micro-turn input.
