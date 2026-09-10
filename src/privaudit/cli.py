"""privaudit CLI."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

from . import __version__
from .core import (
    DEFAULT_LOG_PATH,
    PwDumpNotFound,
    filter_events,
    find_pw_dump,
    read_events,
    run_loop,
)
from .style import resolve_style


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# Kind badges: a consistent color per capture type so a user scanning a
# long history can tell mic vs camera events apart by color alone -- one
# glyph family (a plain three-letter label), color carries the
# distinction, not a different icon/emoji per kind.
_KIND_LABEL = {"mic": "MIC", "camera": "CAM"}


def _kind_badge(style, kind: str) -> str:
    label = _KIND_LABEL.get(kind, kind.upper())
    if kind == "mic":
        return style.cyan(label)
    if kind == "camera":
        return style.bold_yellow(label)
    return label


def _action_badge(style, action: str) -> str:
    if action == "start":
        return style.bold_green("start")
    if action == "stop":
        return style.dim("stop ")
    return action


def cmd_history(args) -> int:
    events = read_events(args.log)
    since_ts = None
    if args.since_hours is not None:
        since_ts = time.time() - args.since_hours * 3600
    events = filter_events(events, kind=args.kind, app_name=args.app, since_ts=since_ts)
    events.sort(key=lambda e: e.ts)

    if args.json:
        print(json.dumps([e.__dict__ for e in events], indent=2))
        return 0

    style = resolve_style(no_color_flag=args.no_color)

    if not events:
        print(style.dim("No matching mic/camera access events recorded."))
        return 0

    for e in events:
        pid_str = style.dim(f" pid={e.pid}") if e.pid else ""
        ts = style.dim(f"[{_fmt_ts(e.ts)}]")
        print(f"{ts} {_kind_badge(style, e.kind)}  {_action_badge(style, e.action):<5}  {e.app_name}{pid_str}")
    return 0


def cmd_watch(args) -> int:
    style = resolve_style(no_color_flag=args.no_color)
    try:
        find_pw_dump()
    except PwDumpNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def on_event(e):
        ts = style.dim(f"[{_fmt_ts(e.ts)}]")
        print(f"{ts} {_kind_badge(style, e.kind)}  {_action_badge(style, e.action):<5}  {e.app_name}")

    print(style.dim(f"Watching mic/camera activity via PipeWire (log: {args.log}). Ctrl+C to stop."))
    try:
        run_loop(
            interval_seconds=args.interval,
            log_path=args.log,
            max_iterations=args.max_iterations,
            on_event=on_event,
        )
    except KeyboardInterrupt:
        print()
    return 0


def cmd_status(args) -> int:
    try:
        pw_dump_bin = find_pw_dump()
    except PwDumpNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    from .core import parse_pw_dump, run_pw_dump

    objects = run_pw_dump(pw_dump_bin)
    active = parse_pw_dump(objects)
    if args.json:
        print(json.dumps([n.__dict__ for n in active], indent=2))
        return 0

    style = resolve_style(no_color_flag=args.no_color)

    if not active:
        print(style.dim("No app is currently capturing your microphone or camera."))
        return 0
    for n in active:
        pid_str = style.dim(f" (pid={n.pid})") if n.pid else ""
        print(f"{_kind_badge(style, n.kind)}  {style.bold(n.app_name)}{pid_str}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="privaudit",
        description=(
            "Local mic/camera access history for Linux, built on PipeWire. "
            "Read-only: never mutes, blocks, or modifies any audio/video stream."
        ),
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--no-color", action="store_true", help="Disable colored output.")
    sub = p.add_subparsers(dest="command", required=True)

    p_watch = sub.add_parser("watch", help="Poll PipeWire and log mic/camera start/stop events")
    p_watch.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds (default 2.0)")
    p_watch.add_argument("--log", type=lambda s: __import__("pathlib").Path(s), default=DEFAULT_LOG_PATH)
    p_watch.add_argument("--max-iterations", type=int, default=None, help=argparse.SUPPRESS)
    p_watch.set_defaults(func=cmd_watch)

    p_hist = sub.add_parser("history", help="Show recorded mic/camera access events")
    p_hist.add_argument("--log", type=lambda s: __import__("pathlib").Path(s), default=DEFAULT_LOG_PATH)
    p_hist.add_argument("--kind", choices=["mic", "camera"], default=None)
    p_hist.add_argument("--app", default=None, help="Filter by substring match on app name/binary")
    p_hist.add_argument("--since-hours", type=float, default=None, help="Only show events from the last N hours")
    p_hist.add_argument("--json", action="store_true")
    p_hist.set_defaults(func=cmd_history)

    p_status = sub.add_parser("status", help="Show what is capturing mic/camera right now")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    return p


def main(argv: list | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
