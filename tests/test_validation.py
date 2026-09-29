from datetime import UTC, date, datetime

import pytest

from iris_ingest.core import (
    CanonicalRecord,
    RecordRejected,
    SourceMetadata,
    collect_problems,
    validate,
)

TS = datetime(2026, 9, 1, 12, tzinfo=UTC)


def make(country="DE", region="NW", source_date=date(2026, 8, 1), fetched_at=TS, key="k1"):
    return CanonicalRecord(
        metadata=SourceMetadata(
            source_id="test",
            source_date=source_date,
            fetched_at=fetched_at,
            country_code=country,
            region_code=region,
        ),
        record_key=key,
    )


def test_valid_record_passes():
    assert validate(make()) is not None


@pytest.mark.parametrize("country", ["", "XX", "DEU", "de", " DE", None, 276])
def test_invalid_country_code_is_rejected_not_defaulted(country):
    record = make(country=country, region=None)
    with pytest.raises(RecordRejected) as exc:
        validate(record)
    assert any("country_code" in r for r in exc.value.reasons)
    # the record itself was not "fixed" to DE on the way
    assert record.country_code == country


def test_country_outside_source_scope():
    with pytest.raises(RecordRejected, match="outside this source's scope"):
        validate(make(country="FR", region=None), allowed_countries=frozenset({"DE"}))


@pytest.mark.parametrize("region", ["XX", "nw", "TOOLONG"])
def test_bad_region_rejected(region):
    with pytest.raises(RecordRejected, match="region_code"):
        validate(make(region=region))


def test_missing_region_is_allowed_and_not_invented():
    record = validate(make(region=None))
    assert record.metadata.region_code is None


def test_source_date_after_fetch_rejected():
    with pytest.raises(RecordRejected, match="after fetched_at"):
        validate(make(source_date=date(2026, 9, 2)))


def test_naive_fetched_at_rejected():
    with pytest.raises(RecordRejected, match="timezone"):
        validate(make(fetched_at=datetime(2026, 9, 1)))


def test_all_problems_reported_together():
    problems = collect_problems(make(country="XX", key=""))
    assert len(problems) == 2
