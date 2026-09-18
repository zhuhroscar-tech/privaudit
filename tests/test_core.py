import json
import subprocess

from privaudit.core import (
    CaptureNode,
    Event,
    PwDumpNotFound,
    append_events,
    diff_snapshots,
    filter_events,
    find_pw_dump,
    parse_pw_dump,
    poll_once,
    read_events,
    run_loop,
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

    # A non-zero exit is a FAILED poll, not "zero objects" -- None signals
    # "unknown state", distinct from an empty list ("known: nothing here").
    assert run_pw_dump("pw-dump", runner=fake_runner) is None


def test_run_pw_dump_handles_garbage_json():
    def fake_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="not json", stderr="")

    assert run_pw_dump("pw-dump", runner=fake_runner) is None


def test_run_pw_dump_handles_timeout_gracefully():
    def fake_runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 15))

    # A hung pw-dump must not raise out of run_pw_dump -- the long-running
    # `watch` loop depends on this to survive a single bad poll.
    assert run_pw_dump("pw-dump", runner=fake_runner) is None


def test_run_pw_dump_handles_missing_binary_gracefully():
    def fake_runner(cmd, **kwargs):
        raise OSError("No such file or directory")

    assert run_pw_dump("pw-dump", runner=fake_runner) is None


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
    assert result.poll_failed is False


def test_poll_once_transient_failure_does_not_fabricate_stop_event():
    """Regression test: a transient pw-dump failure (non-zero exit, timeout,
    or garbage JSON) between two successful polls must NOT be diffed against
    an empty snapshot. Before the fix, run_pw_dump returned [] on failure
    indistinguishably from a real empty result, so poll_once would emit a
    false 'stop' event for an app that never actually stopped capturing --
    and a false 'start' event on the next successful poll, once the state
    "flapped" back. This is a real false-positive/false-negative bug in a
    privacy-audit tool's core detection path."""
    previously_active = [CaptureNode(1, "mic", "Zoom", "zoom", 111)]

    def failing_runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="pipewire busy")

    result = poll_once(previously_active, pw_dump_bin="pw-dump", runner=failing_runner, now=100.0)
    assert result.events == []
    assert result.active == previously_active
    assert result.poll_failed is True


def test_poll_once_recovers_cleanly_after_transient_failure():
    """After a failed poll, the NEXT successful poll must diff against the
    carried-forward previous state, not against an empty one -- so a real
    stop is still detected once it actually happens, and no phantom start
    is fabricated for an app that was continuously active throughout."""
    previously_active = [CaptureNode(1, "mic", "Zoom", "zoom", 111)]
    calls = {"n": 0}

    def flaky_then_stopped_runner(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="pipewire busy")
        return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")

    failed = poll_once(previously_active, pw_dump_bin="pw-dump", runner=flaky_then_stopped_runner, now=100.0)
    assert failed.events == []
    assert failed.active == previously_active

    recovered = poll_once(failed.active, pw_dump_bin="pw-dump", runner=flaky_then_stopped_runner, now=101.0)
    # Zoom really did stop by the second (successful) poll -- exactly one
    # real stop event, not a spurious extra start+stop pair from the gap.
    assert [(e.kind, e.action) for e in recovered.events] == [("mic", "stop")]
    assert recovered.active == []


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


def test_find_pw_dump_raises_when_missing(monkeypatch):
    monkeypatch.setattr("privaudit.core.shutil.which", lambda name: None)
    try:
        find_pw_dump()
        assert False, "expected PwDumpNotFound"
    except PwDumpNotFound as exc:
        assert "pw-dump not found" in str(exc)


def test_find_pw_dump_returns_path_when_present(monkeypatch):
    monkeypatch.setattr("privaudit.core.shutil.which", lambda name: "/usr/bin/pw-dump")
    assert find_pw_dump() == "/usr/bin/pw-dump"


def test_append_events_empty_list_is_noop(tmp_path):
    log = tmp_path / "nested" / "history.jsonl"
    append_events([], log_path=log)
    assert not log.exists()


def test_read_events_skips_blank_lines(tmp_path):
    log = tmp_path / "history.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("\n" + Event(1.0, "mic", "start", "Zoom").to_json() + "\n\n")
    events = read_events(log)
    assert len(events) == 1
    assert events[0].app_name == "Zoom"


def test_run_loop_polls_logs_and_calls_on_event(tmp_path, monkeypatch):
    log = tmp_path / "history.jsonl"
    monkeypatch.setattr("privaudit.core.find_pw_dump", lambda: "/usr/bin/pw-dump")

    calls = {"n": 0}

    def fake_runner(cmd, capture_output, text, timeout, check):
        calls["n"] += 1
        if calls["n"] == 1:
            payload = json.dumps(
                [
                    {
                        "id": 1,
                        "type": "PipeWire:Interface:Node",
                        "info": {
                            "props": {
                                "media.class": "Stream/Input/Audio",
                                "application.name": "Zoom",
                                "application.process.id": 111,
                            }
                        },
                    }
                ]
            )
        else:
            payload = "[]"
        return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr="")

    seen_events = []
    sleeps = []
    run_loop(
        interval_seconds=0.01,
        log_path=log,
        max_iterations=2,
        sleep=lambda s: sleeps.append(s),
        runner=fake_runner,
        on_event=lambda e: seen_events.append(e),
    )

    assert calls["n"] == 2
    # Only one sleep call: after iteration 1 (since max_iterations=2 stops
    # the loop before a sleep would follow iteration 2).
    assert sleeps == [0.01]
    # Poll 1 sees Zoom start; poll 2 sees it stop (fake_runner returns "[]"
    # the second time) -- both transitions are real events run_loop must log.
    assert [e.action for e in seen_events] == ["start", "stop"]
    assert all(e.app_name == "Zoom" for e in seen_events)
    logged = read_events(log)
    assert [e.action for e in logged] == ["start", "stop"]


def test_run_loop_raises_when_pw_dump_missing(monkeypatch):
    def raise_not_found():
        raise PwDumpNotFound("pw-dump not found on PATH.")

    monkeypatch.setattr("privaudit.core.find_pw_dump", raise_not_found)
    try:
        run_loop(max_iterations=1)
        assert False, "expected PwDumpNotFound"
    except PwDumpNotFound:
        pass
