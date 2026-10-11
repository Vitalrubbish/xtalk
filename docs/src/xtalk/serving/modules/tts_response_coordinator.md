# tts_response_coordinator.py

## Purpose, classes, and core methods

The native delivery state machine stores correlation per response. Preparation, replacement, delivery, and preemption stops use the target response metadata; close and cancellation clear snapshots. No semantic arbiter is added, and single serialized delivery ownership remains.

## Core methods

_handle_response_start snapshots the initial request and manages preparation/preemption. _start_delivery publishes delivery; _handle_response_closed releases the next response after settlement; _handle_stop_request discards preparation. shutdown clears state and metadata. _correlations is keyed by response_id so stopping an older response retains its own request_id.
