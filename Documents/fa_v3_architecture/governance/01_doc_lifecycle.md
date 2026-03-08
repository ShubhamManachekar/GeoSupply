# Governance: Document Lifecycle

## Lifecycle States
- Draft: initial authoring.
- Review: technical and architecture review underway.
- Approved: accepted for project use.
- Implemented: content matches shipped code behavior.
- Deprecated: superseded by newer canonical content.

## Required Metadata
Each FA v3 doc should include:
- State.
- Last reviewed date.
- Owner.
- Scope (`actual_state` or `target_state`).

## Transition Rule
A document cannot move to `Implemented` unless code evidence exists and references are traceable.
