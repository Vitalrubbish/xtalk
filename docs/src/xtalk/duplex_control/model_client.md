# model_client.py

## Purpose and types

DuplexModelClient posts complete micro-turn histories with aiohttp and reads NDJSON while preserving special tokens and generated IDs. GenerationEnd carries the stop/length reason, token_ids, and separate server timing/cache metrics. A token-budget ending retains its actual generated IDs.

## Core methods

stream submits history, max_new_tokens, session_id, request_id, and use_cache, logs an identified monotonic request timestamp, and yields text increments plus GenerationEnd. HTTP, protocol, and model errors propagate. The constructor accepts explicit session identity and a diagnostic cache switch; the runtime adapter enables KV reuse by default.

release requests DELETE /cache/{session_id} after inference stops. Transport errors and timeouts defer cleanup to server expiry. Catching asyncio.TimeoutError preserves teardown on Python 3.10. Cancellation closes the connection. Caches remain session-isolated and every request retains its complete history.
