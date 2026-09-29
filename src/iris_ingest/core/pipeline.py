"""Runs one adapter end to end: extract -> normalize -> validate -> stage.

This module knows nothing about any particular source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .adapter import RunContext, SourceAdapter
from .errors import ConfigurationError, RecordRejected
from .geometry import CANONICAL_CRS
from .record import RejectedRecord
from .staging import StagingSink
from .validation import validate


@dataclass
class RunReport:
    source_id: str
    extracted: int = 0
    accepted: int = 0
    rejected: int = 0
    reject_reasons: dict[str, list[str]] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"{self.source_id}: extracted={self.extracted} "
            f"accepted={self.accepted} rejected={self.rejected}"
        )


def _jsonable(payload: Any) -> dict[str, Any]:
    try:
        return {str(k): v for k, v in dict(payload).items()}
    except Exception:
        return {"repr": repr(payload)}


def run(
    adapter: SourceAdapter,
    sink: StagingSink,
    fetched_at: datetime | None = None,
) -> RunReport:
    if adapter.source_crs != CANONICAL_CRS:
        # Reprojection is out of scope for this slice; refusing is safer than
        # writing coordinates in the wrong CRS.
        raise ConfigurationError(
            f"{type(adapter).__name__} declares {adapter.source_crs}; "
            f"only {CANONICAL_CRS} is supported without reprojection"
        )

    ctx = RunContext(fetched_at=fetched_at or datetime.now(UTC))
    report = RunReport(source_id=adapter.source_id)

    with sink:
        for raw in adapter.extract():
            report.extracted += 1
            try:
                record = adapter.normalize(raw, ctx)
                if record.source_id != adapter.source_id:
                    raise RecordRejected(
                        f"adapter emitted source_id {record.source_id!r}, "
                        f"expected {adapter.source_id!r}"
                    )
                validate(record, adapter.countries)
            except RecordRejected as exc:
                report.rejected += 1
                report.reject_reasons[raw.key] = exc.reasons
                sink.write_rejected(
                    RejectedRecord(
                        source_id=adapter.source_id,
                        record_key=raw.key,
                        reasons=exc.reasons,
                        raw=_jsonable(raw.payload),
                    )
                )
                continue
            report.accepted += 1
            sink.write_accepted(record)

    return report
