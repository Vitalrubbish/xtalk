# service.py

## Purpose, classes, and core methods

`Service` automatically registers one `DuplexTimelineRecorder` when `duplex_timeline_enabled` is true. `stop` shuts down other managers, drains the `EventBus`, and closes recorders in `finally` so shutdown events remain observable. The `duplex_enabled` switch registers the duplex scheduler and online protocol execution.

`Service` owns model clones, the `EventBus`, managers and gateways. `DefaultService` supplies the standard stack. `__init__` registers the recorder when the Boolean flag is exactly `True`; prototypes register classes while live WebSocket sessions create files. `_instantiate_manager` injects models/config and subscription overrides. `clone` copies configuration and registrations. `stop` closes recorders after producers and the `EventBus`. Manual recorder registration also enables observation.

## Duplex registration

When `duplex_enabled` is Boolean `True`, `duplex_manager_classes` replaces semantic control managers. Prototypes register classes; cloned sessions create an assembler and adapter. `duplex_model_url` selects the model service; shutdown stops the assembler, adapter and native TTS in order, with the recorder last. With continuous ASR the service reports `acoustic_vad_enabled=false`, keeps session-level PCM input and per-micro-turn transcript reads, and ignores legacy acoustic boundaries.
