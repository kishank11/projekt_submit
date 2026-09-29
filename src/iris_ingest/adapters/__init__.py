"""Concrete adapters.

Every module in this package is imported by ``load_builtin_adapters``, and each
``SourceAdapter`` subclass registers itself. Adding a source means adding a file
here (or shipping it in another package via the ``iris_ingest.adapters`` entry
point group). No core module changes.
"""

from __future__ import annotations

import importlib
import pkgutil
from importlib.metadata import entry_points


def load_builtin_adapters() -> None:
    for mod in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{mod.name}")


def load_plugin_adapters() -> None:
    for ep in entry_points(group="iris_ingest.adapters"):
        ep.load()


def load_all() -> None:
    load_builtin_adapters()
    load_plugin_adapters()
