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
from framegen.spec import FrameSpec  # noqa: E402
from framegen.suggestions import FixCandidate, suggest_fixes  # noqa: E402

_CATALOG = load_catalog()
_PROFILE = _CATALOG.profiles["40-series"]

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
            profile_series="40-series", target_load_kg=5000,
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
        id="healthy_frame_no_suggestions",
        spec=FrameSpec(
            frame_type="table",
            width_mm=800, depth_mm=600, height_mm=900,
            profile_series="40-series", target_load_kg=50,
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


def run() -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in _CASES:
        bars = generate_table(case.spec, _PROFILE)
        report = run_checks(bars, case.spec, _PROFILE)
        fixes = suggest_fixes(case.spec, _PROFILE, report)

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
    print("Summary")
    for s in signals:
        print(f"  {s:<12}: {passes[s]}/{totals[s]}")


if __name__ == "__main__":
    main()
