# state.py

## Purpose, classes, and core methods

Defines the immutable DuplexCorrelation snapshot for session, turn, segment, prefix, request, and response fields. A1 preserves supplied prefix versions; PrefixSnapshot and version advancement belong to A2.

## Class design

DuplexCorrelation is a frozen dataclass. session_id is required; turn_id, segment_id, and prefix_version default to None, while request_id and response_id default to empty strings. Construction stores supplied values; callers allocate and validate identifiers.
