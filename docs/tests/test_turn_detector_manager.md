# test_turn_detector_manager.py

## Purpose, classes, and core methods

Verifies natural completion versus early stop and uses a real EventBus to check that TTSChunkReady leaves listening open, TTSStarted closes it, and TTSPlaybackFinished restores it.

## Running

~~~bash
conda run -n paratalker-dev env PYTHONPATH=src python -m unittest tests.test_turn_detector_manager -v
~~~

Uses an existing local conda environment. Real model services and cluster integration require separate remote acceptance.
