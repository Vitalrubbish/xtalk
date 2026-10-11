# service.py

## Purpose, classes, and core methods

Service automatically registers one DuplexTimelineRecorder when duplex_timeline_enabled is true. stop shuts down other managers, drains EventBus, and closes recorders in finally so shutdown events remain observable. This entry point provides observation only; A2/A3 scheduling and protocol execution are not registered.

## Classes and core methods

Service owns model clones, EventBus, managers, and gateways. DefaultService supplies the standard stack. __init__ registers the recorder when the Boolean flag is exactly True; prototypes register classes while live WebSocket sessions create files. _instantiate_manager injects models/config and subscription overrides. clone copies configuration and registrations. stop closes recorders after producers and EventBus. Manual recorder registration also enables observation.
