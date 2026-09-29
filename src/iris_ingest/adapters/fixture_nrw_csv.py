"""Fixture adapter: NRW site survey delivered as CSV with WKT geometry.

Stands in for a remote tabular source. The file is committed so runs are
deterministic.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

from iris_ingest.core import (
    CanonicalRecord,
    RawRecord,
    RecordRejected,
    RunContext,
    SourceAdapter,
)

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "nrw_sites.csv"


class NrwSitesCsvAdapter(SourceAdapter):
    source_id = "fixture-nrw-csv"
    countries = frozenset({"DE"})
    #: this source only covers North Rhine-Westphalia
    regions = frozenset({"NW"})

    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)

    def extract(self) -> Iterator[RawRecord]:
        with self.path.open(newline="", encoding="utf-8") as fh:
            for line_no, row in enumerate(csv.DictReader(fh), start=2):
                key = (row.get("site_ref") or "").strip() or f"line-{line_no}"
                yield RawRecord(key=key, payload=row)

    def normalize(self, raw: RawRecord, ctx: RunContext) -> CanonicalRecord:
        row = raw.payload
        region = (row.get("region") or "").strip() or None
        if region is not None and region not in self.regions:
            raise RecordRejected(
                f"region_code {region!r} outside source coverage {sorted(self.regions)}"
            )

        area_raw = (row.get("area_m2") or "").strip()
        try:
            area = float(area_raw) if area_raw else None
        except ValueError as exc:
            raise RecordRejected(f"area_m2 {area_raw!r} is not a number") from exc

        return self.build_record(
            ctx,
            record_key=raw.key,
            # passed through as-is: an empty or wrong code must fail, not become DE
            country_code=(row.get("country") or "").strip(),
            region_code=region,
            source_date=(row.get("surveyed_on") or "").strip(),
            attributes={
                "land_use": (row.get("land_use") or "").strip() or None,
                "area_m2": area,
            },
            geom=(row.get("wkt") or "").strip() or None,
        )
