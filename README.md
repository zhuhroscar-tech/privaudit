[![English](https://img.shields.io/badge/English-555555?style=flat)](README.md) [![简体中文](https://img.shields.io/badge/简体中文-555555?style=flat)](README.zh-CN.md)

# privaudit

Local microphone and camera access history for Linux desktops using PipeWire. privaudit observes capture nodes, records start/stop events, and lets you inspect activity afterward without muting or reconfiguring streams.

![Example terminal output](docs/images/example-output.png)

## Requirements and install

Requires Linux, Python 3.9+, a running PipeWire session, and `pw-dump` on `PATH`. PulseAudio-only systems and non-Linux platforms are not supported. The Python runtime uses only the standard library; root is not required.

```bash
git clone https://github.com/zhuhroscar-tech/privaudit.git
cd privaudit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Alternatively, download `privaudit.pyz` from [Releases](https://github.com/zhuhroscar-tech/privaudit/releases) and run `python3 privaudit.pyz --help`. This route needs no pip installation, but still requires PipeWire and Python.

## Quick start

```bash
privaudit watch
# In another terminal with the same environment activated:
privaudit status
privaudit history --since-hours 24
privaudit history --kind mic --app zoom
privaudit history --json
```

`watch` runs in the foreground until Ctrl+C and polls every two seconds. Use `watch --interval 5` to change that interval. `status` inspects the current graph without a watcher; `history` can only show previously recorded events. Optional login startup instructions are in [the reference](docs/REFERENCE.md).

## Privacy and limitations

The tool reads PipeWire metadata, not audio or video content. It makes no network requests, requires no root access, and never opens capture devices. Its own JSONL log stores app names, binaries, PIDs, node IDs, and timestamps at `~/.local/share/privaudit/history.jsonl`. Use `--log PATH` with `watch` and `history`, or set `PRIVAUDIT_LOG`, to change the location.

This is a polling observer, not a security boundary or complete audit trail. Short events between polls, capture outside the visible PipeWire graph, and activity while the watcher is stopped may be missed. Failed `pw-dump` reads are treated as empty snapshots, so an empty status is not proof that nothing captured data. Protect the local log if application activity is sensitive.

## Development and removal

Run `python -m pytest -v`. See [CI](.github/workflows/ci.yml) for Linux integration and zipapp builds. Uninstall with `python -m pip uninstall privaudit`; recorded history remains until you explicitly remove it. Stop any optional user service first.

[MIT license](LICENSE).
