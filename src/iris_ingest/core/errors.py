"""Errors raised by the ingestion core.

Record-level errors (``RecordRejected`` and subclasses) are expected during a run:
the pipeline catches them and writes the record to the reject channel. Anything
else is a bug or a configuration problem and aborts the run.
"""

from __future__ import annotations


class IrisIngestError(Exception):
    """Base class for all ingestion errors."""


class ConfigurationError(IrisIngestError):
    """An adapter or sink is set up in a way the core does not support."""


class RecordRejected(IrisIngestError):
    """A single record cannot be accepted. Carries machine-readable reasons."""

    def __init__(self, reasons: list[str] | str):
        if isinstance(reasons, str):
            reasons = [reasons]
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


class GeometryError(RecordRejected):
    """Geometry is present but cannot be parsed or is invalid."""
