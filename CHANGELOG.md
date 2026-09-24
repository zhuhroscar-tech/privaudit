# Changelog

All notable changes to `privaudit` are documented here.

## v0.1.8 — Repository completeness contracts

- Added this changelog and linked release history from both READMEs.
- Added repository-contract tests for required project files, README links, current changelog entry, CI workflows, and release artifact coverage.
- Bumped the package/runtime version to `0.1.8`.

## v0.1.7 — Packaging license metadata

- Modernized packaging license metadata to the current SPDX string format.
- Declared `LICENSE` for built distributions and removed the deprecated MIT license classifier.
- Added regression coverage so deprecated setuptools license metadata does not return.

## v0.1.6 — PipeWire node-id reuse handling

- Fixed capture diffing when PipeWire reuses a freed node id for a different stream.
- Treats pid or capture-kind changes on the same node id as a stop/start pair instead of silently continuing one session.
- Corrected README wording for failed `pw-dump` polls: failures are unknown snapshots, not empty snapshots.

## v0.1.5 — Failed `pw-dump` poll handling

- Fixed false stop/start history entries caused by treating a failed `pw-dump` invocation as an empty PipeWire graph.
- `run_pw_dump()` now returns `None` for timeout, missing binary, non-zero exit, or invalid JSON.
- `status` reports an explicit polling error instead of falsely saying no app is capturing.

## v0.1.4 — Release artifact maintenance

- Continued Linux runner validation for the installable package and standalone zipapp.
- Kept release downloads aligned with the project version.

## v0.1.3 — CLI and history polish

- Improved command-line behavior and history inspection coverage.
- Preserved the local-only PipeWire privacy model.

## v0.1.2 — Downloadable zipapp release

- Published a standalone `privaudit.pyz` release artifact.
- Kept the editable-install development workflow documented for source users.

## v0.1.1 — Early packaging update

- Refined initial packaging and command-line entry-point behavior.
- Added follow-up validation for source and release usage.

## v0.1.0 — Initial release

- Introduced local PipeWire microphone/camera capture observation.
- Added `watch`, `status`, and `history` commands with JSONL history storage.
- Documented the privacy boundary: PipeWire metadata only, no audio/video content and no network access.
