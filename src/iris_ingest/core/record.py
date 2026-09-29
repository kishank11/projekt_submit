"""The canonical record contract.

Everything downstream of an adapter (validation, staging, promotion) only ever
sees ``CanonicalRecord``. Source metadata is a separate, explicit object so it
cannot get lost inside free-form attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .geometry import GeoJSON


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    source_id: str
    source_date: date
    fetched_at: datetime
    country_code: str
    region_code: str | None = None


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    """One normalized record.

    ``record_key`` identifies the record inside its source. Together with
    ``source_id`` and ``country_code`` it forms the country-scoped identity.
    ``geom`` is a GeoJSON geometry in EPSG:4326 or None for tabular records.
    """

    metadata: SourceMetadata
    record_key: str
    attributes: dict[str, Any] = field(default_factory=dict)
    geom: GeoJSON | None = None

    # convenience accessors so callers don't have to reach into metadata
    @property
    def country_code(self) -> str:
        return self.metadata.country_code

    @property
    def source_id(self) -> str:
        return self.metadata.source_id

    def identity(self) -> tuple[str, str, str]:
        return (self.metadata.country_code, self.metadata.source_id, self.record_key)

    def to_dict(self) -> dict[str, Any]:
        """Flat JSON-ready shape, matching the contract in the assignment."""
        m = self.metadata
        return {
            "country_code": m.country_code,
            "region_code": m.region_code,
            "source_id": m.source_id,
            "source_date": m.source_date.isoformat(),
            "fetched_at": m.fetched_at.isoformat(),
            "record_key": self.record_key,
            "attributes": self.attributes,
            "geom": self.geom,
        }


@dataclass(frozen=True, slots=True)
class RejectedRecord:
    source_id: str
    record_key: str
    reasons: list[str]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "record_key": self.record_key,
            "reasons": self.reasons,
            "raw": self.raw,
        }
