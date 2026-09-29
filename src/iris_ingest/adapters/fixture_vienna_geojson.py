"""Second fixture adapter: Vienna parcels delivered as a GeoJSON FeatureCollection.

It exists to prove the contract: it only subclasses ``SourceAdapter`` and uses
the public ``iris_ingest.core`` API. Nothing in the core was changed for it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from iris_ingest.core import CanonicalRecord, RawRecord, RunContext, SourceAdapter

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "vienna_parcels.geojson"


class ViennaParcelsGeoJsonAdapter(SourceAdapter):
    source_id = "fixture-vienna-geojson"
    countries = frozenset({"AT"})

    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)

    def extract(self) -> Iterator[RawRecord]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for idx, feature in enumerate(data.get("features", [])):
            props = feature.get("properties") or {}
            key = str(props.get("parcel_id") or f"feature-{idx}")
            yield RawRecord(key=key, payload=feature)

    def normalize(self, raw: RawRecord, ctx: RunContext) -> CanonicalRecord:
        props = dict(raw.payload.get("properties") or {})
        return self.build_record(
            ctx,
            record_key=raw.key,
            country_code=props.pop("country", None),
            region_code=props.pop("state", None),
            source_date=props.pop("valid_from", None) or "",
            attributes={k: v for k, v in props.items() if k != "parcel_id"},
            geom=raw.payload.get("geometry"),
        )
