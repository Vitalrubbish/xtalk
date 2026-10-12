# model_client.py

## Purpose, classes, and core methods

DuplexModelClient posts raw ChatML prompts to /generate with aiohttp and reads NDJSON while preserving special tokens. GenerationEnd preserves stop/length reasons instead of inventing EOS at the official token limit. stream propagates HTTP, timeout and model errors; cancellation closes the connection.

## Usage and boundaries

Registered by the Boolean duplex_enabled service switch. Native mode keeps its configuration; official weights, long sessions, audio quality and FDB require remote conda acceptance.

Malformed NDJSON becomes a model-service error; execution stops unplayed output and records evidence.
