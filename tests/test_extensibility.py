"""A new source must be addable by subclassing only, without touching the core."""

import ast
import importlib
import sys
import textwrap
from pathlib import Path

import pytest

from iris_ingest.core import (
    ConfigurationError,
    JsonlSink,
    RawRecord,
    SourceAdapter,
    get_adapter,
    registered_adapters,
    run,
)

ADAPTERS_DIR = Path(__file__).resolve().parents[1] / "src" / "iris_ingest" / "adapters"


class InMemoryAdapter(SourceAdapter):
    """Defined here, in a test file, only by implementing the interface."""

    source_id = "test-in-memory"
    countries = frozenset({"HU", "DE"})

    ROWS = [
        {"id": "a", "cc": "HU", "rc": "BU", "d": "2026-08-01", "wkt": "POINT(19.04 47.50)"},
        {"id": "b", "cc": "DE", "rc": None, "d": "2026-08-02", "wkt": None},
        {"id": "c", "cc": "XX", "rc": None, "d": "2026-08-03", "wkt": None},
        {"id": "d", "cc": "FR", "rc": None, "d": "2026-08-04", "wkt": None},
    ]

    def extract(self):
        for row in self.ROWS:
            yield RawRecord(key=row["id"], payload=row)

    def normalize(self, raw, ctx):
        p = raw.payload
        return self.build_record(
            ctx,
            record_key=raw.key,
            country_code=p["cc"],
            region_code=p["rc"],
            source_date=p["d"],
            geom=p["wkt"],
        )


def test_subclass_registers_itself():
    assert get_adapter("test-in-memory") is InMemoryAdapter


def test_new_adapter_runs_through_unchanged_core(tmp_path, fixed_ts):
    report = run(InMemoryAdapter(), JsonlSink(tmp_path), fetched_at=fixed_ts)
    assert report.accepted == 2
    assert set(report.reject_reasons) == {"c", "d"}


def test_adapter_dropped_into_package_is_discovered(tmp_path, monkeypatch):
    """Simulates a colleague adding a new file to a plugin package."""
    pkg = tmp_path / "extra_sources"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "dummy.py").write_text(
        textwrap.dedent(
            """
            from iris_ingest.core import SourceAdapter

            class DummyAdapter(SourceAdapter):
                source_id = "test-dropped-in"
                def extract(self):
                    return []
                def normalize(self, raw, ctx):
                    raise NotImplementedError
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.import_module("extra_sources.dummy")
    assert "test-dropped-in" in registered_adapters()
    sys.modules.pop("extra_sources.dummy", None)


def test_incomplete_adapter_cannot_be_instantiated():
    class Half(SourceAdapter):
        source_id = "test-half"

        def extract(self):
            return []

    with pytest.raises(TypeError):
        Half()


def test_duplicate_source_id_is_refused():
    with pytest.raises(ConfigurationError, match="already registered"):

        class Clash(SourceAdapter):
            source_id = "fixture-nrw-csv"

            def extract(self):
                return []

            def normalize(self, raw, ctx):
                raise NotImplementedError


def test_non_4326_source_is_refused(tmp_path):
    class Projected(InMemoryAdapter):
        source_id = "test-projected"
        source_crs = "EPSG:25832"

    with pytest.raises(ConfigurationError, match="EPSG:25832"):
        run(Projected(), JsonlSink(tmp_path))


@pytest.mark.parametrize("module", sorted(p.name for p in ADAPTERS_DIR.glob("fixture_*.py")))
def test_adapters_only_use_public_core_api(module):
    """Adapters may import iris_ingest.core, never its internals."""
    tree = ast.parse((ADAPTERS_DIR / module).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("iris_ingest"):
            assert node.module == "iris_ingest.core", f"{module} imports {node.module}"
