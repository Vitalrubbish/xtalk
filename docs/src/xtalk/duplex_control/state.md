# state.py

## Purpose, classes, and core methods

Defines the immutable DuplexCorrelation snapshot for session, turn, segment, prefix, request, and response fields. A1 preserves supplied prefix versions; A2 PrefixSnapshot and version advancement are implemented.

## Class design

DuplexCorrelation is a frozen dataclass. session_id is required; turn_id, segment_id, and prefix_version default to None, while request_id and response_id default to empty strings. Construction stores supplied values; callers allocate and validate identifiers.

## A2/A3 update

Adds frozen PrefixSnapshot with current/emitted prefixes, delta text, revision_kind, speech_state, receipt time and request identity. The assembler maintains versions without semantic turn judgments.
