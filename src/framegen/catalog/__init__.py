from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_CATALOG_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "catalog" / "catalog-v2.json"
)


class Profile(BaseModel):
    model_config = ConfigDict(frozen=True)

    part_number: str
    series: str
    profile_width_mm: float
    price_per_metre: float | None = None
    mass_per_metre_kg: float | None = None
    alloy: str | None = None
    youngs_modulus_mpa: float | None = None
    yield_strength_mpa: float | None = None
    moment_of_inertia_mm4: float | None = None
    source: str
    source_url: str


class Catalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int
    profiles: dict[str, Profile]


def load_catalog(path: Path = _CATALOG_PATH) -> Catalog:
    catalog = Catalog.model_validate_json(path.read_text())
    for profile in catalog.profiles.values():
        if profile.price_per_metre is None:
            print(
                f"WARNING: catalog: price_per_metre missing for {profile.part_number}",
                file=sys.stderr,
            )
        if profile.mass_per_metre_kg is None:
            print(
                "WARNING: catalog: mass_per_metre_kg missing for"
                f" {profile.part_number}",
                file=sys.stderr,
            )
        if profile.youngs_modulus_mpa is None:
            print(
                "WARNING: catalog: youngs_modulus_mpa missing for"
                f" {profile.part_number}",
                file=sys.stderr,
            )
        if profile.yield_strength_mpa is None:
            print(
                "WARNING: catalog: yield_strength_mpa missing for"
                f" {profile.part_number}",
                file=sys.stderr,
            )
        if profile.moment_of_inertia_mm4 is None:
            print(
                "WARNING: catalog: moment_of_inertia_mm4 missing for"
                f" {profile.part_number}",
                file=sys.stderr,
            )
    return catalog
