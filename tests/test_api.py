from __future__ import annotations

from fastapi.testclient import TestClient

from framegen.api import app

client = TestClient(app)


# ── No shelf ──────────────────────────────────────────────────────────────────

def test_no_shelf_status() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    assert resp.status_code == 200


def test_no_shelf_bar_count() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    bars = resp.json()["bars"]
    assert len(bars) == 8


def test_no_shelf_roles() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    bars = resp.json()["bars"]
    by_role: dict[str, int] = {}
    for bar in bars:
        by_role[bar["role"]] = by_role.get(bar["role"], 0) + 1
    assert by_role["leg"] == 4
    assert by_role["top_rail_width"] == 2
    assert by_role["top_rail_depth"] == 2


def test_no_shelf_lengths() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    bars = resp.json()["bars"]
    # derive length from start/end coordinates
    import math
    def length(b: dict) -> float:  # type: ignore[type-arg]
        s, e = b["start"], b["end"]
        return math.dist(s, e)

    by_role: dict[str, list[float]] = {}
    for bar in bars:
        by_role.setdefault(bar["role"], []).append(round(length(bar), 6))

    assert sorted(by_role["leg"]) == [900.0, 900.0, 900.0, 900.0]
    assert sorted(by_role["top_rail_width"]) == [1420.0, 1420.0]
    assert sorted(by_role["top_rail_depth"]) == [620.0, 620.0]


def test_no_shelf_cut_list_total() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    rows = resp.json()["cut_list"]
    total = sum(r["total_mm"] for r in rows)
    assert total == 7680.0


def test_bar_coordinates_are_triples() -> None:
    resp = client.get("/frame", params={"width": 1500, "depth": 700, "height": 900})
    for bar in resp.json()["bars"]:
        assert len(bar["start"]) == 3
        assert len(bar["end"]) == 3
        assert all(isinstance(v, (int, float)) for v in bar["start"])
        assert all(isinstance(v, (int, float)) for v in bar["end"])


# ── With shelf ────────────────────────────────────────────────────────────────

def test_with_shelf_bar_count() -> None:
    resp = client.get(
        "/frame", params={"width": 1500, "depth": 700, "height": 900, "shelf": 300}
    )
    assert len(resp.json()["bars"]) == 12


def test_with_shelf_cut_list_total() -> None:
    resp = client.get(
        "/frame", params={"width": 1500, "depth": 700, "height": 900, "shelf": 300}
    )
    rows = resp.json()["cut_list"]
    total = sum(r["total_mm"] for r in rows)
    assert total == 11760.0


# ── Error cases ───────────────────────────────────────────────────────────────

def test_shelf_above_height_returns_400() -> None:
    resp = client.get(
        "/frame", params={"width": 1500, "depth": 700, "height": 900, "shelf": 950}
    )
    assert resp.status_code == 400
    assert "shelf_height_mm" in resp.json()["detail"]


def test_unknown_series_returns_400() -> None:
    resp = client.get(
        "/frame",
        params={"width": 1500, "depth": 700, "height": 900, "series": "99-series"},
    )
    assert resp.status_code == 400
    assert "unknown series" in resp.json()["detail"]
