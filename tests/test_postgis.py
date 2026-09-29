"""Integration test against a real PostGIS. Skipped unless IRIS_DATABASE_URL is set.

    docker compose up -d
    IRIS_DATABASE_URL=postgresql://iris:iris@localhost:5433/iris uv run pytest -m postgis
"""

import os

import pytest

from conftest import ROOT

from iris_ingest.adapters.fixture_nrw_csv import NrwSitesCsvAdapter
from iris_ingest.core import PostgisSink, run

DSN = os.environ.get("IRIS_DATABASE_URL")

pytestmark = [
    pytest.mark.postgis,
    pytest.mark.skipif(not DSN, reason="IRIS_DATABASE_URL not set"),
]


@pytest.fixture
def db():
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS staging CASCADE")
        conn.execute((ROOT / "migrations" / "001_staging.sql").read_text())
        yield conn


def test_load_into_postgis_is_idempotent(db, fixed_ts):
    run(NrwSitesCsvAdapter(), PostgisSink(DSN), fetched_at=fixed_ts)
    run(NrwSitesCsvAdapter(), PostgisSink(DSN), fetched_at=fixed_ts)

    n, n_geom, srids = db.execute(
        "SELECT count(*), count(geom), array_agg(DISTINCT ST_SRID(geom)) "
        "FILTER (WHERE geom IS NOT NULL) FROM staging.source_record"
    ).fetchone()
    assert (n, n_geom, srids) == (22, 21, [4326])

    nulls = db.execute(
        "SELECT count(*) FROM staging.source_record WHERE country_code IS NULL"
    ).fetchone()[0]
    assert nulls == 0


def test_database_refuses_bad_country_code_even_without_python(db):
    import psycopg

    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO staging.source_record (country_code, source_id, record_key, "
            "source_date, fetched_at, batch_id) "
            "VALUES ('de', 's', 'k', '2026-08-01', now(), gen_random_uuid())"
        )
