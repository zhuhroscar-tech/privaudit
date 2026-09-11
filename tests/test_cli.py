import json

from privaudit.cli import main
from privaudit.core import Event, PwDumpNotFound, append_events


def test_cli_history_empty(tmp_path, capsys):
    log = tmp_path / "history.jsonl"
    rc = main(["history", "--log", str(log)])
    assert rc == 0
    assert "No matching" in capsys.readouterr().out


def test_cli_history_shows_events(tmp_path, capsys):
    log = tmp_path / "history.jsonl"
    append_events([Event(1700000000.0, "mic", "start", "Zoom", "zoom", 111, 1)], log_path=log)
    rc = main(["history", "--log", str(log)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "MIC" in out
    assert "Zoom" in out


def test_cli_history_json(tmp_path, capsys):
    log = tmp_path / "history.jsonl"
    append_events([Event(1700000000.0, "camera", "start", "Firefox")], log_path=log)
    rc = main(["history", "--log", str(log), "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["app_name"] == "Firefox"


def test_cli_history_filters_by_kind(tmp_path, capsys):
    log = tmp_path / "history.jsonl"
    append_events(
        [
            Event(1.0, "mic", "start", "Zoom"),
            Event(2.0, "camera", "start", "Firefox"),
        ],
        log_path=log,
    )
    rc = main(["history", "--log", str(log), "--kind", "camera"])
    out = capsys.readouterr().out
    assert "Firefox" in out
    assert "Zoom" not in out


def test_cli_status_no_pw_dump(monkeypatch, capsys):
    def raise_not_found():
        raise PwDumpNotFound("pw-dump not found on PATH.")

    monkeypatch.setattr("privaudit.cli.find_pw_dump", raise_not_found)
    rc = main(["status"])
    assert rc == 2
    assert "pw-dump not found" in capsys.readouterr().err


def test_cli_watch_no_pw_dump(monkeypatch, capsys):
    def raise_not_found():
        raise PwDumpNotFound("pw-dump not found on PATH.")

    monkeypatch.setattr("privaudit.cli.find_pw_dump", raise_not_found)
    rc = main(["watch", "--max-iterations", "1"])
    assert rc == 2


def test_kind_badge_unknown_kind_returns_upper_label():
    from privaudit.cli import _kind_badge
    from privaudit.style import Style

    style = Style(False)
    assert _kind_badge(style, "screen") == "SCREEN"


def test_action_badge_unknown_action_passthrough():
    from privaudit.cli import _action_badge
    from privaudit.style import Style

    style = Style(False)
    assert _action_badge(style, "resume") == "resume"


def test_action_badge_stop_is_dimmed():
    from privaudit.cli import _action_badge
    from privaudit.style import Style

    style = Style(True)
    assert _action_badge(style, "stop") == style.dim("stop ")


def test_cli_history_since_hours_filters_out_old_events(tmp_path, capsys):
    import time as time_mod

    log = tmp_path / "history.jsonl"
    old = Event(time_mod.time() - 999999, "mic", "start", "OldApp")
    recent = Event(time_mod.time(), "mic", "start", "NewApp")
    append_events([old, recent], log_path=log)
    rc = main(["history", "--log", str(log), "--since-hours", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "NewApp" in out
    assert "OldApp" not in out


def test_cli_watch_renders_events_via_on_event_callback(tmp_path, capsys, monkeypatch):
    """cmd_watch's on_event callback (lines that print each transition as
    it's logged) is exercised directly: run_loop itself is unit-tested in
    test_core.py, so here we fake run_loop to invoke the real on_event
    closure cmd_watch builds, proving the CAM/MIC badge rendering works."""
    from privaudit.core import Event

    log = tmp_path / "history.jsonl"
    monkeypatch.setattr("privaudit.cli.find_pw_dump", lambda: "/usr/bin/pw-dump")

    captured_kwargs = {}

    def fake_run_loop(**kwargs):
        captured_kwargs.update(kwargs)
        kwargs["on_event"](Event(1700000000.0, "camera", "start", "Camtool", pid=222))

    monkeypatch.setattr("privaudit.cli.run_loop", fake_run_loop)
    rc = main(["watch", "--log", str(log), "--max-iterations", "1", "--interval", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Watching mic/camera activity" in out
    assert "CAM" in out
    assert "Camtool" in out
    assert captured_kwargs["log_path"] == log
    assert captured_kwargs["max_iterations"] == 1


def test_cli_watch_handles_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr("privaudit.cli.find_pw_dump", lambda: "/usr/bin/pw-dump")

    def raise_interrupt(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("privaudit.cli.run_loop", raise_interrupt)
    rc = main(["watch"])
    assert rc == 0


def test_cli_status_no_active_captures(monkeypatch, capsys):
    monkeypatch.setattr("privaudit.cli.find_pw_dump", lambda: "/usr/bin/pw-dump")
    monkeypatch.setattr("privaudit.core.run_pw_dump", lambda pw_dump_bin: [])
    rc = main(["status"])
    assert rc == 0
    assert "No app is currently capturing" in capsys.readouterr().out


def test_cli_status_shows_active_captures_with_pid(monkeypatch, capsys):
    from privaudit.core import CaptureNode

    monkeypatch.setattr("privaudit.cli.find_pw_dump", lambda: "/usr/bin/pw-dump")
    monkeypatch.setattr("privaudit.core.run_pw_dump", lambda pw_dump_bin: ["raw"])
    monkeypatch.setattr(
        "privaudit.core.parse_pw_dump",
        lambda objects: [CaptureNode(1, "mic", "Zoom", "zoom", 999)],
    )
    rc = main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Zoom" in out
    assert "999" in out


def test_cli_status_json_output(monkeypatch, capsys):
    from privaudit.core import CaptureNode

    monkeypatch.setattr("privaudit.cli.find_pw_dump", lambda: "/usr/bin/pw-dump")
    monkeypatch.setattr("privaudit.core.run_pw_dump", lambda pw_dump_bin: ["raw"])
    monkeypatch.setattr(
        "privaudit.core.parse_pw_dump",
        lambda objects: [CaptureNode(1, "camera", "Firefox", "firefox", None)],
    )
    rc = main(["status", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["app_name"] == "Firefox"
