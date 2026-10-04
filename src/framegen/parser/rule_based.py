from __future__ import annotations

import re
from typing import NamedTuple

from pydantic import ValidationError

from framegen.parser import ParseResult
from framegen.spec import MIN_LEVEL_HEIGHT_MM, ShelfUnitSpec, TableSpec

# ── Regex helpers ─────────────────────────────────────────────────────────────

_NUM_UNIT_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*'
    r'(mm|millimetres?|millimeters?'
    r'|cm|centimetres?|centimeters?'
    r'|m(?!m)(?!etre)(?!eter)|metres?|meters?'
    r'|kg|kilograms?'
    r')\b',
    re.IGNORECASE,
)
_BARE_NUM_RE = re.compile(r'(\d+(?:\.\d+)?)(?!\s*(?:mm|cm|m(?!m)|kg|kilograms?)|\d)')

_UNITLESS_SMALL = 100.0

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

_BLOCK_UNIT = (
    r'millimetres?|millimeters?|mm'
    r'|centimetres?|centimeters?|cm'
    r'|metres?|meters?|m\b'
)
_BLOCK_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(' + _BLOCK_UNIT + r')?\s*(?:x|×|by)\s*'
    r'(\d+(?:\.\d+)?)\s*(' + _BLOCK_UNIT + r')?'
    r'(?:\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*(' + _BLOCK_UNIT + r')?)?',
    re.IGNORECASE,
)

# ── Shelf-unit detection ──────────────────────────────────────────────────────

# Words that unambiguously signal a shelf unit (not a table/bench)
_SHELF_UNIT_RE = re.compile(
    r'(?<!\w)(?:'
    r'shelf\s+unit|shelving(?:\s+unit)?|bookcase|bookshelf'
    r'|racking?|display\s+unit|storage\s+(?:unit|rack)|display\s+rack'
    r')(?!\w)',
    re.IGNORECASE,
)

# "3 shelves", "4 levels", "5-tier", …
_LEVEL_COUNT_RE = re.compile(
    r'(\d+)\s*[-\s]?(?:shelf|shelves|level|levels|tier|tiers)(?!\w)',
    re.IGNORECASE,
)

# Keywords whose nearby numbers are shelf heights (not the frame W/D/H)
_SHELF_H_KW = re.compile(
    r'(?<!\w)(?:shelf|shelves|level|levels|tier|tiers)(?!\w)',
    re.IGNORECASE,
)

_SHELF_H_RADIUS = 80  # chars around a shelf/level/tier keyword

# Word-number count phrases: "four levels", "six shelves", …
_WORD_COUNT_RE = re.compile(
    r'(?<!\w)(two|three|four|five|six|seven|eight|nine|ten)'
    r'\s*[-\s]?(?:shelf|shelves|level|levels|tier|tiers)(?!\w)',
    re.IGNORECASE,
)
_WORD_TO_N: dict[str, int] = {
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
# "per level", "per shelf", "per tier" — unambiguous shelf-unit language
_PER_LEVEL_RE = re.compile(
    r'(?<!\w)per\s+(?:level|shelf|tier)(?!\w)',
    re.IGNORECASE,
)
# "shelves" plural standalone — ambiguous without a count; must not silently
# become a table, so the table parser returns not_parsed to let the LLM decide.
_SHELVES_PLURAL_RE = re.compile(r'(?<!\w)shelves(?!\w)', re.IGNORECASE)


# ── Tokens ────────────────────────────────────────────────────────────────────

class _Tok(NamedTuple):
    raw: float
    unit: str   # "mm" | "cm" | "m" | "kg" | ""
    start: int
    end: int

    @property
    def mm(self) -> float:
        if self.unit == "cm":
            return self.raw * 10.0
        if self.unit == "m":
            return self.raw * 1000.0
        return self.raw

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

_SEARCH_RADIUS = 40


def _effective_slot(slot: str, kw_text: str, text: str) -> str:
    if slot == "width" and _KW_LONG.search(text) and _KW_WIDE.search(text):
        if _KW_WIDE.search(kw_text):
            return "depth"
    return slot


def _keyword_assignments(
    text: str, tokens: list[_Tok], pre_assigned: set[int],
    filled_slots: set[str] | None = None,
) -> dict[int, str]:
    kw_hits: list[tuple[int, str, str]] = []
    for slot, pat in _KW.items():
        for m in pat.finditer(text):
            kw_hits.append((m.start(), slot, m.group(0)))
    kw_hits.sort()

    assigned_tok: dict[int, str] = {}
    assigned_slots: dict[str, int] = {}
    _filled = filled_slots or set()

    for kw_pos, slot, kw_text in kw_hits:
        effective = _effective_slot(slot, kw_text, text)
        if effective in assigned_slots or effective in _filled:
            continue
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
    w: float
    d: float
    h: float | None
    raw_vals: list[tuple[float, str]]
    start: int
    end: int


def _to_mm(raw: float, unit: str) -> float:
    if unit == "cm":
        return raw * 10.0
    if unit == "m":
        return raw * 1000.0
    return raw


def _find_first_block(text: str) -> _Block | None:
    m = _BLOCK_RE.search(text)
    if not m:
        return None

    vals: list[tuple[float, str]] = [
        (float(m.group(1)), _norm_unit(m.group(2) or "")),
        (float(m.group(3)), _norm_unit(m.group(4) or "")),
    ]
    if m.group(5):
        vals.append((float(m.group(5)), _norm_unit(m.group(6) or "")))

    if len(vals) >= 2 and vals[-1][1] != "" and all(v[1] == "" for v in vals[:-1]):
        trail = vals[-1][1]
        vals = [(v[0], trail) for v in vals]

    w = _to_mm(*vals[0])
    d = _to_mm(*vals[1])
    h = _to_mm(*vals[2]) if len(vals) > 2 else None

    return _Block(w=w, d=d, h=h, raw_vals=list(vals), start=m.start(), end=m.end())


# ── Shelf-unit helpers ────────────────────────────────────────────────────────

def _count_pos_set(text: str, tokens: list[_Tok]) -> set[int]:
    """Token indices that are part of a level-count phrase like '3 levels'."""
    pos: set[int] = set()
    for cm in _LEVEL_COUNT_RE.finditer(text):
        for i, tok in enumerate(tokens):
            if tok.start >= cm.start() and tok.end <= cm.end():
                pos.add(i)
    return pos


def _shelf_nearby_values(
    text: str,
    tokens: list[_Tok],
    block_indices: set[int],
    count_pos: set[int],
) -> list[float]:
    """
    Sorted mm values of tokens that sit near a shelf/level/tier keyword and
    are plausible level heights (≥ MIN_LEVEL_HEIGHT_MM).  Excludes block
    tokens, kg tokens, and count-phrase tokens.
    """
    seen: set[int] = set()
    values: list[float] = []
    for m in _SHELF_H_KW.finditer(text):
        kpos = m.start()
        for i, tok in enumerate(tokens):
            if i in block_indices or tok.unit == "kg" or i in count_pos:
                continue
            if i in seen:
                continue
            dist = min(abs(tok.start - kpos), abs(tok.end - kpos))
            if dist <= _SHELF_H_RADIUS and tok.mm >= MIN_LEVEL_HEIGHT_MM:
                seen.add(i)
                values.append(tok.mm)
    return sorted(values)


def _evenly_spaced_levels(H: float, n: int) -> list[float]:
    """n evenly-spaced levels ending exactly at H."""
    levels: list[float] = [float(round(H * (i + 1) / n)) for i in range(n)]
    levels[-1] = H
    return levels


def _try_parse_shelf_unit(
    text: str,
    tokens: list[_Tok],
    block: _Block | None,
) -> ParseResult | None:
    """
    Attempt to parse the text as a shelf unit.  Returns None if the text does
    not contain a shelf-unit signal so the caller can fall through to the table
    parser.

    Signals:
      (a) Two or more explicit heights near a shelf/level/tier keyword.
      (b) Shelf-unit type words (bookcase, shelving unit, rack, …).
    """
    has_signal = bool(_SHELF_UNIT_RE.search(text))
    has_count = bool(_LEVEL_COUNT_RE.search(text)) or bool(_WORD_COUNT_RE.search(text))
    has_per_level = bool(_PER_LEVEL_RE.search(text))

    block_indices: set[int] = set()
    if block is not None:
        block_indices = {
            i
            for i, tok in enumerate(tokens)
            if block.start <= tok.start < block.end
        }

    count_pos = _count_pos_set(text, tokens)
    shelf_vals = _shelf_nearby_values(text, tokens, block_indices, count_pos)
    has_two_shelves = len(shelf_vals) >= 2

    if not has_signal and not has_two_shelves and not has_count and not has_per_level:
        return None

    if block is None:
        # Signals present but no dimension block — cannot build spec; go to LLM.
        return _NOT_PARSED

    for raw_n, raw_u in block.raw_vals:
        if raw_u == "" and raw_n < _UNITLESS_SMALL:
            return _unitless_small_error(raw_n)

    W = block.w
    D = block.d
    H_from_block = block.h

    defaults: list[str] = []

    # Frame height
    if H_from_block is not None:
        H = H_from_block
    elif shelf_vals:
        H = shelf_vals[-1]   # last explicit shelf height IS the frame top
    else:
        H = 1800.0 if has_signal else 900.0
        defaults.append(f"height_mm={int(H)}")

    # Level heights
    if has_two_shelves:
        levels: list[float] = list(shelf_vals)
        if abs(levels[-1] - H) > 1.0:
            levels = [v for v in levels if v < H - 1.0]
            levels.append(H)
    else:
        # Signal word without explicit heights — use count or default 3.
        # User-supplied counts are NOT clamped: "2 shelves" → 2 levels → spec_invalid;
        # "12 levels" → 12 levels → spec_invalid. Only the implicit default 3 is safe.
        count_m = _LEVEL_COUNT_RE.search(text)
        word_m = _WORD_COUNT_RE.search(text)
        if count_m:
            n = int(count_m.group(1))
        elif word_m:
            n = _WORD_TO_N[word_m.group(1).lower()]
        else:
            n = 3
        levels = _evenly_spaced_levels(H, n)

    # Load per level
    load_toks = [tok for tok in tokens if tok.unit == "kg"]
    if load_toks:
        load_per_level: float = load_toks[0].kg
    else:
        load_per_level = 30.0
        defaults.append("load_per_level_kg=30")

    try:
        spec = ShelfUnitSpec.model_validate(
            dict(
                frame_type="shelf_unit",
                width_mm=W,
                depth_mm=D,
                height_mm=H,
                profile_series="40-series",
                level_heights_mm=levels,
                load_per_level_kg=load_per_level,
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

    # ── Shelf-unit fast path ──────────────────────────────────────────────────
    shelf_result = _try_parse_shelf_unit(text, tokens, block)
    if shelf_result is not None:
        return shelf_result

    # "shelves" plural without a count or explicit heights cannot be resolved by
    # the rule parser.  Return not_parsed so the LLM can decide (shelf unit vs
    # table with multiple shelves).
    if _SHELVES_PLURAL_RE.search(text):
        return _NOT_PARSED

    # ── Slot candidates ───────────────────────────────────────────────────────
    slots: dict[str, list[float]] = {
        "width": [], "depth": [], "height": [], "shelf": [], "load": []
    }
    assigned_tok_indices: set[int] = set()

    # (A) kg tokens → load
    for i, tok in enumerate(tokens):
        if tok.unit == "kg":
            slots["load"].append(tok.kg)
            assigned_tok_indices.add(i)

    # (B) Reserve block tokens
    block_inside: list[int] = []
    if block is not None:
        block_inside = [
            i for i, tok in enumerate(tokens) if block.start <= tok.start < block.end
        ]
        for i in block_inside:
            assigned_tok_indices.add(i)

    # (C) Keyword-matched tokens
    pre_filled: set[str] = set()
    if slots["load"]:
        pre_filled.add("load")
    kw_map = _keyword_assignments(
        text, tokens, assigned_tok_indices, filled_slots=pre_filled
    )
    for tok_idx, slot in kw_map.items():
        tok = tokens[tok_idx]
        is_dim = slot in ("width", "depth", "height")
        if is_dim and tok.unit == "" and tok.raw < _UNITLESS_SMALL:
            return _unitless_small_error(tok.raw)
        val = tok.kg if slot == "load" else tok.mm
        slots[slot].append(val)
        assigned_tok_indices.add(tok_idx)

    # (D) Positional block
    if block is not None:
        for raw_n, raw_u in block.raw_vals:
            if raw_u == "" and raw_n < _UNITLESS_SMALL:
                return _unitless_small_error(raw_n)

        if not slots["width"] and not slots["depth"]:
            slots["width"].append(block.w)
            slots["depth"].append(block.d)
            if block.h is not None and not slots["height"]:
                slots["height"].append(block.h)

    # ── Strict accounting ─────────────────────────────────────────────────────
    for i in range(len(tokens)):
        if i not in assigned_tok_indices:
            return _NOT_PARSED

    # ── Duplicate slot candidates → not_parsed ─────────────────────────────────
    for slot, cands in slots.items():
        if len(cands) > 1:
            return _NOT_PARSED

    # ── Required fields ───────────────────────────────────────────────────────
    if not slots["width"] or not slots["depth"]:
        return _NOT_PARSED

    # ── Build spec ────────────────────────────────────────────────────────────
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
        spec = TableSpec.model_validate(
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
