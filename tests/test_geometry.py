import pytest
from shapely.geometry import Point

from iris_ingest.core import GeometryError, normalize_geometry, to_wkb_hex

SQUARE_WKT = "POLYGON((6.7 51.4, 6.71 51.4, 6.71 51.41, 6.7 51.41, 6.7 51.4))"


def test_none_stays_none():
    assert normalize_geometry(None) is None


@pytest.mark.parametrize(
    "value",
    [
        SQUARE_WKT,
        {"type": "Polygon", "coordinates": [[[6.7, 51.4], [6.71, 51.4], [6.71, 51.41], [6.7, 51.41], [6.7, 51.4]]]},
        Point(6.7, 51.4).buffer(0.001).wkb,
        Point(6.7, 51.4).buffer(0.001).wkb_hex,
    ],
    ids=["wkt", "geojson", "wkb-bytes", "wkb-hex"],
)
def test_inputs_normalize_to_geojson(value):
    out = normalize_geometry(value)
    assert out["type"] == "Polygon"
    assert isinstance(out["coordinates"][0][0], list)  # lists, not tuples


def test_all_representations_agree():
    from_wkt = normalize_geometry(SQUARE_WKT)
    from_wkb = normalize_geometry(to_wkb_hex(from_wkt))
    assert from_wkt == from_wkb


def test_z_is_dropped():
    assert normalize_geometry("POINT Z (6.7 51.4 30)") == {"type": "Point", "coordinates": [6.7, 51.4]}


@pytest.mark.parametrize(
    "value, fragment",
    [
        ("POLYGON((0 0, 1 1, 1 0, 0 1, 0 0))", "invalid"),
        ("POLYGON EMPTY", "empty"),
        ("not a geometry", "could not be parsed"),
        ("", "empty string"),
        ("POINT(350000 5700000)", "outside EPSG:4326"),  # UTM coordinates mislabelled
        ({"type": "Feature", "geometry": None, "properties": {}}, "Feature"),
        (42, "unsupported"),
    ],
)
def test_bad_geometry_is_rejected(value, fragment):
    with pytest.raises(GeometryError) as exc:
        normalize_geometry(value)
    assert fragment in str(exc.value)
