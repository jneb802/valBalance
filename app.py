#!/usr/bin/env python3
"""Analyze shrine scenarios from JSON using only Python's standard library."""
import argparse
import json
import sys
from pathlib import Path

from model import DEFAULTS, analyze


def format_value(value):
    if value is None:
        return "not reached"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def report(data, result):
    lines = ["SHRINE BALANCE — deterministic planning estimates", "",
             "Creature TTK starts at attack initiation; player TTD starts at first impact.",
             "HTD excludes healing, blocking, parrying, and random hit avoidance.", ""]
    for enemy, row in zip(data["enemies"], result["enemies"]):
        lines.extend([
            f"{row['name']} [{enemy['role']}] — {row['health']:g} HP" + (f" / {row['stars']} stars" if row['stars'] is not None else ""),
            f"  Raw attack: {row['raw_physical']:g} physical + {row['raw_elemental']:g} elemental",
            f"  HTK: {row['htk']} ({row['htk_rating']})",
            f"  Focused TTK: {row['ttk']:.2f}s ({row['ttk_rating']}); practical estimate: {row['practical']:.2f}s",
            f"  Received damage: {row['damage']:.2f} normal / {row['low_damage']:.2f} at low health",
            f"  Player HTD: {format_value(row['htd'])} ({row['htd_rating']}); TTD: {format_value(row['ttd'])} seconds",
        ])
        if row['target_possible']:
            upper = f" and <= {row['health_max']:g}" if row['health_max'] is not None else ""
            lines.append(f"  Health fitting both targets: > {row['health_min_exclusive']:g}{upper}")
        else:
            lines.append("  No health value satisfies both targets at this attack speed.")
        lines.append("")
    for wave in result["waves"]:
        lines.extend([
            f"{wave['name']} — {wave['count']} enemies",
            f"  Sequential clear estimate: {wave['clear']:.2f}s",
            f"  Constant-pack damage/s: {wave['pressure']:.2f} normal / {wave['low_pressure']:.2f} at low health",
            f"  Constant-pack TTD: {format_value(wave['ttd'])} seconds; clear/TTD: {format_value(wave['ratio'])}",
            "",
        ])
    lines.extend([
        "ASSUMPTIONS",
        "Effective player damage must be immediate damage after target defenses, not total poison payload.",
        "Practical TTK divides focused TTK by attack uptime. Wave clear sums sequential single-target kills.",
        "Wave pressure holds all enemies alive and spreads damage evenly, minus entered healing.",
        "No area attacks, poison timing, triggered effects, enemy healing, or spawn delays are simulated.",
        "Ratios are comparisons of assumptions, not difficulty scores. Validate with in-game measurements.",
    ])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    example = commands.add_parser("example", help="Write an editable Snuffiss / Black Forest example")
    example.add_argument("output", type=Path)
    calculate = commands.add_parser("analyze", help="Analyze a scenario")
    calculate.add_argument("scenario", type=Path)
    calculate.add_argument("--json", action="store_true", help="Output machine-readable results")
    calculate.add_argument("--output", type=Path, help="Write report to a new file instead of stdout")
    args = parser.parse_args(argv)
    try:
        if args.command == "example":
            with args.output.open("x") as stream:
                json.dump(DEFAULTS, stream, indent=2, allow_nan=False)
                stream.write("\n")
            print(f"Wrote {args.output}. Attack damage and timings are examples; replace them with measurements.")
            return 0
        with args.scenario.open() as stream:
            data = json.load(stream)
        result = analyze(data)
        output = json.dumps(result, indent=2, allow_nan=False) + "\n" if args.json else report(data, result)
        if args.output:
            with args.output.open("x") as stream:
                stream.write(output)
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
