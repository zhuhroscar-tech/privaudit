"""Core logic for privaudit.

The problem: modern Linux desktops (GNOME, KDE, sway/Hyprland and everything
else running on PipeWire, which is now the default audio/video stack on
Fedora, Ubuntu 22.10+, Arch, and most rolling distros) have no equivalent of
Android's "privacy dashboard" or macOS's OverSight: there is no built-in,
DE-agnostic history of *which application used your microphone or camera and
when*. If you step away from your desk and come back, or just want to check
"did anything use my mic while I was in that video call", there is nothing
to check except manually running `pactl list source-outputs` or `pw-dump`
and reading raw JSON at that exact moment -- you cannot see what already
happened.

privaudit polls PipeWire's object graph via `pw-dump` (the standard PipeWire
CLI, present wherever PipeWire itself is -- no extra daemon/kernel module
needed), detects when an application starts or stops actively capturing
audio (`Stream/Input/Audio`, i.e. microphone) or video (`Stream/Input/Video`,
i.e. camera), and appends a compact, human-diffable event log. A separate
`privaudit history` command lets you query that log after the fact --
exactly the gap Android/macOS-style privacy dashboards fill that Linux does
not.

This module never touches audio/video streams itself, never mutes/blocks
anything, and never modifies PipeWire configuration -- it is a read-only
observer. Its only write is appending JSON lines to its own log file.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_LOG_PATH = Path(
    __import__("os").environ.get("PRIVAUDIT_LOG")
    or (Path.home() / ".local" / "share" / "privaudit" / "history.jsonl")
)

# PipeWire media.class values that represent something actively *capturing*
# (as opposed to *playing back*) audio or video.
MIC_MEDIA_CLASS = "Stream/Input/Audio"
CAMERA_MEDIA_CLASS = "Stream/Input/Video"
CAPTURE_MEDIA_CLASSES = {MIC_MEDIA_CLASS: "mic", CAMERA_MEDIA_CLASS: "camera"}


class PwDumpNotFound(RuntimeError):
    pass


@dataclass(frozen=True)
class CaptureNode:
    node_id: int
    kind: str  # "mic" | "camera"
    app_name: str
    app_binary: Optional[str] = None
    pid: Optional[int] = None


@dataclass
class Event:
    ts: float
    kind: str  # "mic" | "camera"
    action: str  # "start" | "stop"
    app_name: str
    app_binary: Optional[str] = None
    pid: Optional[int] = None
    node_id: Optional[int] = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "ts": self.ts,
                "kind": self.kind,
                "action": self.action,
                "app_name": self.app_name,
                "app_binary": self.app_binary,
                "pid": self.pid,
                "node_id": self.node_id,
            }
        )

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            ts=d["ts"],
            kind=d["kind"],
            action=d["action"],
            app_name=d.get("app_name", "unknown"),
            app_binary=d.get("app_binary"),
            pid=d.get("pid"),
            node_id=d.get("node_id"),
        )


def find_pw_dump() -> str:
    path = shutil.which("pw-dump")
    if not path:
        raise PwDumpNotFound(
            "pw-dump not found on PATH. privaudit requires PipeWire "
            "(the 'pipewire' or 'pipewire-utils' package on most distros). "
            "PulseAudio-only systems are not currently supported."
        )
    return path


def run_pw_dump(pw_dump_bin: str, runner=subprocess.run, timeout: int = 15) -> Optional[list]:
    """Run pw-dump and parse its JSON output.

    Returns the parsed object list on success, or ``None`` if the poll
    itself failed (hung/missing binary, non-zero exit, or unparseable
    output). ``None`` is deliberately distinct from ``[]``: an empty list
    means "pw-dump ran fine and reported zero objects" (a fact worth
    diffing against), while ``None`` means "we don't actually know the
    current state this round" -- the caller must NOT treat a failed poll
    as equivalent to "nothing is capturing", or every transient pw-dump
    hiccup would fabricate a false stop event (and a false start event on
    the next successful poll) for an app that never actually stopped.
    """
    try:
        proc = runner([pw_dump_bin], capture_output=True, text=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError):
        # A hung/missing pw-dump must not crash the long-running `watch`
        # loop -- report this poll as failed and let the next poll retry.
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def _app_display_name(info: dict) -> str:
    props = info.get("info", {}).get("props", {}) if "info" in info else info.get("props", {})
    return (
        props.get("application.name")
        or props.get("node.description")
        or props.get("node.name")
        or "unknown"
    )


def parse_pw_dump(objects: list) -> list:
    """Extract active capture nodes (mic/camera) from a pw-dump object list."""
    nodes = []
    for obj in objects:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        info = obj.get("info") or {}
        props = info.get("props") or {}
        media_class = props.get("media.class")
        kind = CAPTURE_MEDIA_CLASSES.get(media_class)
        if not kind:
            continue
        # A node existing in the graph means a stream is set up; PipeWire
        # removes Stream/Input/* nodes when the capture actually stops (as
        # opposed to just going quiet), so presence == active capture for
        # our purposes.
        pid_raw = props.get("application.process.id")
        pid = int(pid_raw) if isinstance(pid_raw, (int, str)) and str(pid_raw).isdigit() else None
        nodes.append(
            CaptureNode(
                node_id=obj.get("id"),
                kind=kind,
                app_name=_app_display_name(obj),
                app_binary=props.get("application.process.binary"),
                pid=pid,
            )
        )
    return nodes


def diff_snapshots(previous: list, current: list, now: Optional[float] = None) -> list:
    """Compare two CaptureNode snapshots (by node_id) and emit start/stop events."""
    now = now if now is not None else time.time()
    prev_by_id = {n.node_id: n for n in previous}
    curr_by_id = {n.node_id: n for n in current}

    events = []
    for node_id, node in curr_by_id.items():
        if node_id not in prev_by_id:
            events.append(
                Event(now, node.kind, "start", node.app_name, node.app_binary, node.pid, node_id)
            )
    for node_id, node in prev_by_id.items():
        if node_id not in curr_by_id:
            events.append(
                Event(now, node.kind, "stop", node.app_name, node.app_binary, node.pid, node_id)
            )
    return events


def append_events(events: list, log_path: Path = DEFAULT_LOG_PATH) -> None:
    if not events:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        for e in events:
            f.write(e.to_json() + "\n")


def read_events(log_path: Path = DEFAULT_LOG_PATH) -> list:
    if not log_path.exists():
        return []
    events = []
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(Event.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError):
                continue
    return events


def filter_events(
    events: list,
    kind: Optional[str] = None,
    app_name: Optional[str] = None,
    since_ts: Optional[float] = None,
) -> list:
    out = events
    if kind:
        out = [e for e in out if e.kind == kind]
    if app_name:
        needle = app_name.lower()
        out = [e for e in out if needle in e.app_name.lower() or (e.app_binary and needle in e.app_binary.lower())]
    if since_ts is not None:
        out = [e for e in out if e.ts >= since_ts]
    return out


@dataclass
class PollResult:
    events: list
    active: list
    poll_failed: bool = False


def poll_once(
    previous_active: list,
    pw_dump_bin: Optional[str] = None,
    runner=subprocess.run,
    now: Optional[float] = None,
) -> PollResult:
    pw_dump_bin = pw_dump_bin or find_pw_dump()
    objects = run_pw_dump(pw_dump_bin, runner=runner)
    if objects is None:
        # The poll itself failed (hung/missing pw-dump, non-zero exit, or
        # unparseable output) -- we genuinely don't know the current state
        # this round. Carry the previous active set forward unchanged and
        # emit no events, rather than diffing against an empty snapshot and
        # fabricating a false stop (and, on the next successful poll, a
        # false start) for an app that never actually stopped capturing.
        return PollResult(events=[], active=previous_active, poll_failed=True)
    current = parse_pw_dump(objects)
    events = diff_snapshots(previous_active, current, now=now)
    return PollResult(events=events, active=current, poll_failed=False)


def run_loop(
    interval_seconds: float = 2.0,
    log_path: Path = DEFAULT_LOG_PATH,
    max_iterations: Optional[int] = None,
    sleep=time.sleep,
    runner=subprocess.run,
    on_event=None,
) -> None:
    """Poll indefinitely (or for max_iterations, used by tests), logging
    start/stop transitions. Never modifies PipeWire state."""
    pw_dump_bin = find_pw_dump()
    active: list = []
    i = 0
    while max_iterations is None or i < max_iterations:
        result = poll_once(active, pw_dump_bin=pw_dump_bin, runner=runner)
        if result.events:
            append_events(result.events, log_path=log_path)
            if on_event:
                for e in result.events:
                    on_event(e)
        active = result.active
        i += 1
        if max_iterations is None or i < max_iterations:
            sleep(interval_seconds)
