from datetime import UTC, datetime
from pathlib import Path

import pytest

from iris_ingest.adapters import load_all

ROOT = Path(__file__).resolve().parents[1]
FIXED_TS = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="session", autouse=True)
def _adapters_loaded():
    load_all()


@pytest.fixture
def fixed_ts():
    return FIXED_TS
