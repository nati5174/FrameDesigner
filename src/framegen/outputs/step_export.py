"""
Pure-Python writer for STEP AP214 (AUTOMOTIVE_DESIGN) files.

Generates one MANIFOLD_SOLID_BREP per bar as an axis-aligned box solid.
All geometry is expressed in millimetres.  No production dependencies.

Schema: AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }
Units:  millimetre, radian, steradian (GLOBAL_UNIT_ASSIGNED_CONTEXT).

Simplified: square cross-section bars without T-slots, end holes,
or brackets.  For checking fit and layout only.
"""
from __future__ import annotations

from framegen.generate import Bar

# Fixed timestamp -- no datetime.now() calls so output is deterministic.
_TIMESTAMP = "2026-10-04T00:00:00"
_SCHEMA = "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }"
_APP_PROTOCOL = "automotive_design"
_APP_CTX_STR = "core data for automotive mechanical design process"


def _role_label(role: str) -> str:
    """Convert internal role identifier to plain label (underscores to spaces)."""
    return role.replace("_", " ")


def _v(val: float) -> str:
    """Format a float for STEP output: 6 decimal places, no scientific notation."""
    return f"{val:.6f}"


class _C:
    """Monotonically-increasing entity-ID counter, resetting per file."""

    __slots__ = ("_n",)

    def __init__(self) -> None:
        self._n = 0

    def __call__(self) -> int:
        self._n += 1
        return self._n


def _bbox(
    bar: Bar, p: float
) -> tuple[float, float, float, float, float, float]:
    """
    Return (xmin, xmax, ymin, ymax, zmin, zmax) for a bar with profile width p.

    Bars are axis-aligned.  The profile extends p/2 on each side of its
    centreline in the two transverse directions.
    """
    s, e = bar.start, bar.end
    h = p / 2.0
    if s.x != e.x:  # along X (width rail)
        return (min(s.x, e.x), max(s.x, e.x), s.y - h, s.y + h, s.z - h, s.z + h)
    if s.y != e.y:  # along Y (depth rail)
        return (s.x - h, s.x + h, min(s.y, e.y), max(s.y, e.y), s.z - h, s.z + h)
    # along Z (leg or centre leg)
    return (s.x - h, s.x + h, s.y - h, s.y + h, min(s.z, e.z), max(s.z, e.z))


def _write_box(  # noqa: PLR0914
    c: _C,
    L: list[str],
    bar: Bar,
    p: float,
    n_dx: int, n_nx: int,
    n_dy: int, n_ny: int,
    n_dz: int, n_nz: int,
) -> int:
    """
    Emit all entities for one axis-aligned box solid.
    Return the MANIFOLD_SOLID_BREP entity ID.

    Face winding: counter-clockwise when viewed from outside.
    Corners:
      P0=(x0,y0,z0)  P1=(x1,y0,z0)  P2=(x1,y1,z0)  P3=(x0,y1,z0)
      P4=(x0,y0,z1)  P5=(x1,y0,z1)  P6=(x1,y1,z1)  P7=(x0,y1,z1)

    Edge curves (direction from first to second vertex):
      E01 P0->P1 +X   E12 P1->P2 +Y   E23 P2->P3 -X   E03 P0->P3 +Y
      E45 P4->P5 +X   E56 P5->P6 +Y   E67 P6->P7 -X   E47 P4->P7 +Y
      E04 P0->P4 +Z   E15 P1->P5 +Z   E26 P2->P6 +Z   E37 P3->P7 +Z

    Face windings (.T. = forward edge sense, .F. = reversed):
      -Z  normal (0,0,-1)  P0 P3 P2 P1  E03.T E23.F E12.F E01.F
      +Z  normal (0,0,+1)  P4 P5 P6 P7  E45.T E56.T E67.T E47.F
      -Y  normal (0,-1,0)  P0 P1 P5 P4  E01.T E15.T E45.F E04.F
      +Y  normal (0,+1,0)  P3 P7 P6 P2  E37.T E67.F E26.F E23.T
      -X  normal (-1,0,0)  P0 P4 P7 P3  E04.T E47.T E37.F E03.F
      +X  normal (+1,0,0)  P1 P2 P6 P5  E12.T E26.T E56.F E15.F
    """
    x0, x1, y0, y1, z0, z1 = _bbox(bar, p)
    dx = x1 - x0
    dy = y1 - y0
    dz = z1 - z0

    # 8 corner CARTESIAN_POINTs
    def pt(x: float, y: float, z: float) -> int:
        n = c()
        L.append(f"#{n} = CARTESIAN_POINT('',({_v(x)},{_v(y)},{_v(z)}));")
        return n

    cp0 = pt(x0, y0, z0)  # P0
    cp1 = pt(x1, y0, z0)  # P1
    cp2 = pt(x1, y1, z0)  # P2
    cp3 = pt(x0, y1, z0)  # P3
    cp4 = pt(x0, y0, z1)  # P4
    cp5 = pt(x1, y0, z1)  # P5
    cp6 = pt(x1, y1, z1)  # P6
    cp7 = pt(x0, y1, z1)  # P7

    # 8 VERTEX_POINTs
    def vp(n_cp: int) -> int:
        n = c()
        L.append(f"#{n} = VERTEX_POINT('',#{n_cp});")
        return n

    v0 = vp(cp0)
    v1 = vp(cp1)
    v2 = vp(cp2)
    v3 = vp(cp3)
    v4 = vp(cp4)
    v5 = vp(cp5)
    v6 = vp(cp6)
    v7 = vp(cp7)

    # 4 VECTORs (reuse shared DIRECTION entities; only magnitudes are bar-specific)
    def vec(n_dir: int, mag: float) -> int:
        n = c()
        L.append(f"#{n} = VECTOR('',#{n_dir},{_v(mag)});")
        return n

    vx_px = vec(n_dx, dx)  # +X, magnitude dx
    vx_mx = vec(n_nx, dx)  # -X, magnitude dx
    vx_py = vec(n_dy, dy)  # +Y, magnitude dy
    vx_pz = vec(n_dz, dz)  # +Z, magnitude dz

    # 12 LINEs + 12 EDGE_CURVEs
    def ln(n_orig: int, n_vec: int) -> int:
        n = c()
        L.append(f"#{n} = LINE('',#{n_orig},#{n_vec});")
        return n

    def ec(n_v1: int, n_v2: int, n_ln: int) -> int:
        n = c()
        L.append(f"#{n} = EDGE_CURVE('',#{n_v1},#{n_v2},#{n_ln},.T.);")
        return n

    e01 = ec(v0, v1, ln(cp0, vx_px))  # P0->P1 (+X)
    e12 = ec(v1, v2, ln(cp1, vx_py))  # P1->P2 (+Y)
    e23 = ec(v2, v3, ln(cp2, vx_mx))  # P2->P3 (-X)
    e03 = ec(v0, v3, ln(cp0, vx_py))  # P0->P3 (+Y)
    e45 = ec(v4, v5, ln(cp4, vx_px))  # P4->P5 (+X)
    e56 = ec(v5, v6, ln(cp5, vx_py))  # P5->P6 (+Y)
    e67 = ec(v6, v7, ln(cp6, vx_mx))  # P6->P7 (-X)
    e47 = ec(v4, v7, ln(cp4, vx_py))  # P4->P7 (+Y)
    e04 = ec(v0, v4, ln(cp0, vx_pz))  # P0->P4 (+Z)
    e15 = ec(v1, v5, ln(cp1, vx_pz))  # P1->P5 (+Z)
    e26 = ec(v2, v6, ln(cp2, vx_pz))  # P2->P6 (+Z)
    e37 = ec(v3, v7, ln(cp3, vx_pz))  # P3->P7 (+Z)

    # Face helpers
    def oe(n_ec: int, fwd: bool) -> int:
        """ORIENTED_EDGE: .T. = stored direction, .F. = reversed."""
        n = c()
        sense = ".T." if fwd else ".F."
        L.append(f"#{n} = ORIENTED_EDGE('',*,*,#{n_ec},{sense});")
        return n

    def el(oe_ids: list[int]) -> int:
        n = c()
        refs = ",".join(f"#{i}" for i in oe_ids)
        L.append(f"#{n} = EDGE_LOOP('',({refs}));")
        return n

    def fob(n_el: int) -> int:
        n = c()
        L.append(f"#{n} = FACE_OUTER_BOUND('',#{n_el},.T.);")
        return n

    def af(
        ox: float, oy: float, oz: float,
        n_norm: int,
        n_xdir: int,
        n_fob_id: int,
    ) -> int:
        """
        Emit face origin point, AXIS2_PLACEMENT_3D, PLANE, ADVANCED_FACE.
        .T. flag on ADVANCED_FACE: plane outward normal matches shell sense.
        """
        n_fcp = c()
        L.append(
            f"#{n_fcp} = CARTESIAN_POINT('',({_v(ox)},{_v(oy)},{_v(oz)}));"
        )
        n_a2p = c()
        L.append(
            f"#{n_a2p} = AXIS2_PLACEMENT_3D('',#{n_fcp},#{n_norm},#{n_xdir});"
        )
        n_pln = c()
        L.append(f"#{n_pln} = PLANE('',#{n_a2p});")
        n_face = c()
        L.append(f"#{n_face} = ADVANCED_FACE('',(#{n_fob_id}),#{n_pln},.T.);")
        return n_face

    mx = (x0 + x1) / 2.0
    my = (y0 + y1) / 2.0
    mz = (z0 + z1) / 2.0

    # Six faces with outward normals, CCW winding when viewed from outside.
    # -Z (z=z0, normal -Z, x-ref +X): P0 P3 P2 P1
    f_nz = af(
        mx, my, z0, n_nz, n_dx,
        fob(el([oe(e03, True), oe(e23, False), oe(e12, False), oe(e01, False)])),
    )
    # +Z (z=z1, normal +Z, x-ref +X): P4 P5 P6 P7
    f_pz = af(
        mx, my, z1, n_dz, n_dx,
        fob(el([oe(e45, True), oe(e56, True), oe(e67, True), oe(e47, False)])),
    )
    # -Y (y=y0, normal -Y, x-ref +X): P0 P1 P5 P4
    f_ny = af(
        mx, y0, mz, n_ny, n_dx,
        fob(el([oe(e01, True), oe(e15, True), oe(e45, False), oe(e04, False)])),
    )
    # +Y (y=y1, normal +Y, x-ref +X): P3 P7 P6 P2
    f_py = af(
        mx, y1, mz, n_dy, n_dx,
        fob(el([oe(e37, True), oe(e67, False), oe(e26, False), oe(e23, True)])),
    )
    # -X (x=x0, normal -X, x-ref +Y): P0 P4 P7 P3
    f_nx = af(
        x0, my, mz, n_nx, n_dy,
        fob(el([oe(e04, True), oe(e47, True), oe(e37, False), oe(e03, False)])),
    )
    # +X (x=x1, normal +X, x-ref +Y): P1 P2 P6 P5
    f_px = af(
        x1, my, mz, n_dx, n_dy,
        fob(el([oe(e12, True), oe(e26, True), oe(e56, False), oe(e15, False)])),
    )

    # CLOSED_SHELL
    n_shell = c()
    L.append(
        f"#{n_shell} = CLOSED_SHELL('',("
        f"#{f_nz},#{f_pz},#{f_ny},#{f_py},#{f_nx},#{f_px}));"
    )

    # MANIFOLD_SOLID_BREP named with plain role label + integer length
    label = f"{_role_label(bar.role)} {round(bar.length_mm)}"
    n_msb = c()
    L.append(f"#{n_msb} = MANIFOLD_SOLID_BREP('{label}',#{n_shell});")
    return n_msb


def step_filename(width_mm: float, depth_mm: float, height_mm: float) -> str:
    """Return the download filename, e.g. 'frame-1500x700x900.step'."""

    def _fmt(v: float) -> str:
        return str(int(v)) if v == int(v) else str(v)

    return f"frame-{_fmt(width_mm)}x{_fmt(depth_mm)}x{_fmt(height_mm)}.step"


def export_step(bars: list[Bar], profile_width_mm: float, design_name: str) -> str:
    """
    Return a STEP AP214 (AUTOMOTIVE_DESIGN) file as a string.

    All bars become MANIFOLD_SOLID_BREP entities inside a single
    ADVANCED_BREP_SHAPE_REPRESENTATION.  One PRODUCT represents the whole
    frame.  Coordinates are in millimetres.

    Parameters
    ----------
    bars:             list returned by generate_table / generate_shelf_unit.
    profile_width_mm: profile side length in mm (e.g. 40.0 for 40-series).
    design_name:      label for the PRODUCT entity, e.g. 'table 1500x700x900'.
    """
    c = _C()
    L: list[str] = []

    # Application context
    n_app_ctx = c()
    L.append(f"#{n_app_ctx} = APPLICATION_CONTEXT('{_APP_CTX_STR}');")

    n_app_proto = c()
    L.append(
        f"#{n_app_proto} = APPLICATION_PROTOCOL_DEFINITION("
        f"'international standard','{_APP_PROTOCOL}',2000,#{n_app_ctx});"
    )

    n_prod_ctx = c()
    L.append(f"#{n_prod_ctx} = PRODUCT_CONTEXT('',#{n_app_ctx},'mechanical');")

    n_pdc = c()
    L.append(
        f"#{n_pdc} = PRODUCT_DEFINITION_CONTEXT("
        f"'part definition',#{n_app_ctx},'design');"
    )

    # One PRODUCT for the whole frame
    n_prod = c()
    L.append(
        f"#{n_prod} = PRODUCT("
        f"'{design_name}','{design_name}','',(#{n_prod_ctx}));"
    )

    n_pdf = c()
    L.append(f"#{n_pdf} = PRODUCT_DEFINITION_FORMATION('','',#{n_prod});")

    n_pd = c()
    L.append(f"#{n_pd} = PRODUCT_DEFINITION('design','',#{n_pdf},#{n_pdc});")

    n_pds = c()
    L.append(f"#{n_pds} = PRODUCT_DEFINITION_SHAPE('','',#{n_pd});")

    # Unit and geometry context (compound STEP entity syntax)
    n_len_unit = c()
    L.append(
        f"#{n_len_unit} = ( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );"
    )

    n_ang_unit = c()
    L.append(
        f"#{n_ang_unit} = ( NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.) );"
    )

    n_sol_unit = c()
    L.append(
        f"#{n_sol_unit} ="
        f" ( NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT() );"
    )

    n_unc = c()
    L.append(
        f"#{n_unc} = UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),"
        f"#{n_len_unit},'distance_accuracy_value',"
        f"'Confusion accuracy of a planar surface');"
    )

    n_ctx = c()
    L.append(
        f"#{n_ctx} = ( "
        f"GEOMETRIC_REPRESENTATION_CONTEXT(3) "
        f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{n_unc})) "
        f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{n_len_unit},#{n_ang_unit},#{n_sol_unit})) "
        f"REPRESENTATION_CONTEXT('','3D Space') );"
    )

    # Shared direction entities (reused across all bars)
    n_dx = c()
    L.append(f"#{n_dx} = DIRECTION('',(1.,0.,0.));")    # +X
    n_nx = c()
    L.append(f"#{n_nx} = DIRECTION('',(-1.,0.,0.));")   # -X
    n_dy = c()
    L.append(f"#{n_dy} = DIRECTION('',(0.,1.,0.));")    # +Y
    n_ny = c()
    L.append(f"#{n_ny} = DIRECTION('',(0.,-1.,0.));")   # -Y
    n_dz = c()
    L.append(f"#{n_dz} = DIRECTION('',(0.,0.,1.));")    # +Z
    n_nz = c()
    L.append(f"#{n_nz} = DIRECTION('',(0.,0.,-1.));")   # -Z

    # Identity placement (first item in ADVANCED_BREP_SHAPE_REPRESENTATION)
    n_orig_pt = c()
    L.append(f"#{n_orig_pt} = CARTESIAN_POINT('',(0.,0.,0.));")
    n_id_axis = c()
    L.append(
        f"#{n_id_axis} = AXIS2_PLACEMENT_3D('',#{n_orig_pt},#{n_dz},#{n_dx});"
    )

    # Per-bar box geometry
    msb_ids: list[int] = []
    for bar in bars:
        msb_id = _write_box(
            c, L, bar, profile_width_mm,
            n_dx, n_nx, n_dy, n_ny, n_dz, n_nz,
        )
        msb_ids.append(msb_id)

    # ADVANCED_BREP_SHAPE_REPRESENTATION (identity placement + all BREPs)
    n_absr = c()
    msb_refs = ",".join(f"#{mid}" for mid in msb_ids)
    L.append(
        f"#{n_absr} = ADVANCED_BREP_SHAPE_REPRESENTATION("
        f"'',(#{n_id_axis},{msb_refs}),#{n_ctx});"
    )

    # SHAPE_DEFINITION_REPRESENTATION (links product shape to geometry)
    n_sdr = c()
    L.append(f"#{n_sdr} = SHAPE_DEFINITION_REPRESENTATION(#{n_pds},#{n_absr});")

    # Assemble complete STEP file
    header = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(("
        "'Frame Designer - simplified bar geometry',"
        "'No T-slots or brackets'),'2;1');\n"
        f"FILE_NAME('frame','{_TIMESTAMP}',(''),(''),'Frame Designer','','');\n"
        f"FILE_SCHEMA(('{_SCHEMA}'));\n"
        "ENDSEC;\n"
        "DATA;"
    )
    data = "\n".join(L)
    return f"{header}\n{data}\nENDSEC;\nEND-ISO-10303-21;\n"
