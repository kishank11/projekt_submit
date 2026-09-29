"""Load-to-staging.

A sink receives accepted and rejected records from the pipeline. Two sinks ship:

* ``JsonlSink``: writes ``accepted.jsonl`` and ``rejected.jsonl``. Default, no
  infrastructure needed.
* ``PostgisSink``: writes into the staging schema from ``migrations/``. Needs
  ``psycopg`` (``pip install .[postgres]``).

Staging is deliberately not the final table. Promotion to curated tables is a
separate, reviewed step (see README).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import IO, Self
from uuid import uuid4

from .errors import ConfigurationError
from .geometry import to_wkb_hex
from .record import CanonicalRecord, RejectedRecord


class StagingSink(ABC):
    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close(success=exc_type is None)

    def open(self) -> None:  # noqa: B027 - optional hook
        pass

    @abstractmethod
    def write_accepted(self, record: CanonicalRecord) -> None: ...

    @abstractmethod
    def write_rejected(self, rejected: RejectedRecord) -> None: ...

    def close(self, success: bool = True) -> None:  # noqa: B027 - optional hook
        pass


def _dumps(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class JsonlSink(StagingSink):
    def __init__(self, out_dir: str | Path):
        self.out_dir = Path(out_dir)
        self._accepted: IO[str] | None = None
        self._rejected: IO[str] | None = None

    def open(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._accepted = (self.out_dir / "accepted.jsonl").open("w", encoding="utf-8")
        self._rejected = (self.out_dir / "rejected.jsonl").open("w", encoding="utf-8")

    def write_accepted(self, record: CanonicalRecord) -> None:
        assert self._accepted is not None, "sink not opened"
        self._accepted.write(_dumps(record.to_dict()) + "\n")

    def write_rejected(self, rejected: RejectedRecord) -> None:
        assert self._rejected is not None, "sink not opened"
        self._rejected.write(_dumps(rejected.to_dict()) + "\n")

    def close(self, success: bool = True) -> None:
        for fh in (self._accepted, self._rejected):
            if fh is not None:
                fh.close()


class PostgisSink(StagingSink):
    """Writes one batch per run inside a single transaction.

    Re-running the same source upserts by (country_code, source_id, record_key),
    so staging stays idempotent. A failed run rolls back completely.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.batch_id = uuid4()
        self._conn = None

    def open(self) -> None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on install
            raise ConfigurationError(
                "PostgisSink needs psycopg: pip install '.[postgres]'"
            ) from exc
        self._conn = psycopg.connect(self.dsn)

    def write_accepted(self, record: CanonicalRecord) -> None:
        m = record.metadata
        self._conn.execute(
            """
            INSERT INTO staging.source_record
                (country_code, region_code, source_id, record_key, source_date,
                 fetched_at, attributes, geom, batch_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb,
                    ST_SetSRID(ST_GeomFromWKB(decode(%s, 'hex')), 4326), %s)
            ON CONFLICT (country_code, source_id, record_key) DO UPDATE SET
                region_code = EXCLUDED.region_code,
                source_date = EXCLUDED.source_date,
                fetched_at  = EXCLUDED.fetched_at,
                attributes  = EXCLUDED.attributes,
                geom        = EXCLUDED.geom,
                batch_id    = EXCLUDED.batch_id
            """,
            (
                m.country_code,
                m.region_code,
                m.source_id,
                record.record_key,
                m.source_date,
                m.fetched_at,
                _dumps(record.attributes),
                to_wkb_hex(record.geom),
                self.batch_id,
            ),
        )

    def write_rejected(self, rejected: RejectedRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO staging.rejected_record
                (source_id, record_key, reasons, raw, batch_id)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            """,
            (
                rejected.source_id,
                rejected.record_key,
                rejected.reasons,
                _dumps(rejected.raw),
                self.batch_id,
            ),
        )

    def close(self, success: bool = True) -> None:
        if self._conn is None:
            return
        if success:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
