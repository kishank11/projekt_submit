"""Public API of the ingestion core. Adapters import from here only."""

from .adapter import (
    RawRecord,
    RunContext,
    SourceAdapter,
    get_adapter,
    registered_adapters,
)
from .errors import ConfigurationError, GeometryError, IrisIngestError, RecordRejected
from .geometry import CANONICAL_CRS, normalize_geometry, to_wkb_hex
from .pipeline import RunReport, run
from .record import CanonicalRecord, RejectedRecord, SourceMetadata
from .staging import JsonlSink, PostgisSink, StagingSink
from .validation import collect_problems, validate

__all__ = [
    "CANONICAL_CRS",
    "CanonicalRecord",
    "ConfigurationError",
    "GeometryError",
    "IrisIngestError",
    "JsonlSink",
    "PostgisSink",
    "RawRecord",
    "RecordRejected",
    "RejectedRecord",
    "RunContext",
    "RunReport",
    "SourceAdapter",
    "SourceMetadata",
    "StagingSink",
    "collect_problems",
    "get_adapter",
    "normalize_geometry",
    "registered_adapters",
    "run",
    "to_wkb_hex",
    "validate",
]
