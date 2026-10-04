"""
Eval suite for the fix-suggestions module.

Usage:
    python -m evals.suggestions_suite

Scoring per case (four signals):
  1. validity    — every offered fix's check_report.load.passed is True
  2. coverage    — at least one expected fix_type appears in the offered fixes
  3. count       — len(suggestions) <= 3
  4. minimality  — for each fix, the next step in the worsening direction fails

Runs without an API key; suggestions are pure code.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from framegen.catalog import load_catalog  # noqa: E402
from framegen.checks import run_checks  # noqa: E402
from framegen.generate.table import generate_table  # noqa: E402
from framegen.spec import TableSpec  # noqa: E402
from framegen.suggestions import (  # noqa: E402
    FixCandidate,
    suggest_cheaper_profile,
    suggest_fixes,
)

FrameSpec = TableSpec

_CATALOG = load_catalog()
_PROFILE = _CATALOG.profiles["40-series"]
_PROFILE_45 = _CATALOG.profiles["45-series"]

# Rounding step used by suggestions/__init__.py
_SPAN_STEP_MM = 10
_LOAD_STEP_KG = 5


# ── Test cases ────────────────────────────────────────────────────────────────

@dataclass
class Case:
    id: str
    spec: FrameSpec
    expected_fix_types: list[str]   # fix_types we expect to see at least one of
    expects_empty: bool = False     # True means frame passes → suggestions should be []


_CASES: list[Case] = [
    Case(
        id="wide_span_dist_fail",
        spec=FrameSpec(
            frame_type="table",
            width_mm=3000, depth_mm=700, height_mm=900,
            profile_series="40-series", target_load_kg=100,
        ),
        expected_fix_types=["reduce_span_width", "reduce_load", "centre_legs"],
    ),
    Case(
        id="heavy_load_dist_fail",
        spec=FrameSpec(
            frame_type="table",
            width_mm=1500, depth_mm=700, height_mm=900,
            profile_series="40-series", target_load_kg=1500,
        ),
        expected_fix_types=["reduce_load"],
    ),
    Case(
        id="concentrated_warn_only",
        # 1500×700 at 100 kg passes distributed but may warn on concentrated
        # For this test we just check: if suggestions are generated they are valid
        spec=FrameSpec(
            frame_type="table",
            width_mm=1500, depth_mm=700, height_mm=900,
            profile_series="40-series", target_load_kg=100,
        ),
        expected_fix_types=[],   # might be empty if no warning; that's fine
        expects_empty=False,     # we just validate whatever is returned
    ),
    Case(
        id="healthy_frame_cheapest_profile",
        # 20-series is cheapest — no cheaper profile exists → no cheaper suggestion
        spec=FrameSpec(
            frame_type="table",
            width_mm=400, depth_mm=300, height_mm=500,
            profile_series="20-series", target_load_kg=5,
        ),
        expected_fix_types=[],
        expects_empty=True,
    ),
    Case(
        id="centre_legs_resolves_3000_wide",
        spec=FrameSpec(
            frame_type="table",
            width_mm=3000, depth_mm=700, height_mm=900,
            profile_series="40-series", target_load_kg=100,
        ),
        expected_fix_types=["centre_legs"],
    ),
]


# ── Cheaper-profile test cases (standalone function) ──────────────────────────

@dataclass
class CheaperCase:
    id: str
    spec: FrameSpec
    expects_candidate: bool          # True → must return a FixCandidate
    expected_profile: str | None = None  # profile_series we expect
    min_saving_usd: float | None = None  # minimum saving expected


_CHEAPER_CASES: list[CheaperCase] = [
    CheaperCase(
        id="40_series_finds_cheaper_passing_profile",
        spec=FrameSpec(
            frame_type="table",
            width_mm=800, depth_mm=600, height_mm=900,
            profile_series="40-series", target_load_kg=50,
        ),
        expects_candidate=True,
        # 30-series is the cheapest alternative that passes for this light load
        expected_profile="30-series",
    ),
    CheaperCase(
        id="1500_700_100kg_40_to_45_saving_31",
        spec=FrameSpec(
            frame_type="table",
            width_mm=1500, depth_mm=700, height_mm=900,
            profile_series="40-series", target_load_kg=100,
        ),
        expects_candidate=True,
        expected_profile="45-series",
        min_saving_usd=31.0,
    ),
    CheaperCase(
        id="cheapest_20_series_no_suggestion",
        spec=FrameSpec(
            frame_type="table",
            width_mm=400, depth_mm=300, height_mm=500,
            profile_series="20-series", target_load_kg=5,
        ),
        expects_candidate=False,
    ),
]


# ── Scoring helpers ────────────────────────────────────────────────────────────

def _check_validity(fixes: list[FixCandidate]) -> bool:
    return all(c.check_report.load.passed for c in fixes)


def _check_coverage(fixes: list[FixCandidate], expected: list[str]) -> bool:
    if not expected:
        return True  # nothing expected — not scored
    offered = {c.fix_type for c in fixes}
    return bool(offered & set(expected))


def _check_count(fixes: list[FixCandidate]) -> bool:
    return len(fixes) <= 3


def _next_step_fails(c: FixCandidate, orig_spec: FrameSpec) -> bool:
    """Return True if making the fix one step worse causes load check to fail."""
    profile = _PROFILE

    def _run(spec: FrameSpec) -> bool:
        try:
            bars = generate_table(spec, profile)
        except ValueError:
            return False
        report = run_checks(bars, spec, profile)
        if c.resolves == "distributed":
            return report.load.passed
        else:
            gov = report.load.governing_rail
            return gov is None or gov.concentrated.passed

    if c.fix_type == "reduce_span_width":
        worse = c.spec.model_copy(update={"width_mm": c.spec.width_mm + _SPAN_STEP_MM})
        return not _run(worse)
    elif c.fix_type == "reduce_span_depth":
        worse = c.spec.model_copy(update={"depth_mm": c.spec.depth_mm + _SPAN_STEP_MM})
        return not _run(worse)
    elif c.fix_type == "reduce_load":
        worse_spec = c.spec.model_copy(
            update={"target_load_kg": c.spec.target_load_kg + _LOAD_STEP_KG}
        )
        return not _run(worse_spec)
    elif c.fix_type == "centre_legs":
        # Inverse: removing centre_legs should fail
        worse_spec = c.spec.model_copy(update={"centre_legs": False})
        return not _run(worse_spec)
    elif c.fix_type == "cheaper_profile":
        # Profile switches have no numeric "step worse" — consider minimality N/A
        return True
    elif c.fix_type == "reduce_load_per_level":
        if c.spec.load_per_level_kg is None:
            return False
        worse_spec = c.spec.model_copy(
            update={"load_per_level_kg": c.spec.load_per_level_kg + _LOAD_STEP_KG}
        )
        return not _run(worse_spec)
    return False


def _check_minimality(
    fixes: list[FixCandidate], orig_spec: FrameSpec
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for c in fixes:
        if not _next_step_fails(c, orig_spec):
            failures.append(c.fix_type)
    return (not failures), failures


# ── Runner ────────────────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    id: str
    fixes: list[FixCandidate]
    validity: bool
    coverage: bool
    count: bool
    minimality: bool
    minimality_failures: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class CheaperResult:
    id: str
    candidate: FixCandidate | None
    passed: bool
    note: str = ""


def run_cheaper() -> list[CheaperResult]:
    results: list[CheaperResult] = []
    for case in _CHEAPER_CASES:
        profile = _CATALOG.profiles[case.spec.profile_series]
        bars = generate_table(case.spec, profile)
        report = run_checks(bars, case.spec, profile)
        candidate = suggest_cheaper_profile(case.spec, profile, report, _CATALOG)

        if not case.expects_candidate:
            passed = candidate is None
            note = "expects None"
        else:
            if candidate is None:
                passed = False
                note = "expected candidate, got None"
            else:
                notes: list[str] = []
                ok = True
                if (
                    case.expected_profile
                    and candidate.spec.profile_series != case.expected_profile
                ):
                    ok = False
                    notes.append(
                        f"profile: expected {case.expected_profile!r},"
                        f" got {candidate.spec.profile_series!r}"
                    )
                if case.min_saving_usd is not None:
                    # Extract saving from trade_off string
                    import re as _re
                    m = _re.search(r"\$([0-9.]+)", candidate.trade_off)
                    saving = float(m.group(1)) if m else 0.0
                    if saving < case.min_saving_usd:
                        ok = False
                        notes.append(
                            f"saving ${saving:.2f}"
                            f" < expected ${case.min_saving_usd:.2f}"
                        )
                passed = ok
                note = "; ".join(notes)

        results.append(
            CheaperResult(id=case.id, candidate=candidate, passed=passed, note=note)
        )
    return results


def run() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in _CASES:
        profile = _CATALOG.profiles[case.spec.profile_series]
        bars = generate_table(case.spec, profile)
        report = run_checks(bars, case.spec, profile)
        fixes = suggest_fixes(case.spec, profile, report)

        if case.expects_empty:
            validity = (fixes == [])
            coverage = True
            count = True
            minimality = True
            minimality_failures: list[str] = []
            note = "expects_empty"
        else:
            validity = _check_validity(fixes)
            coverage = _check_coverage(fixes, case.expected_fix_types)
            count = _check_count(fixes)
            minimality, minimality_failures = _check_minimality(fixes, case.spec)
            note = ""

        results.append(CaseResult(
            id=case.id,
            fixes=fixes,
            validity=validity,
            coverage=coverage,
            count=count,
            minimality=minimality,
            minimality_failures=minimality_failures,
            note=note,
        ))
    return results


def main() -> None:
    results = run()
    cheaper_results = run_cheaper()
    print("\nSuggestions eval")
    print("=" * 60)

    signals = ("validity", "coverage", "count", "minimality")
    totals = {s: 0 for s in signals}
    passes = {s: 0 for s in signals}

    for r in results:
        totals["validity"] += 1
        totals["coverage"] += 1
        totals["count"] += 1
        totals["minimality"] += 1

        ok = {
            "validity": r.validity,
            "coverage": r.coverage,
            "count": r.count,
            "minimality": r.minimality,
        }
        for s in signals:
            if ok[s]:
                passes[s] += 1

        status = "PASS" if all(ok.values()) else "FAIL"
        fix_types = [c.fix_type for c in r.fixes]
        print(f"\n[{status}] {r.id}")
        print(f"  fixes offered : {fix_types}")
        print(f"  validity      : {'OK' if r.validity else 'FAIL'}")
        print(f"  coverage      : {'OK' if r.coverage else 'FAIL'}")
        print(f"  count         : {'OK' if r.count else 'FAIL'} ({len(r.fixes)})")
        min_ok = 'OK' if r.minimality else 'FAIL'
        min_note = (
            f" — not minimal: {r.minimality_failures}" if r.minimality_failures else ""
        )
        print(f"  minimality    : {min_ok}{min_note}")
        if r.note:
            print(f"  note          : {r.note}")

    print("\n" + "=" * 60)
    print("Summary — structural fixes")
    for s in signals:
        print(f"  {s:<12}: {passes[s]}/{totals[s]}")

    print("\nCost suggestion eval")
    print("=" * 60)
    for r in cheaper_results:
        status = "PASS" if r.passed else "FAIL"
        profile_str = r.candidate.spec.profile_series if r.candidate else "None"
        trade_off = r.candidate.trade_off if r.candidate else "-"
        print(f"\n[{status}] {r.id}")
        print(f"  profile : {profile_str}")
        print(f"  trade_off: {trade_off}")
        if r.note:
            print(f"  note    : {r.note}")

    n_cheaper_pass = sum(1 for r in cheaper_results if r.passed)
    print(f"\nCost suggestion: {n_cheaper_pass}/{len(cheaper_results)}")


if __name__ == "__main__":
    main()
