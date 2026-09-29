# IRIS ingest: reusable source adapter contract

Submission for **IRIS-CAND-01**. A small Python package that gives every IRIS
data source the same path into staging:

```
extract  ->  normalize  ->  validate  ->  load to staging
(adapter)    (adapter)      (core)        (core sink)
```

A source only implements the first two steps. Validation, reject handling and
loading live in the core and are identical for every source.

> *Note: This implementation was written with the assistance of an AI assistant.*

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv run iris-ingest run fixture-nrw-csv --out out
```

That one command creates the virtualenv, installs the package, runs the NRW
fixture adapter and writes `out/accepted.jsonl` and `out/rejected.jsonl`:

```
fixture-nrw-csv: extracted=27 accepted=22 rejected=5
  rejected NW-023: country_code is missing
  rejected NW-024: country_code 'XX' is not an ISO 3166-1 alpha-2 code
  rejected NW-025: country_code 'DEU' is not an ISO 3166-1 alpha-2 code
  rejected NW-026: geom is invalid: Self-intersection[6.812 51.412]
  rejected NW-027: region_code 'BY' outside source coverage ['NW']
```

Other commands:

| Command | What it does |
|---|---|
| `uv run pytest` | full test suite (PostGIS tests skip without a database) |
| `uv run iris-ingest list` | registered adapters |
| `make demo` | same as quick start with a fixed `fetched_at` (reproducible) |
| `make test-postgis` | starts PostGIS 16 / 3.4 via docker compose, runs integration tests |
| `uv run iris-ingest run <source> --database-url postgresql://...` | stage into PostGIS instead of JSONL (run `make migrate` first) |

Without uv: `python3.12 -m venv .venv && . .venv/bin/activate && pip install -e '.[postgres]' pytest`.

## Canonical record

```json
{
  "country_code": "DE",
  "region_code": "NW",
  "source_id": "fixture-nrw-csv",
  "source_date": "2026-08-02",
  "fetched_at": "2026-09-01T12:00:00+00:00",
  "record_key": "NW-001",
  "attributes": {"area_m2": 1137.5, "land_use": "grassland"},
  "geom": {"type": "Polygon", "coordinates": [[[6.72, 51.38], "..."]]}
}
```

`examples/normalized_output.jsonl` is the committed output of the fixture run
(a test asserts the pipeline reproduces it byte for byte).
`examples/rejected_output.jsonl` shows the reject channel.

In code this is `CanonicalRecord(metadata: SourceMetadata, record_key, attributes, geom)`.
`SourceMetadata` holds `source_id, source_date, fetched_at, country_code, region_code`
as explicit typed fields, so metadata can't end up buried in `attributes`.
`record_key` is an addition to the minimum contract: without a per-source key
there is no idempotent upsert and no way to point at a rejected row.

## Adding a source

Create one file in `src/iris_ingest/adapters/` (or in another package, registered
under the `iris_ingest.adapters` entry point group):

```python
from iris_ingest.core import RawRecord, SourceAdapter

class MySource(SourceAdapter):
    source_id = "my-source"
    countries = frozenset({"DE"})       # optional scope check

    def extract(self):
        for row in read_somewhere():
            yield RawRecord(key=row["id"], payload=row)

    def normalize(self, raw, ctx):
        return self.build_record(
            ctx,
            record_key=raw.key,
            country_code=raw.payload["country"],   # never default this
            region_code=raw.payload.get("region"),
            source_date=raw.payload["date"],
            attributes={"...": "..."},
            geom=raw.payload.get("wkt"),           # GeoJSON, WKT, WKB or None
        )
```

The class registers itself on definition and shows up in `iris-ingest list`.
`fixture_vienna_geojson.py` is the second adapter, written exactly this way.
`tests/test_extensibility.py` checks the claim: an adapter defined inside the
test file, one dropped into a new package, and an AST check that adapters only
import the public `iris_ingest.core` API.

## Layout

```
src/iris_ingest/
  core/
    record.py       CanonicalRecord, SourceMetadata, RejectedRecord
    adapter.py      SourceAdapter base class, RawRecord, registry
    geometry.py     GeoJSON/WKT/WKB -> canonical GeoJSON (EPSG:4326)
    countries.py    ISO 3166-1 list, region codes for pilot countries
    validation.py   contract checks, run for every source
    staging.py      JsonlSink, PostgisSink
    pipeline.py     run(adapter, sink) -> RunReport
  adapters/
    fixture_nrw_csv.py         CSV + WKT, 27 rows (22 valid)
    fixture_vienna_geojson.py  GeoJSON FeatureCollection, 7 features
  cli.py
migrations/001_staging.sql     staging schema (PostGIS)
fixtures/                      committed, deterministic input data
examples/                      normalized output of the fixture run
```

## Design decisions

**Adapter does mapping, core does judging.** If adapters validated their own
output, each new source would be a new chance to get it wrong. The pipeline
validates every record after `normalize`, and adapters can only add stricter,
source-specific checks (the NRW adapter rejects regions outside `NW`).

**country_code is never defaulted.** Validation is strict: exact uppercase
ISO 3166-1 alpha-2. `"de"`, `" DE"`, `"DEU"`, `""` and `None` are all rejected,
and the test checks the record was not quietly rewritten on the way. Adapters
can declare `countries` to reject valid codes that don't belong to the source.
Identity is `(country_code, source_id, record_key)` in Python and as a UNIQUE
constraint in SQL. The database has its own CHECK on `country_code`, so a bug
in Python still can't store a bad code.

**Geometry.** Field is `geom` everywhere. Inputs (GeoJSON, WKT, WKB bytes/hex)
are converted to a GeoJSON geometry in EPSG:4326, which round-trips losslessly
to WKB for PostGIS. `None` stays `None` (NW-007 has no geometry and is
accepted with `geom: null`). Empty, unparseable or invalid geometries are
rejected, not repaired with `buffer(0)`, because a repair can change area,
which matters for eco-point estimates. Coordinates outside lon/lat bounds are
rejected, which catches projected data mislabelled as 4326. Z is dropped.

**Rejects are data.** Rejected rows go to `rejected.jsonl` or
`staging.rejected_record` with reasons and the raw payload, so someone can
triage them. A bad row never aborts the run; a configuration problem does.

**Staging is idempotent and transactional.** `PostgisSink` upserts on the
identity key inside one transaction per run with a `batch_id`. Re-running a
source doesn't duplicate rows; a crashed run leaves nothing half written.

**fetched_at is injectable.** `--fetched-at` makes runs byte-for-byte
reproducible, which is what lets the example output double as a regression test.

## Simplifications and how they'd evolve

| Now | Production |
|---|---|
| Only EPSG:4326 sources; others are refused at run start | Reproject with pyproj in `geometry.py`; adapter still just declares `source_crs` |
| Region lists only for DE and AT | Full ISO 3166-2 table, or a reference table in PostGIS |
| Units are encoded in attribute names (`area_m2`) | Typed attribute schema per source (pydantic or JSON Schema) with units and uncertainty fields |
| All rows in one transaction | Batched `COPY` into a temp table then merge, for large sources |
| Staging only | Separate promotion step: staging -> curated tables after QA gates and review, recorded per `batch_id` |
| Single migration file run by hand | Migration tool (Alembic/sqitch) with version tracking |
| Fixtures stand in for remote sources | `extract` gets an HTTP/file client injected, with retries and a raw-payload archive for replay |

## Assumptions

* `source_date` is the date the source says the data is valid for; it must not
  be after `fetched_at`.
* A missing `region_code` is allowed and stored as NULL. Missing is recorded,
  not guessed.
* Attributes are passed through as the adapter maps them; the core does not
  interpret them.
