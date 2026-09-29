"""The adapter interface. This is the only thing a new source has to implement.

A source adapter answers two questions:

1. ``extract``: what raw rows does the source have?
2. ``normalize``: how does one raw row map onto the canonical contract?

It does *not* validate against the contract, touch the database, or decide
what happens to bad rows. The pipeline does that, identically for every source.

Adapters register themselves when their class is defined. Nothing in the core
needs editing to add one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, ClassVar

from .errors import ConfigurationError, RecordRejected
from .geometry import CANONICAL_CRS, normalize_geometry
from .record import CanonicalRecord, SourceMetadata


@dataclass(frozen=True, slots=True)
class RawRecord:
    """A row as the source delivered it, plus a key for error reporting."""

    key: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class RunContext:
    fetched_at: datetime


_REGISTRY: dict[str, type[SourceAdapter]] = {}


class SourceAdapter(ABC):
    #: stable identifier of the source, e.g. "fixture-nrw-csv"
    source_id: ClassVar[str]
    #: countries this source may legitimately contain; None means "any valid code"
    countries: ClassVar[frozenset[str] | None] = None
    #: CRS of geometries the source delivers
    source_crs: ClassVar[str] = CANONICAL_CRS

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return  # intermediate base classes don't register
        source_id = getattr(cls, "source_id", None)
        if not source_id:
            raise ConfigurationError(f"{cls.__name__} must define source_id")
        existing = _REGISTRY.get(source_id)
        if existing is not None and existing.__qualname__ != cls.__qualname__:
            raise ConfigurationError(
                f"source_id {source_id!r} already registered by {existing.__name__}"
            )
        _REGISTRY[source_id] = cls

    # ---- the two methods a source implements --------------------------------

    @abstractmethod
    def extract(self) -> Iterable[RawRecord]:
        """Yield raw records. No transformation beyond reading the source."""

    @abstractmethod
    def normalize(self, raw: RawRecord, ctx: RunContext) -> CanonicalRecord:
        """Map one raw record to the canonical contract.

        Raise ``RecordRejected`` for rows the adapter can already tell are bad.
        Use ``build_record`` so metadata and geometry are handled consistently.
        Never fall back to a default country_code.
        """

    # ---- helper for implementations ----------------------------------------

    def build_record(
        self,
        ctx: RunContext,
        *,
        record_key: str,
        country_code: str | None,
        source_date: date | str,
        region_code: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        geom: Any = None,
    ) -> CanonicalRecord:
        if country_code is None or (isinstance(country_code, str) and not country_code.strip()):
            raise RecordRejected("country_code is missing")
        if isinstance(source_date, str):
            try:
                source_date = date.fromisoformat(source_date)
            except ValueError as exc:
                raise RecordRejected(f"source_date {source_date!r} is not ISO 8601") from exc

        return CanonicalRecord(
            metadata=SourceMetadata(
                source_id=self.source_id,
                source_date=source_date,
                fetched_at=ctx.fetched_at,
                country_code=country_code,
                region_code=region_code or None,
            ),
            record_key=record_key,
            attributes=dict(attributes or {}),
            geom=normalize_geometry(geom),
        )


def registered_adapters() -> dict[str, type[SourceAdapter]]:
    return dict(_REGISTRY)


def get_adapter(source_id: str) -> type[SourceAdapter]:
    try:
        return _REGISTRY[source_id]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise ConfigurationError(
            f"unknown source {source_id!r} (registered: {known})"
        ) from None
