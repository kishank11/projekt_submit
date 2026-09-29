from conftest import ROOT

from iris_ingest.cli import main


def test_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "fixture-nrw-csv" in out and "fixture-vienna-geojson" in out


def test_run_writes_jsonl(tmp_path, capsys):
    code = main(["run", "fixture-nrw-csv", "--out", str(tmp_path), "--fetched-at", "2026-09-01T12:00:00+00:00"])
    assert code == 0
    assert "accepted=22" in capsys.readouterr().out
    assert (tmp_path / "accepted.jsonl").read_text() == (
        ROOT / "examples" / "normalized_output.jsonl"
    ).read_text()


def test_fail_on_reject(tmp_path):
    assert main(["run", "fixture-nrw-csv", "--out", str(tmp_path), "--fail-on-reject"]) == 2


def test_unknown_source(capsys):
    assert main(["run", "nope"]) == 1
    assert "unknown source" in capsys.readouterr().err
