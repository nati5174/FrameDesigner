"""
Eval harness for the frame parser.

Usage:
    python -m evals.run [--config rule_based|llm|dispatcher]
                       [--file dev|regression|test]

Configs:
    rule_based  — rule-based parser only
    llm         — LLM parser only (skipped if ANTHROPIC_API_KEY not set)
    dispatcher  — full dispatcher (default)

Files:
    dev         — prompts_dev.json (default)
    regression  — prompts_regression.json
    test        — prompts_test.json (user-written; not tracked in the repo)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure src/ is on the path when run as a script
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

# Load .env once at startup; variables already in the environment take precedence.
load_dotenv(override=False)

from framegen.parser import ParseResult  # noqa: E402
from framegen.parser import parse as _dispatcher_parse  # noqa: E402
from framegen.parser.llm import parse as _llm_parse  # noqa: E402
from framegen.parser.rule_based import parse as _rb_parse  # noqa: E402
from framegen.spec import ShelfUnitSpec  # noqa: E402

_EVALS_DIR = Path(__file__).parent
_RESULTS_DIR = _EVALS_DIR / "results"
_TOL = 1.0  # mm / kg tolerance for field comparison


# ── Scoring helpers ───────────────────────────────────────────────────────────

@dataclass
class PromptResult:
    id: str
    group: str
    text: str
    expected: dict[str, Any]
    result: ParseResult
    passed: bool
    field_results: dict[str, bool] = field(default_factory=dict)


def _check_field(actual: float | None, expected: float | None) -> bool:
    if expected is None:
        return True  # not checked
    if actual is None:
        return False
    return abs(actual - expected) <= _TOL


def _score_prompt(p: dict[str, Any], result: ParseResult) -> PromptResult:
    exp = p["expected"]
    passed = False
    field_results: dict[str, bool] = {}

    exp_outcome = exp["outcome"]

    if exp_outcome == "not_parsed":
        passed = result.outcome == "not_parsed"

    elif exp_outcome == "spec_invalid":
        passed = result.outcome == "spec_invalid"

    elif exp_outcome == "spec_valid":
        if result.outcome != "spec_valid" or result.spec is None:
            passed = False
        else:
            spec = result.spec
            w_ok = _check_field(spec.width_mm, exp.get("W"))
            d_ok = _check_field(spec.depth_mm, exp.get("D"))
            h_ok = _check_field(spec.height_mm, exp.get("H"))
            if isinstance(spec, ShelfUnitSpec):
                # Shelf unit: no shelf_height, load is per-level
                s_ok = True
                l_ok = _check_field(spec.load_per_level_kg, exp.get("L"))
                # Check frame_type when caller specifies it
                type_ok = exp.get("frame_type", "shelf_unit") == "shelf_unit"
            else:
                s_ok = _check_field(spec.shelf_height_mm, exp.get("S"))
                l_ok = _check_field(spec.target_load_kg, exp.get("L"))
                # If caller expects shelf_unit but got table, fail
                type_ok = exp.get("frame_type", "table") == "table"
            field_results = {"W": w_ok, "D": d_ok, "H": h_ok, "S": s_ok, "L": l_ok}
            passed = all(field_results.values()) and type_ok

    return PromptResult(
        id=p["id"],
        group=p["group"],
        text=p["text"],
        expected=exp,
        result=result,
        passed=passed,
        field_results=field_results,
    )


# ── Parser runners ─────────────────────────────────────────────────────────────

def _run_parser(config: str, text: str) -> ParseResult | None:
    """Return None if config is skipped (no API key)."""
    if config == "rule_based":
        # Apply pre-checks manually (they live in the dispatcher)
        from framegen.parser import _check_enclosure, _check_imperial
        err = _check_imperial(text) or _check_enclosure(text)
        if err:
            return ParseResult(
                outcome="spec_invalid", spec=None, error=err, parser_used="none"
            )
        return _rb_parse(text)
    elif config == "llm":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None  # skipped
        from framegen.parser import _check_enclosure, _check_imperial
        err = _check_imperial(text) or _check_enclosure(text)
        if err:
            return ParseResult(
                outcome="spec_invalid", spec=None, error=err, parser_used="none"
            )
        return _llm_parse(text)
    else:  # dispatcher
        if not os.environ.get("ANTHROPIC_API_KEY"):
            # Still run dispatcher but LLM calls will fall through to not_parsed
            pass
        return _dispatcher_parse(text)


# ── Reporting ─────────────────────────────────────────────────────────────────

def _report(
    config: str, prompt_results: list[PromptResult], skipped: bool
) -> dict[str, Any]:
    if skipped:
        return {"config": config, "status": "skipped: no API key"}

    total = len(prompt_results)
    n_pass = sum(1 for r in prompt_results if r.passed)

    # Per group
    groups: dict[str, list[PromptResult]] = {}
    for r in prompt_results:
        groups.setdefault(r.group, []).append(r)
    group_scores = {
        g: f"{sum(1 for r in rs if r.passed)}/{len(rs)}"
        for g, rs in sorted(groups.items())
    }

    # Per field (spec_valid rows only)
    field_totals: dict[str, int] = {"W": 0, "D": 0, "H": 0, "S": 0, "L": 0}
    field_passes: dict[str, int] = {"W": 0, "D": 0, "H": 0, "S": 0, "L": 0}
    for r in prompt_results:
        for f, ok in r.field_results.items():
            field_totals[f] += 1
            if ok:
                field_passes[f] += 1
    field_scores = {
        f: f"{field_passes[f]}/{field_totals[f]}" if field_totals[f] else "n/a"
        for f in ("W", "D", "H", "S", "L")
    }

    # Failures detail
    failures = [
        {
            "id": r.id,
            "text": r.text,
            "expected": r.expected,
            "got_outcome": r.result.outcome,
            "got_error": r.result.error,
            "got_spec": (
                {
                    "frame_type": (
                        "shelf_unit"
                        if isinstance(r.result.spec, ShelfUnitSpec)
                        else "table"
                    ),
                    "W": r.result.spec.width_mm,
                    "D": r.result.spec.depth_mm,
                    "H": r.result.spec.height_mm,
                    "S": (
                        None
                        if isinstance(r.result.spec, ShelfUnitSpec)
                        else r.result.spec.shelf_height_mm
                    ),
                    "L": (
                        r.result.spec.load_per_level_kg
                        if isinstance(r.result.spec, ShelfUnitSpec)
                        else r.result.spec.target_load_kg
                    ),
                }
                if r.result.spec else None
            ),
            "field_results": r.field_results,
        }
        for r in prompt_results
        if not r.passed
    ]

    return {
        "config": config,
        "status": "ok",
        "overall": f"{n_pass}/{total}",
        "by_group": group_scores,
        "by_field": field_scores,
        "failures": failures,
    }


def _print_report(rep: dict[str, Any]) -> None:
    config = rep["config"]
    if rep.get("status", "ok") != "ok":
        print(f"\n[{config}] {rep['status']}")
        return

    print(f"\n[{config}]  overall: {rep['overall']}")
    print(f"  by group: {rep['by_group']}")
    print(f"  by field: {rep['by_field']}")
    if rep["failures"]:
        print(f"  failures ({len(rep['failures'])}):")
        for f in rep["failures"]:
            print(f"    {f['id']} {f['text']!r}")
            print(f"      expected {f['expected']['outcome']} | got {f['got_outcome']}")
            if f["got_spec"]:
                print(f"      spec: {f['got_spec']}")
            if f.get("field_results"):
                bad = [k for k, v in f["field_results"].items() if not v]
                print(f"      wrong fields: {bad}")


# ── Git hash ──────────────────────────────────────────────────────────────────

def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="dispatcher",
                    choices=["rule_based", "llm", "dispatcher", "all"])
    ap.add_argument("--file", default="dev",
                    choices=["dev", "regression", "test"])
    args = ap.parse_args()

    _file_map = {
        "dev": "prompts_dev.json",
        "regression": "prompts_regression.json",
        "test": "prompts_test.json",
    }
    prompt_file = _EVALS_DIR / _file_map[args.file]
    with open(prompt_file) as f:
        data = json.load(f)
    prompts: list[dict[str, Any]] = data["prompts"]

    configs = (
        ["rule_based", "llm", "dispatcher"] if args.config == "all" else [args.config]
    )

    all_reports: list[dict[str, Any]] = []
    for config in configs:
        # Check if LLM-dependent config needs key
        needs_key = config in ("llm", "dispatcher")
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        if needs_key and not has_key and config == "llm":
            all_reports.append({"config": config, "status": "skipped: no API key"})
            continue

        prompt_results: list[PromptResult] = []
        for p in prompts:
            result = _run_parser(config, p["text"])
            if result is None:
                all_reports.append({"config": config, "status": "skipped: no API key"})
                break
            prompt_results.append(_score_prompt(p, result))
        else:
            all_reports.append(_report(config, prompt_results, skipped=False))

    # Print
    for rep in all_reports:
        _print_report(rep)

    # Save results
    _RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    result_path = _RESULTS_DIR / f"{ts}_{args.config}_{args.file}.json"
    with open(result_path, "w") as f:
        json.dump(
            {
                "timestamp": ts,
                "git_hash": _git_hash(),
                "prompt_file": str(prompt_file.name),
                "prompt_file_version": data.get("version"),
                "configs": all_reports,
            },
            f,
            indent=2,
        )
    print(f"\nResults saved to {result_path.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()
