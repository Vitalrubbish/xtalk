# test_duplex_observability.py

## Purpose, classes, and core methods

Uses fake PCM TTS and asynchronous text streams to exercise the real generation, TTS, coordinator, and playback event chain. Verifies delivery metadata, concurrent response isolation, reserved IDs, fresh requests after played feedback, targeted preemption, and Service timeline registration and shutdown tail.

## Running

~~~bash
conda run -n interclarify-dev python -m unittest tests.test_duplex_observability -v
~~~

Uses an existing local conda environment. Real model services and cluster integration require separate remote acceptance.
