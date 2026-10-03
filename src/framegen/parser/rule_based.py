from __future__ import annotations

import re
from typing import NamedTuple

from pydantic import ValidationError

from framegen.parser import ParseResult
from framegen.spec import FrameSpec

# ── Regex helpers ─────────────────────────────────────────────────────────────

# Matches a number (int or decimal) then an optional unit suffix.
# Accepts both abbreviations (mm, cm, m, kg) and spelled-out forms.
# Group 1 = digits, Group 2 = unit token.
_NUM_UNIT_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(mm|millimetres?|millimeters?'
    r'|cm|centimetres?|centimeters?'
    r'|m(?!m)(?!etre)(?!eter)|metres?|meters?'
    r'|kg|kilograms?'
    r')\b',
    re.IGNORECASE,
)
# Matches a bare number (no unit) — handled separately.
_BARE_NUM_RE = re.compile(r'(\d+(?:\.\d+)?)(?!\s*(?:mm|cm|m(?!m)|kg|kilograms?)|\d)')

_UNITLESS_SMALL = 100.0  # bare numbers < this in dimension context are ambiguous

# Dimension keywords — separate "long" so it can be remapped when "wide" also appears
_KW_LONG = re.compile(r'(?<!\w)(?:long(?:er)?|length)(?!\w)', re.IGNORECASE)
_KW_WIDE = re.compile(r'(?<!\w)(?:wide(?:r)?|width)(?!\w)', re.IGNORECASE)
_KW = {
    "width":  re.compile(
        r'(?<!\w)(?:wide(?:r)?|width|long(?:er)?|length)(?!\w)', re.IGNORECASE
    ),
    "depth":  re.compile(r'(?<!\w)(?:deep(?:er)?|depth)(?!\w)', re.IGNORECASE),
    "height": re.compile(
        r'(?<!\w)(?:tall(?:er)?|height|high(?:er)?)(?!\w)', re.IGNORECASE
    ),
    "shelf":  re.compile(r'(?<!\w)(?:shelf|shelves)(?!\w)', re.IGNORECASE),
    "load":   re.compile(
        r'(?<!\w)(?:holds?|load(?:ing)?|capacity|support(?:s)?)(?!\w)', re.IGNORECASE
    ),
}

# Positional N×N or N×N×N block
_BLOCK_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(mm|cm|m(?!m)|)?\s*(?:x|×|by)\s*'
    r'(\d+(?:\.\d+)?)\s*(mm|cm|m(?!m)|)?'
    r'(?:\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*(mm|cm|m(?!m)|)?)?',
    re.IGNORECASE,
)


# ── Tokens ────────────────────────────────────────────────────────────────────

class _Tok(NamedTuple):
    raw: float    # numeric value as written
    unit: str     # "mm" | "cm" | "m" | "kg" | ""
    start: int
    end: int

    @property
    def mm(self) -> float:
        if self.unit == "cm":
            return self.raw * 10.0
        if self.unit == "m":
            return self.raw * 1000.0
        return self.raw  # mm or bare (bare ≥100 treated as mm; bare <100 flagged)

    @property
    def kg(self) -> float:
        return self.raw


def _norm_unit(u: str) -> str:
    u = u.lower()
    if u in ("kg", "kilogram", "kilograms"):
        return "kg"
    if u in ("cm", "centimetre", "centimetres", "centimeter", "centimeters"):
        return "cm"
    if u in ("m", "metre", "metres", "meter", "meters"):
        return "m"
    if u in ("mm", "millimetre", "millimetres", "millimeter", "millimeters"):
        return "mm"
    return ""


def _extract_all_tokens(text: str) -> list[_Tok]:
    """Extract every numeric token with its unit (if any)."""
    tokens: list[_Tok] = []
    used: set[int] = set()

    for m in _NUM_UNIT_RE.finditer(text):
        raw = float(m.group(1))
        unit = _norm_unit(m.group(2))
        tokens.append(_Tok(raw=raw, unit=unit, start=m.start(), end=m.end()))
        for i in range(m.start(), m.end()):
            used.add(i)

    for m in _BARE_NUM_RE.finditer(text):
        if m.start() in used:
            continue
        raw = float(m.group(1))
        tokens.append(_Tok(raw=raw, unit="", start=m.start(), end=m.end()))

    tokens.sort(key=lambda t: t.start)
    return tokens


# ── Keyword→nearest-token assignment ─────────────────────────────────────────

_SEARCH_RADIUS = 40  # chars: how far to look for a keyword near a number


def _effective_slot(slot: str, kw_text: str, text: str) -> str:
    """
    When "long/length" and "wide/width" BOTH appear in the text, treat
    "long/length" as width and "wide/width" as depth (furniture convention:
    long = longest side, wide = shorter horizontal side).
    """
    if slot == "width" and _KW_LONG.search(text) and _KW_WIDE.search(text):
        if _KW_WIDE.search(kw_text):
            return "depth"
    return slot


def _keyword_assignments(
    text: str, tokens: list[_Tok], pre_assigned: set[int],
    filled_slots: set[str] | None = None,
) -> dict[int, str]:
    """
    Return {token_index: slot_name} for keyword-matched tokens.

    For each keyword occurrence, find the nearest unassigned token within
    _SEARCH_RADIUS chars and assign it to that slot.  Earlier occurrences
    take priority.  A token can only be assigned once.
    """
    # Collect keyword occurrences: (position, slot, matched_text)
    kw_hits: list[tuple[int, str, str]] = []
    for slot, pat in _KW.items():
        for m in pat.finditer(text):
            kw_hits.append((m.start(), slot, m.group(0)))
    kw_hits.sort()  # process in text order

    assigned_tok: dict[int, str] = {}   # token_index → slot
    assigned_slots: dict[str, int] = {} # slot → token_index (first wins)
    _filled = filled_slots or set()

    for kw_pos, slot, kw_text in kw_hits:
        effective = _effective_slot(slot, kw_text, text)
        if effective in assigned_slots or effective in _filled:
            # Already have a token for this slot — skip (duplicate handled later)
            continue
        # Find nearest unassigned token within radius
        best_idx: int | None = None
        best_dist = _SEARCH_RADIUS + 1
        for i, tok in enumerate(tokens):
            if i in assigned_tok or i in pre_assigned:
                continue
            dist = min(abs(tok.start - kw_pos), abs(tok.end - kw_pos))
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx is not None and best_idx not in assigned_tok:
            assigned_tok[best_idx] = effective
            assigned_slots[effective] = best_idx

    return assigned_tok


# ── Block parser ──────────────────────────────────────────────────────────────

class _Block(NamedTuple):
    w: float  # mm
    d: float  # mm
    h: float | None  # mm
    raw_vals: list[tuple[float, str]]  # (raw_number, unit) for each position
    start: int
    end: int


def _find_first_block(text: str) -> _Block | None:
    m = _BLOCK_RE.search(text)
    if not m:
        return None
    n1, u1 = float(m.group(1)), _norm_unit(m.group(2) or "")
    n2, u2 = float(m.group(3)), _norm_unit(m.group(4) or "")
    w = n1 * (10 if u1 == "cm" else 1000 if u1 == "m" else 1)
    d = n2 * (10 if u2 == "cm" else 1000 if u2 == "m" else 1)
    h: float | None = None
    raw_vals = [(n1, u1), (n2, u2)]
    if m.group(5):
        n3, u3 = float(m.group(5)), _norm_unit(m.group(6) or "")
        h = n3 * (10 if u3 == "cm" else 1000 if u3 == "m" else 1)
        raw_vals.append((n3, u3))
    return _Block(w=w, d=d, h=h, raw_vals=raw_vals, start=m.start(), end=m.end())


# ── Main parse ────────────────────────────────────────────────────────────────

_NOT_PARSED = ParseResult(
    outcome="not_parsed", spec=None, error=None, parser_used="rule_based"
)


def _unitless_small_error(raw: float) -> ParseResult:
    return ParseResult(
        outcome="spec_invalid",
        spec=None,
        error=(
            f"Unitless number {raw:g} is ambiguous "
            "(mm, cm, or m?). Please add units."
        ),
        parser_used="rule_based",
    )


def parse(text: str) -> ParseResult:  # noqa: C901
    """
    Strict rule-based parser.
    Pre-checks (imperial, enclosure) must be applied by the caller.
    """
    tokens = _extract_all_tokens(text)
    block = _find_first_block(text)

    # ── Slot candidates ───────────────────────────────────────────────────────
    slots: dict[str, list[float]] = {
        "width": [], "depth": [], "height": [], "shelf": [], "load": []
    }
    assigned_tok_indices: set[int] = set()

    # (A) Tokens with kg unit are unambiguously load.
    for i, tok in enumerate(tokens):
        if tok.unit == "kg":
            slots["load"].append(tok.kg)
            assigned_tok_indices.add(i)

    # (B) Pre-reserve block tokens so keyword assignment can't steal them.
    #     Block tokens are only for W/D/H positional assignment (step D).
    block_inside: list[int] = []
    if block is not None:
        block_inside = [
            i for i, tok in enumerate(tokens) if block.start <= tok.start < block.end
        ]
        for i in block_inside:
            assigned_tok_indices.add(i)

    # (C) Keyword-matched tokens (nearest-neighbour, skips already-assigned)
    pre_filled: set[str] = set()
    if slots["load"]:
        pre_filled.add("load")
    kw_map = _keyword_assignments(
        text, tokens, assigned_tok_indices, filled_slots=pre_filled
    )
    for tok_idx, slot in kw_map.items():
        tok = tokens[tok_idx]
        # Unitless-small check for dimension candidates
        is_dim = slot in ("width", "depth", "height")
        if is_dim and tok.unit == "" and tok.raw < _UNITLESS_SMALL:
            return _unitless_small_error(tok.raw)
        val = tok.kg if slot == "load" else tok.mm
        slots[slot].append(val)
        assigned_tok_indices.add(tok_idx)

    # (D) Positional block — fills ONLY slots not already filled by keywords
    if block is not None:
        # Check for unitless-small in block values
        for raw_n, raw_u in block.raw_vals:
            if raw_u == "" and raw_n < _UNITLESS_SMALL:
                return _unitless_small_error(raw_n)

        # Assign block values to empty slots
        if not slots["width"] and not slots["depth"]:
            slots["width"].append(block.w)
            slots["depth"].append(block.d)
            if block.h is not None and not slots["height"]:
                slots["height"].append(block.h)

    # ── Two-shelf rejection ──────────────────────────────────────────────────
    # Check before strict accounting: find all numbers within 60 chars of any
    # "shelf" keyword; if 2 or more distinct numbers are found, reject.
    for sm in _KW["shelf"].finditer(text):
        spos = sm.start()
        nearby = [
            tok for i, tok in enumerate(tokens)
            if i not in set(block_inside)  # block tokens are W/D/H, not shelf heights
            and tok.unit != "kg"           # load tokens are not shelf heights
            and min(abs(tok.start - spos), abs(tok.end - spos)) <= 60
        ]
        if len(nearby) >= 2:
            return ParseResult(
                outcome="spec_invalid",
                spec=None,
                error="Only one shelf height is supported.",
                parser_used="rule_based",
            )

    if len(slots["shelf"]) >= 2:
        return ParseResult(
            outcome="spec_invalid",
            spec=None,
            error="Only one shelf height is supported.",
            parser_used="rule_based",
        )

    # ── Strict accounting: any unassigned token → not_parsed ─────────────────
    for i in range(len(tokens)):
        if i not in assigned_tok_indices:
            return _NOT_PARSED

    # ── Duplicate slot candidates → not_parsed ────────────────────────────────
    for slot, cands in slots.items():
        if len(cands) > 1:
            return _NOT_PARSED

    # ── Required fields ───────────────────────────────────────────────────────
    if not slots["width"] or not slots["depth"]:
        return _NOT_PARSED

    # ── Build spec with defaults ──────────────────────────────────────────────
    defaults: list[str] = []

    width_mm = slots["width"][0]
    depth_mm = slots["depth"][0]

    if slots["height"]:
        height_mm = slots["height"][0]
    else:
        height_mm = 900.0
        defaults.append("height_mm=900")

    load_kg = slots["load"][0] if slots["load"] else None
    if load_kg is None:
        load_kg = 100.0
        defaults.append("target_load_kg=100")

    shelf_height: float | None = None
    if slots["shelf"]:
        shelf_height = slots["shelf"][0]
    elif _KW["shelf"].search(text):
        shelf_height = 300.0
        defaults.append("shelf_height_mm=300")

    try:
        spec = FrameSpec.model_validate(
            dict(
                frame_type="table",
                width_mm=width_mm,
                depth_mm=depth_mm,
                height_mm=height_mm,
                profile_series="40-series",
                target_load_kg=load_kg,
                shelf_height_mm=shelf_height,
            )
        )
    except ValidationError as exc:
        msgs = "; ".join(e["msg"] for e in exc.errors())
        return ParseResult(
            outcome="spec_invalid",
            spec=None,
            error=msgs,
            parser_used="rule_based",
        )

    return ParseResult(
        outcome="spec_valid",
        spec=spec,
        error=None,
        defaults_applied=defaults,
        parser_used="rule_based",
    )
