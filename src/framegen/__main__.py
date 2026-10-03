from __future__ import annotations

import argparse
import sys

from framegen.catalog import load_catalog
from framegen.generate.table import generate_table
from framegen.outputs.cut_list import build_cut_list, format_cut_list
from framegen.spec import TableSpec


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a frame cut list.")
    parser.add_argument("--width", type=float, required=True, metavar="MM")
    parser.add_argument("--depth", type=float, required=True, metavar="MM")
    parser.add_argument("--height", type=float, required=True, metavar="MM")
    parser.add_argument(
        "--shelf",
        type=float,
        default=None,
        metavar="MM",
        help="height of the top face of shelf rails above the floor (mm)",
    )
    parser.add_argument("--profile-series", default="40-series", metavar="SERIES")
    parser.add_argument("--load", type=float, default=100.0, metavar="KG")
    args = parser.parse_args()

    catalog = load_catalog()

    if args.profile_series not in catalog.profiles:
        print(
            f"Error: profile series '{args.profile_series}' not in catalog.",
            file=sys.stderr,
        )
        sys.exit(1)

    profile = catalog.profiles[args.profile_series]

    spec = TableSpec(
        frame_type="table",
        width_mm=args.width,
        depth_mm=args.depth,
        height_mm=args.height,
        profile_series=args.profile_series,
        shelf_height_mm=args.shelf,
        target_load_kg=args.load,
    )

    bars = generate_table(spec, profile)
    cut_list = build_cut_list(bars)
    print(format_cut_list(cut_list))


if __name__ == "__main__":
    main()
