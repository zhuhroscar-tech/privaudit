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
