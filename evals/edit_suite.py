"""
Edit eval harness for the /edit endpoint.

Called from evals/run.py with --config edit [rule_based|llm|dispatcher]
or directly:
    python -m evals.edit_suite [--config rule_based|llm|dispatcher]
                               [--file dev|regression]

Each prompt has:
  input_spec  — the current frame spec (or null for first-turn cases)
  text        — the user message
  expected    — outcome + optional spec field checks

Expected fields for spec checking:
  spec.height_mm, spec.width_mm, spec.depth_mm, spec.target_load_kg,
  spec.load_per_level_kg, spec.centre_legs, spec.shelf_height_mm,
  spec.frame_type
  spec.level_heights_mm_len   — check len(level_heights_mm)
  spec.level_heights_mm_contains — check a value is in level_heights_mm
  missing — list of field names that must appear in result.missing
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))
load_dotenv(override=False)

from framegen.parser.edit_dispatch import EditResult, edit_parse  # noqa: E402
from framegen.spec import ShelfUnitSpec, TableSpec  # noqa: E402

_EVALS_DIR = Path(__file__).parent
_RESULTS_DIR = _EVALS_DIR / "results"
_TOL = 1.0


# ── Input spec reconstruction ─────────────────────────────────────────────────

def _build_input_spec(d: dict[str, Any] | None) -> TableSpec | ShelfUnitSpec | None:
    if d is None:
        return None
    if d.get("frame_type") == "shelf_unit":
        return ShelfUnitSpec.model_validate(d)
    return TableSpec.model_validate(d)


# ── Scoring ───────────────────────────────────────────────────────────────────

@dataclass
class EditPromptResult:
    id: str
    group: str
    text: str
    expected: dict[str, Any]
    result: EditResult
    passed: bool
    fail_reason: str = ""


def _check_spec_fields(
    result: EditResult,
    exp_spec: dict[str, Any],
) -> tuple[bool, str]:
    """Check expected spec fields against result.spec. Returns (ok, reason)."""
    spec = result.spec
    if spec is None:
        return False, "spec is None"

    for k, v in exp_spec.items():
        if k == "frame_type":
            actual = spec.frame_type
            if actual != v:
                return False, f"frame_type: expected {v!r}, got {actual!r}"
        elif k == "height_mm":
            if abs(spec.height_mm - v) > _TOL:
                return False, f"height_mm: expected {v}, got {spec.height_mm}"
        elif k == "width_mm":
            if abs(spec.width_mm - v) > _TOL:
                return False, f"width_mm: expected {v}, got {spec.width_mm}"
        elif k == "depth_mm":
            if abs(spec.depth_mm - v) > _TOL:
                return False, f"depth_mm: expected {v}, got {spec.depth_mm}"
        elif k == "target_load_kg":
            if not isinstance(spec, TableSpec):
                return False, "expected TableSpec for target_load_kg"
            if abs(spec.target_load_kg - v) > _TOL:
                return (
                    False,
                    f"target_load_kg: expected {v}, got {spec.target_load_kg}",
                )
        elif k == "load_per_level_kg":
            if not isinstance(spec, ShelfUnitSpec):
                return False, "expected ShelfUnitSpec for load_per_level_kg"
            if abs(spec.load_per_level_kg - v) > _TOL:
                return (
                    False,
                    f"load_per_level_kg: expected {v}, got {spec.load_per_level_kg}",
                )
        elif k == "shelf_height_mm":
            if not isinstance(spec, TableSpec):
                return False, "expected TableSpec for shelf_height_mm"
            if v is None:
                if spec.shelf_height_mm is not None:
                    return (
                        False,
                        f"shelf_height_mm: expected None, got {spec.shelf_height_mm}",
                    )
            else:
                if spec.shelf_height_mm is None:
                    return False, "shelf_height_mm: expected value, got None"
                if abs(spec.shelf_height_mm - v) > _TOL:
                    return (
                        False,
                        f"shelf_height_mm: expected {v}, got {spec.shelf_height_mm}",
                    )
        elif k == "centre_legs":
            if spec.centre_legs != v:
                return False, f"centre_legs: expected {v}, got {spec.centre_legs}"
        elif k == "level_heights_mm_len":
            if not isinstance(spec, ShelfUnitSpec):
                return False, "expected ShelfUnitSpec for level_heights_mm"
            n = len(spec.level_heights_mm)
            if n != v:
                return False, f"level_heights_mm length: expected {v}, got {n}"
        elif k == "level_heights_mm_contains":
            if not isinstance(spec, ShelfUnitSpec):
                return False, "expected ShelfUnitSpec for level_heights_mm"
            if not any(abs(h - v) <= _TOL for h in spec.level_heights_mm):
                return (
                    False,
                    f"level_heights_mm does not contain {v}: {spec.level_heights_mm}",
                )

    return True, ""


def _score_prompt(
    p: dict[str, Any],
    result: EditResult,
) -> EditPromptResult:
    exp = p["expected"]
    exp_outcome = exp["outcome"]

    # Outcome must match
    if result.outcome != exp_outcome:
        return EditPromptResult(
            id=p["id"],
            group=p["group"],
            text=p["text"],
            expected=exp,
            result=result,
            passed=False,
            fail_reason=(
                f"outcome: expected {exp_outcome!r}, got {result.outcome!r}"
            ),
        )

    # Spec checks
    if "spec" in exp and exp_outcome in ("edit", "new_design"):
        ok, reason = _check_spec_fields(result, exp["spec"])
        if not ok:
            return EditPromptResult(
                id=p["id"],
                group=p["group"],
                text=p["text"],
                expected=exp,
                result=result,
                passed=False,
                fail_reason=reason,
            )

    # Missing checks (for clarify)
    if "missing" in exp and exp_outcome == "clarify":
        for m in exp["missing"]:
            if m not in result.missing:
                return EditPromptResult(
                    id=p["id"],
                    group=p["group"],
                    text=p["text"],
                    expected=exp,
                    result=result,
                    passed=False,
                    fail_reason=f"missing field {m!r} not in result.missing",
                )

    return EditPromptResult(
        id=p["id"],
        group=p["group"],
        text=p["text"],
        expected=exp,
        result=result,
        passed=True,
    )


# ── Parser runners ────────────────────────────────────────────────────────────

def _run_edit(config: str, text: str, spec_in: Any) -> EditResult | None:
    """
    Run edit_parse under the given config. Returns None if skipped.

    rule_based  — LLM disabled; rule parser + unsupported check only.
    llm         — full dispatcher (rule parser first, LLM fallback).
                  Skipped if no API key.
    dispatcher  — full dispatcher; LLM falls through to not_parsed
                  when no API key.
    """
    import framegen.parser.edit_llm as _edit_llm_mod

    if config == "rule_based":
        # Disable the edit LLM so only the rule parser runs.
        prev_client = _edit_llm_mod._client
        prev_explicit = _edit_llm_mod._client_set_explicitly
        _edit_llm_mod._client = None
        _edit_llm_mod._client_set_explicitly = True
        try:
            return edit_parse(text, spec_in, None)
        finally:
            _edit_llm_mod._client = prev_client
            _edit_llm_mod._client_set_explicitly = prev_explicit

    if config == "llm":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return None  # skip
        return edit_parse(text, spec_in, None)

    # dispatcher — full pipeline
    return edit_parse(text, spec_in, None)


# ── Reporting ─────────────────────────────────────────────────────────────────

def _report(
    config: str,
    prompt_results: list[EditPromptResult],
    skipped: bool,
) -> dict[str, Any]:
    if skipped:
        return {"config": config, "status": "skipped: no API key"}

    total = len(prompt_results)
    n_pass = sum(1 for r in prompt_results if r.passed)

    groups: dict[str, list[EditPromptResult]] = {}
    for r in prompt_results:
        groups.setdefault(r.group, []).append(r)
    group_scores = {
        g: f"{sum(1 for r in rs if r.passed)}/{len(rs)}"
        for g, rs in sorted(groups.items())
    }

    failures = [
        {
            "id": r.id,
            "text": r.text,
            "expected": r.expected,
            "got_outcome": r.result.outcome,
            "got_error": r.result.error,
            "fail_reason": r.fail_reason,
            "parser_used": r.result.parser_used,
        }
        for r in prompt_results
        if not r.passed
    ]

    return {
        "config": config,
        "status": "ok",
        "overall": f"{n_pass}/{total}",
        "by_group": group_scores,
        "failures": failures,
    }


def _print_report(rep: dict[str, Any]) -> None:
    config = rep.get("config", "?")
    if rep.get("status", "ok") != "ok":
        print(f"\n[{config}] {rep['status']}")
        return
    print(f"\n[{config}]  overall: {rep['overall']}")
    print(f"  by group: {rep['by_group']}")
    if rep["failures"]:
        print(f"  failures ({len(rep['failures'])}):")
        for f in rep["failures"]:
            print(f"    {f['id']} {f['text']!r}")
            print(
                f"      expected {f['expected']['outcome']!r}"
                f" | got {f['got_outcome']!r}"
                f" | {f['fail_reason']}"
            )


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

def run(
    config: str,
    prompt_file: Path,
) -> tuple[dict[str, Any], bool]:
    """Run the edit eval for one config. Returns (report, was_skipped)."""
    with open(prompt_file) as fh:
        data = json.load(fh)
    prompts: list[dict[str, Any]] = data["prompts"]

    prompt_results: list[EditPromptResult] = []
    for p in prompts:
        spec_in = _build_input_spec(p.get("input_spec"))
        result = _run_edit(config, p["text"], spec_in)
        if result is None:
            return {"config": config, "status": "skipped: no API key"}, True
        prompt_results.append(_score_prompt(p, result))

    return _report(config, prompt_results, skipped=False), False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        default="rule_based",
        choices=["rule_based", "llm", "dispatcher", "all"],
    )
    ap.add_argument("--file", default="dev", choices=["dev", "regression"])
    args = ap.parse_args()

    _file_map = {
        "dev": "prompts_edit_dev.json",
        "regression": "prompts_edit_regression.json",
    }
    prompt_file = _EVALS_DIR / _file_map[args.file]

    configs = (
        ["rule_based", "llm", "dispatcher"] if args.config == "all" else [args.config]
    )

    all_reports: list[dict[str, Any]] = []
    for config in configs:
        rep, _ = run(config, prompt_file)
        all_reports.append(rep)
        _print_report(rep)

    _RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    result_path = _RESULTS_DIR / f"{ts}_edit_{args.config}_{args.file}.json"
    with open(result_path, "w") as fh:
        json.dump(
            {
                "timestamp": ts,
                "git_hash": _git_hash(),
                "prompt_file": str(prompt_file.name),
                "prompt_file_version": (
                    json.load(open(prompt_file)).get("version")
                ),
                "configs": all_reports,
            },
            fh,
            indent=2,
        )
    print(f"\nResults saved to {result_path.relative_to(_ROOT)}")


if __name__ == "__main__":
    main()
