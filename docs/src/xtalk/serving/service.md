# service.py

## Purpose, classes, and core methods

Service automatically registers one DuplexTimelineRecorder when duplex_timeline_enabled is true. stop shuts down other managers, drains EventBus, and closes recorders in finally so shutdown events remain observable. The duplex_enabled switch registers A2/A3 scheduling and online protocol execution.

## Classes and core methods

Service owns model clones, EventBus, managers, and gateways. DefaultService supplies the standard stack. __init__ registers the recorder when the Boolean flag is exactly True; prototypes register classes while live WebSocket sessions create files. _instantiate_manager injects models/config and subscription overrides. clone copies configuration and registrations. stop closes recorders after producers and EventBus. Manual recorder registration also enables observation.

## A2/A3 update

When duplex_enabled is Boolean True, duplex_manager_classes replaces semantic control managers. Prototypes register classes; cloned sessions create an assembler/adapter. duplex_model_url selects the model service; shutdown stops the assembler, adapter and native TTS in order, with the recorder last.
