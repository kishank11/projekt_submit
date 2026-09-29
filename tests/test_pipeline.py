import json

from conftest import ROOT

from iris_ingest.adapters.fixture_nrw_csv import NrwSitesCsvAdapter
from iris_ingest.adapters.fixture_vienna_geojson import ViennaParcelsGeoJsonAdapter
from iris_ingest.core import JsonlSink, run

CONTRACT_KEYS = {
    "country_code",
    "region_code",
    "source_id",
    "source_date",
    "fetched_at",
    "record_key",
    "attributes",
    "geom",
}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_clean_run_imports_at_least_20_records(tmp_path, fixed_ts):
    report = run(NrwSitesCsvAdapter(), JsonlSink(tmp_path), fetched_at=fixed_ts)
    accepted = read_jsonl(tmp_path / "accepted.jsonl")

    assert report.accepted >= 20
    assert len(accepted) == report.accepted
    assert report.extracted == report.accepted + report.rejected


def test_every_accepted_record_matches_contract(tmp_path, fixed_ts):
    run(NrwSitesCsvAdapter(), JsonlSink(tmp_path), fetched_at=fixed_ts)
    for rec in read_jsonl(tmp_path / "accepted.jsonl"):
        assert set(rec) == CONTRACT_KEYS
        assert rec["country_code"] == "DE"
        assert rec["source_id"] == "fixture-nrw-csv"
        assert "geometry" not in rec and "wkt" not in rec["attributes"]


def test_known_bad_rows_are_rejected_with_reasons(tmp_path, fixed_ts):
    report = run(NrwSitesCsvAdapter(), JsonlSink(tmp_path), fetched_at=fixed_ts)
    assert set(report.reject_reasons) == {"NW-023", "NW-024", "NW-025", "NW-026", "NW-027"}

    rejected = {r["record_key"]: r for r in read_jsonl(tmp_path / "rejected.jsonl")}
    assert rejected["NW-023"]["reasons"] == ["country_code is missing"]
    # raw row is kept for triage
    assert rejected["NW-024"]["raw"]["country"] == "XX"


def test_missing_geometry_stays_null(tmp_path, fixed_ts):
    run(NrwSitesCsvAdapter(), JsonlSink(tmp_path), fetched_at=fixed_ts)
    by_key = {r["record_key"]: r for r in read_jsonl(tmp_path / "accepted.jsonl")}
    assert by_key["NW-007"]["geom"] is None


def test_output_is_deterministic_and_matches_committed_example(tmp_path, fixed_ts):
    run(NrwSitesCsvAdapter(), JsonlSink(tmp_path / "a"), fetched_at=fixed_ts)
    run(NrwSitesCsvAdapter(), JsonlSink(tmp_path / "b"), fetched_at=fixed_ts)
    a = (tmp_path / "a" / "accepted.jsonl").read_text()
    assert a == (tmp_path / "b" / "accepted.jsonl").read_text()
    assert a == (ROOT / "examples" / "normalized_output.jsonl").read_text()


def test_both_adapters_share_the_same_pipeline(tmp_path, fixed_ts):
    r1 = run(NrwSitesCsvAdapter(), JsonlSink(tmp_path / "nrw"), fetched_at=fixed_ts)
    r2 = run(ViennaParcelsGeoJsonAdapter(), JsonlSink(tmp_path / "vie"), fetched_at=fixed_ts)
    assert (r1.accepted, r2.accepted) == (22, 6)
    vienna = read_jsonl(tmp_path / "vie" / "accepted.jsonl")
    assert {r["country_code"] for r in vienna} == {"AT"}
    assert all(set(r) == CONTRACT_KEYS for r in vienna)
