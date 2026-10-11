# test_duplex_protocol.py

## Purpose, classes, and core methods

Covers input serialization, five control states, answer text, protocol error codes, protocol observations, JSONL error codes and sequence, generation-to-playback correlation, recorder unsubscribe, and idempotent close. Tests use EventBus, temporary directories, and fake streams without model inference.

## Running

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_duplex_protocol -v
~~~

Uses an existing local conda environment. Real model services and cluster integration require separate remote acceptance.
