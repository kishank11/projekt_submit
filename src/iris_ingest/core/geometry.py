"""Geometry normalization.

Adapters hand over whatever the source gives them (GeoJSON mapping, WKT text,
WKB bytes or hex). The core turns it into one representation: a GeoJSON
geometry mapping in EPSG:4326. From there WKB/WKT for PostGIS is one call away.

Rules:
* ``None`` stays ``None``. We never invent a geometry.
* Unparseable, empty or topologically invalid input is rejected, not repaired.
* Coordinates outside lon/lat bounds are rejected. That catches projected
  coordinates that were labelled as EPSG:4326 and swapped axes in most cases.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import shapely
from shapely import wkb, wkt
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

from .errors import GeometryError

CANONICAL_CRS = "EPSG:4326"

GeoJSON = dict[str, Any]


def _parse(value: Any) -> BaseGeometry:
    if isinstance(value, BaseGeometry):
        return value
    if isinstance(value, Mapping):
        if value.get("type") == "Feature":
            raise GeometryError("geom must be a geometry, got a GeoJSON Feature")
        return shape(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return wkb.loads(bytes(value))
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise GeometryError("geom is an empty string")
        if all(c in "0123456789abcdefABCDEF" for c in text):
            return wkb.loads(text, hex=True)
        return wkt.loads(text)
    raise GeometryError(f"unsupported geometry input type {type(value).__name__}")


def normalize_geometry(value: Any) -> GeoJSON | None:
    """Return a GeoJSON geometry mapping in EPSG:4326, or None if value is None."""
    if value is None:
        return None
    try:
        geom = _parse(value)
    except GeometryError:
        raise
    except Exception as exc:  # shapely raises several different types here
        raise GeometryError(f"geom could not be parsed: {exc}") from exc

    if geom.is_empty:
        raise GeometryError("geom is empty")
    if shapely.has_z(geom):
        geom = shapely.force_2d(geom)
    if not geom.is_valid:
        raise GeometryError(f"geom is invalid: {explain_validity(geom)}")

    minx, miny, maxx, maxy = geom.bounds
    if minx < -180 or maxx > 180 or miny < -90 or maxy > 90:
        raise GeometryError(
            f"geom bounds {geom.bounds} are outside EPSG:4326; "
            "is the source in a projected CRS?"
        )

    # json round trip turns shapely's tuples into plain lists so output is stable
    return json.loads(json.dumps(mapping(geom)))


def to_wkb_hex(geom: GeoJSON | None) -> str | None:
    """Canonical GeoJSON -> WKB hex (what PostGIS accepts via ST_GeomFromWKB)."""
    if geom is None:
        return None
    return shape(geom).wkb_hex
