import json
import subprocess

from privaudit.core import (
    CaptureNode,
    Event,
    append_events,
    diff_snapshots,
    filter_events,
    parse_pw_dump,
    poll_once,
    read_events,
    run_pw_dump,
)

SAMPLE_PW_DUMP = [
    {
        "id": 55,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "media.class": "Stream/Input/Audio",
                "application.name": "Zoom",
                "application.process.id": "12345",
                "application.process.binary": "zoom",
            }
        },
    },
    {
        "id": 56,
        "type": "PipeWire:Interface:Node",
        "info": {
            "props": {
                "media.class": "Stream/Input/Video",
                "application.name": "Firefox",
                "application.process.id": "999",
            }
        },
    },
    {
        "id": 57,
        "type": "PipeWire:Interface:Node",
        "info": {"props": {"media.class": "Audio/Sink", "node.description": "Speakers"}},
    },
    {"id": 58, "type": "PipeWire:Interface:Port", "info": {}},
]


def test_parse_pw_dump_extracts_capture_nodes_only():
    nodes = parse_pw_dump(SAMPLE_PW_DUMP)
    assert len(nodes) == 2
    kinds = {n.kind for n in nodes}
    assert kinds == {"mic", "camera"}
    zoom = next(n for n in nodes if n.kind == "mic")
    assert zoom.app_name == "Zoom"
    assert zoom.pid == 12345
    assert zoom.app_binary == "zoom"


def test_parse_pw_dump_ignores_playback_and_non_node_objects():
    nodes = parse_pw_dump(SAMPLE_PW_DUMP)
    assert all(n.kind in ("mic", "camera") for n in nodes)


def test_run_pw_dump_parses_json_output():
    def fake_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(SAMPLE_PW_DUMP), stderr="")

    result = run_pw_dump("pw-dump", runner=fake_runner)
    assert len(result) == 4


def test_run_pw_dump_handles_failure_gracefully():
    def fake_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="err")

    assert run_pw_dump("pw-dump", runner=fake_runner) == []


def test_run_pw_dump_handles_garbage_json():
    def fake_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="not json", stderr="")

    assert run_pw_dump("pw-dump", runner=fake_runner) == []


def test_diff_snapshots_detects_start():
    prev = []
    curr = [CaptureNode(1, "mic", "Zoom")]
    events = diff_snapshots(prev, curr, now=100.0)
    assert len(events) == 1
    assert events[0].action == "start"
    assert events[0].app_name == "Zoom"
    assert events[0].ts == 100.0


def test_diff_snapshots_detects_stop():
    prev = [CaptureNode(1, "mic", "Zoom")]
    curr = []
    events = diff_snapshots(prev, curr, now=200.0)
    assert len(events) == 1
    assert events[0].action == "stop"


def test_diff_snapshots_no_change_no_events():
    node = CaptureNode(1, "mic", "Zoom")
    events = diff_snapshots([node], [node], now=100.0)
    assert events == []


def test_poll_once_returns_new_active_set():
    def fake_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(SAMPLE_PW_DUMP), stderr="")

    result = poll_once([], pw_dump_bin="pw-dump", runner=fake_runner, now=42.0)
    assert len(result.active) == 2
    assert len(result.events) == 2
    assert all(e.action == "start" for e in result.events)


def test_append_and_read_events_round_trip(tmp_path):
    log = tmp_path / "sub" / "history.jsonl"
    events = [Event(1.0, "mic", "start", "Zoom", "zoom", 111, 1)]
    append_events(events, log_path=log)
    read_back = read_events(log)
    assert len(read_back) == 1
    assert read_back[0].app_name == "Zoom"
    assert read_back[0].pid == 111


def test_read_events_missing_file_returns_empty(tmp_path):
    assert read_events(tmp_path / "nope.jsonl") == []


def test_read_events_skips_corrupt_lines(tmp_path):
    log = tmp_path / "history.jsonl"
    log.write_text('{"ts": 1.0, "kind": "mic", "action": "start", "app_name": "A"}\nnot json\n')
    events = read_events(log)
    assert len(events) == 1


def test_filter_events_by_kind_app_and_time():
    events = [
        Event(10.0, "mic", "start", "Zoom", "zoom"),
        Event(20.0, "camera", "start", "Firefox", "firefox"),
        Event(30.0, "mic", "stop", "Zoom", "zoom"),
    ]
    assert len(filter_events(events, kind="mic")) == 2
    assert len(filter_events(events, app_name="fire")) == 1
    assert len(filter_events(events, since_ts=15.0)) == 2
