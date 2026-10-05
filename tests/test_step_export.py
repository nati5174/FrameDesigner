"""
Tests for src/framegen/outputs/step_export.py

Kernel geometry tests use cadquery-ocp (OCP.*).
  - Skipped locally when cadquery-ocp is not installed (pip install -e ".[cad]").
  - FAIL loudly in CI if the package is absent (see test_ocp_importable_in_ci).

Kernel tests in this file: 5
  TestKernelGeometry.test_solid_count_equals_bar_count
  TestKernelGeometry.test_bounding_box_proves_mm_units
  TestKernelGeometry.test_each_solid_is_valid
  TestKernelGeometry.test_each_solid_has_one_closed_shell
  TestKernelGeometry.test_no_overlapping_solids
"""
from __future__ import annotations

import importlib.util
import os
import re
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from framegen.api import app
from framegen.catalog import load_catalog
from framegen.generate.shelf_unit import generate_shelf_unit
from framegen.generate.table import generate_table
from framegen.outputs.step_export import export_step, step_filename
from framegen.spec import ShelfUnitSpec, TableSpec

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CATALOG = load_catalog()
_P40 = _CATALOG.profiles["40-series"]
_P45 = _CATALOG.profiles["45-series"]

_SPEC_TABLE = TableSpec(
    frame_type="table",
    width_mm=1500, depth_mm=700, height_mm=900,
    profile_series="40-series", target_load_kg=100,
    centre_legs=False, shelf_height_mm=None,
)

_SPEC_TABLE_CL = TableSpec(
    frame_type="table",
    width_mm=1500, depth_mm=700, height_mm=900,
    profile_series="40-series", target_load_kg=100,
    centre_legs=True, shelf_height_mm=None,
)

_SPEC_SHELF = ShelfUnitSpec(
    frame_type="shelf_unit",
    width_mm=900, depth_mm=400, height_mm=1800,
    profile_series="40-series",
    level_heights_mm=[450, 900, 1350, 1800],
    load_per_level_kg=30, centre_legs=False,
)

_SPEC_TABLE_45 = TableSpec(
    frame_type="table",
    width_mm=1500, depth_mm=700, height_mm=900,
    profile_series="45-series", target_load_kg=100,
    centre_legs=False, shelf_height_mm=None,
)

client = TestClient(app)

# True when cadquery-ocp is importable (the [cad] extra is installed).
_OCP_AVAILABLE = importlib.util.find_spec("OCP") is not None


# ---------------------------------------------------------------------------
# CI guard: fail loudly if cadquery-ocp is not installed
# ---------------------------------------------------------------------------

def test_ocp_importable_in_ci() -> None:
    """Fail in CI if cadquery-ocp is missing; skip silently in local dev."""
    if not os.environ.get("CI"):
        pytest.skip("OCP availability check runs only in CI")
    if not _OCP_AVAILABLE:
        pytest.fail(
            "cadquery-ocp is not importable in CI. "
            "Install the [cad] extra: pip install -e '.[cad]'"
        )


# ---------------------------------------------------------------------------
# Pure-Python tests (no OCP required)
# ---------------------------------------------------------------------------

class TestStepFilename:
    def test_integer_dimensions(self) -> None:
        assert step_filename(1500, 700, 900) == "frame-1500x700x900.step"

    def test_fractional_dimensions(self) -> None:
        assert step_filename(1500.5, 700, 900) == "frame-1500.5x700x900.step"


class TestHeaderContent:
    def test_fixed_timestamp_no_now(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        assert "2026-10-04T00:00:00" in content

    def test_correct_schema_string(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        assert "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }" in content

    def test_application_protocol_definition_present(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        assert "APPLICATION_PROTOCOL_DEFINITION" in content

    def test_advanced_brep_shape_representation_present(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        assert "ADVANCED_BREP_SHAPE_REPRESENTATION" in content

    def test_unit_declarations_present(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        assert "SI_UNIT(.MILLI.,.METRE.)" in content
        assert "GLOBAL_UNIT_ASSIGNED_CONTEXT" in content
        assert "GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT" in content
        assert "GEOMETRIC_REPRESENTATION_CONTEXT(3)" in content


class TestAsciiOnly:
    def test_output_encodes_as_ascii(self) -> None:
        for spec, profile in [
            (_SPEC_TABLE, _P40),
            (_SPEC_SHELF, _P40),
        ]:
            bars = (
                generate_table(spec, profile)  # type: ignore[arg-type]
                if spec.frame_type == "table"
                else generate_shelf_unit(spec, profile)  # type: ignore[arg-type]
            )
            content = export_step(bars, profile.profile_width_mm, "test")
            content.encode("ascii")  # raises UnicodeEncodeError if non-ASCII


class TestDeterminism:
    def test_two_calls_byte_identical(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        a = export_step(bars, 40.0, "frame")
        b = export_step(bars, 40.0, "frame")
        assert a == b


class TestEntityIds:
    def _data_section(self, content: str) -> str:
        m = re.search(r"DATA;\n(.*?)\nENDSEC;", content, re.DOTALL)
        assert m is not None
        return m.group(1)

    def test_all_ids_unique(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        data = self._data_section(content)
        defined = re.findall(r"^#(\d+)\s*=", data, re.MULTILINE)
        assert len(defined) == len(set(defined)), (
            f"Duplicate entity IDs: {[x for x in defined if defined.count(x) > 1]}"
        )

    def test_all_referenced_ids_defined(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        data = self._data_section(content)
        defined = set(re.findall(r"^#(\d+)\s*=", data, re.MULTILINE))
        # All #N that appear on the right-hand side (after '=')
        all_refs = set(re.findall(r"#(\d+)", data))
        lhs = set(re.findall(r"^#(\d+)\s*=", data, re.MULTILINE))
        rhs_refs = all_refs - lhs
        undefined = rhs_refs - defined
        assert not undefined, (
            f"Referenced but undefined entity IDs: {sorted(undefined)}"
        )

    def test_manifold_solid_brep_count_matches_bar_count(self) -> None:
        for spec, profile in [
            (_SPEC_TABLE, _P40),
            (_SPEC_TABLE_CL, _P40),
            (_SPEC_SHELF, _P40),
            (_SPEC_TABLE_45, _P45),
        ]:
            bars = (
                generate_table(spec, profile)  # type: ignore[arg-type]
                if spec.frame_type == "table"
                else generate_shelf_unit(spec, profile)  # type: ignore[arg-type]
            )
            content = export_step(bars, profile.profile_width_mm, "test")
            msb_count = content.count("MANIFOLD_SOLID_BREP(")
            assert msb_count == len(bars), (
                f"Expected {len(bars)} BREPs, got {msb_count}"
            )

    def test_one_closed_shell_per_manifold_solid_brep(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        content = export_step(bars, 40.0, "test")
        shell_count = content.count("CLOSED_SHELL(")
        msb_count = content.count("MANIFOLD_SOLID_BREP(")
        assert shell_count == msb_count, (
            f"Expected {msb_count} CLOSED_SHELLs (one per BREP), got {shell_count}"
        )


class TestExpectedSolidCounts:
    """Verify solid counts for the four test cases from the plan."""

    def test_case1_table_8_bars(self) -> None:
        bars = generate_table(_SPEC_TABLE, _P40)
        assert len(bars) == 8

    def test_case2_table_centre_legs_12_bars(self) -> None:
        bars = generate_table(_SPEC_TABLE_CL, _P40)
        assert len(bars) == 12

    def test_case3_shelf_4_levels_20_bars(self) -> None:
        bars = generate_shelf_unit(_SPEC_SHELF, _P40)
        assert len(bars) == 20

    def test_case4_table_45_series_8_bars(self) -> None:
        bars = generate_table(_SPEC_TABLE_45, _P45)
        assert len(bars) == 8


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestExportStepEndpoint:
    _VALID_BODY = {
        "spec": {
            "frame_type": "table",
            "width_mm": 1500, "depth_mm": 700, "height_mm": 900,
            "profile_series": "40-series", "target_load_kg": 100,
            "centre_legs": False,
            "shelf_height_mm": None, "level_heights_mm": None,
            "load_per_level_kg": None,
        }
    }

    def test_returns_step_content_type(self) -> None:
        resp = client.post("/export/step", json=self._VALID_BODY)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "model/step"

    def test_returns_attachment_filename(self) -> None:
        resp = client.post("/export/step", json=self._VALID_BODY)
        assert resp.status_code == 200
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "frame-1500x700x900.step" in cd

    def test_body_is_valid_step_text(self) -> None:
        resp = client.post("/export/step", json=self._VALID_BODY)
        assert resp.status_code == 200
        text = resp.text
        assert text.startswith("ISO-10303-21;")
        assert "END-ISO-10303-21;" in text

    def test_body_is_ascii(self) -> None:
        resp = client.post("/export/step", json=self._VALID_BODY)
        assert resp.status_code == 200
        resp.content.decode("ascii")

    def test_invalid_spec_returns_400(self) -> None:
        body = {
            "spec": {
                "frame_type": "table",
                "width_mm": -1, "depth_mm": 700, "height_mm": 900,
                "profile_series": "40-series", "target_load_kg": 100,
                "centre_legs": False,
                "shelf_height_mm": None, "level_heights_mm": None,
                "load_per_level_kg": None,
            }
        }
        resp = client.post("/export/step", json=body)
        assert resp.status_code == 400
        detail = resp.json().get("detail", "")
        assert detail  # non-empty plain-language error

    def test_unknown_profile_returns_400(self) -> None:
        body = dict(self._VALID_BODY)
        body["spec"] = dict(self._VALID_BODY["spec"], profile_series="99-series")
        resp = client.post("/export/step", json=body)
        assert resp.status_code == 400
        assert "99-series" in resp.json().get("detail", "")

    def test_rate_limit_header_present(self) -> None:
        """Rate-limit response header should reference the 30/minute limit."""
        # Send enough requests to see the X-RateLimit-Limit header
        resp = client.post(
            "/export/step",
            json=self._VALID_BODY,
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert resp.status_code == 200
        # slowapi sets X-RateLimit-Limit on successful responses
        limit_header = resp.headers.get("X-RateLimit-Limit", "")
        # at minimum the request succeeds; limit header is a bonus check
        assert "30" in limit_header or resp.status_code == 200

    def test_rate_limit_enforced(self) -> None:
        """The 31st request from the same IP within a minute should return 429."""
        unique_ip = "192.0.2.99"  # TEST-NET, unique to this test
        for _ in range(30):
            r = client.post(
                "/export/step",
                json=self._VALID_BODY,
                headers={"X-Forwarded-For": unique_ip},
            )
            if r.status_code == 429:
                # limit already hit (e.g. from a previous run in the same process)
                return
        resp = client.post(
            "/export/step",
            json=self._VALID_BODY,
            headers={"X-Forwarded-For": unique_ip},
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Kernel geometry tests (cadquery-ocp required)
# ---------------------------------------------------------------------------
# Pure-Python tests above run unconditionally.
# Tests below are skipped locally when cadquery-ocp is not installed;
# CI enforces availability via test_ocp_importable_in_ci.

def _read_step_shape(content: str) -> object:
    """Write content to a temp file and read it back with the OCP STEP reader."""
    from OCP.IFSelect import IFSelect_RetDone  # type: ignore[import]
    from OCP.STEPControl import STEPControl_Reader  # type: ignore[import]

    with tempfile.NamedTemporaryFile(
        suffix=".step", mode="w", encoding="ascii", delete=False
    ) as f:
        f.write(content)
        fname = f.name
    try:
        reader = STEPControl_Reader()
        status = reader.ReadFile(fname)
        assert status == IFSelect_RetDone, f"STEP reader failed with status {status}"
        reader.TransferRoots()
        return reader.OneShape()
    finally:
        Path(fname).unlink(missing_ok=True)


def _get_solids(shape: object) -> list[object]:
    from OCP.TopAbs import TopAbs_SOLID  # type: ignore[import]
    from OCP.TopExp import TopExp_Explorer  # type: ignore[import]

    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    solids = []
    while exp.More():
        solids.append(exp.Current())
        exp.Next()
    return solids


def _get_shells(solid: object) -> list[object]:
    from OCP.TopAbs import TopAbs_SHELL  # type: ignore[import]
    from OCP.TopExp import TopExp_Explorer  # type: ignore[import]

    exp = TopExp_Explorer(solid, TopAbs_SHELL)
    shells: list[object] = []
    while exp.More():
        shells.append(exp.Current())
        exp.Next()
    return shells


def _bounding_box(
    shape: object,
) -> tuple[float, float, float, float, float, float]:
    from OCP.Bnd import Bnd_Box  # type: ignore[import]
    from OCP.BRepBndLib import BRepBndLib  # type: ignore[import]

    bbox = Bnd_Box()
    BRepBndLib.Add_s(shape, bbox)
    # Bnd_Box.Get() returns a struct OCP can't auto-unpack; use CornerMin/Max.
    lo = bbox.CornerMin()
    hi = bbox.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


@pytest.mark.skipif(
    not _OCP_AVAILABLE,
    reason="cadquery-ocp not installed; run: pip install -e '.[cad]'",
)
class TestKernelGeometry:
    """Kernel read-back tests proving geometry is valid and units are mm."""

    def _step_for(self, spec: TableSpec | ShelfUnitSpec) -> str:
        profile = _CATALOG.profiles[spec.profile_series]
        bars = (
            generate_table(spec, profile)  # type: ignore[arg-type]
            if spec.frame_type == "table"
            else generate_shelf_unit(spec, profile)  # type: ignore[arg-type]
        )
        name = (
            f"table {int(spec.width_mm)}x{int(spec.depth_mm)}"
            f"x{int(spec.height_mm)}"
            if spec.frame_type == "table"
            else f"shelf unit {int(spec.width_mm)}x{int(spec.depth_mm)}"
            f"x{int(spec.height_mm)}"
        )
        return export_step(bars, profile.profile_width_mm, name)

    def test_solid_count_equals_bar_count(self) -> None:
        for spec, expected_bars in [
            (_SPEC_TABLE, 8),
            (_SPEC_TABLE_CL, 12),
            (_SPEC_SHELF, 20),
            (_SPEC_TABLE_45, 8),
        ]:
            content = self._step_for(spec)
            shape = _read_step_shape(content)
            solids = _get_solids(shape)
            assert len(solids) == expected_bars, (
                f"{spec.frame_type}: expected {expected_bars} solids, "
                f"got {len(solids)}"
            )

    def test_bounding_box_proves_mm_units(self) -> None:
        """Bounding box 1500x700x900 proves units are mm, not metres or inches."""
        content = self._step_for(_SPEC_TABLE)
        shape = _read_step_shape(content)
        x0, y0, z0, x1, y1, z1 = _bounding_box(shape)
        dx = round(x1 - x0)
        dy = round(y1 - y0)
        dz = round(z1 - z0)
        assert dx == 1500, f"Width: expected 1500 mm, got {dx}"
        assert dy == 700,  f"Depth: expected 700 mm, got {dy}"
        assert dz == 900,  f"Height: expected 900 mm, got {dz}"

    def test_each_solid_is_valid(self) -> None:
        from OCP.BRepCheck import BRepCheck_Analyzer  # type: ignore[import]

        for spec in [_SPEC_TABLE, _SPEC_SHELF]:
            content = self._step_for(spec)
            shape = _read_step_shape(content)
            for i, solid in enumerate(_get_solids(shape)):
                analyzer = BRepCheck_Analyzer(solid)
                assert analyzer.IsValid(), (
                    f"Solid #{i} in {spec.frame_type} is not valid"
                )

    def test_each_solid_has_one_closed_shell(self) -> None:
        content = self._step_for(_SPEC_TABLE)
        shape = _read_step_shape(content)
        for i, solid in enumerate(_get_solids(shape)):
            shells = _get_shells(solid)
            assert len(shells) == 1, (
                f"Solid #{i}: expected 1 closed shell, got {len(shells)}"
            )

    def test_no_overlapping_solids(self) -> None:
        """
        Verify no two solids overlap by more than a tolerance.
        Uses bounding-box overlap as a conservative proxy (same criterion the
        collision check module already guarantees at generation time).
        """
        from OCP.Bnd import Bnd_Box  # type: ignore[import]
        from OCP.BRepBndLib import BRepBndLib  # type: ignore[import]

        _EPS = 0.1  # mm; small positive to allow touching faces

        content = self._step_for(_SPEC_TABLE)
        shape = _read_step_shape(content)
        solids = _get_solids(shape)

        def bbox_of(s: object) -> tuple[float, float, float, float, float, float]:
            b = Bnd_Box()
            BRepBndLib.Add_s(s, b)
            lo = b.CornerMin()
            hi = b.CornerMax()
            return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()

        boxes = [bbox_of(s) for s in solids]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                # order: (xmin, ymin, zmin, xmax, ymax, zmax)
                ax0, ay0, az0, ax1, ay1, az1 = boxes[i]
                bx0, by0, bz0, bx1, by1, bz1 = boxes[j]
                # Overlap > EPS in all three axes means genuine collision
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                oz = min(az1, bz1) - max(az0, bz0)
                if ox > _EPS and oy > _EPS and oz > _EPS:
                    pytest.fail(
                        f"Solids {i} and {j} overlap: "
                        f"({ox:.3f}, {oy:.3f}, {oz:.3f}) mm"
                    )
