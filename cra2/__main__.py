"""CRA2 command line:  cra2 CHG-01 | change.json | -  [--mode fast|auto|deep] [--json]"""

import argparse
import json
import re
import sys
from pathlib import Path

MAX_INPUT_CHARACTERS = 1024 * 1024


def _reject_constant(value: str):
    raise ValueError(f"Change JSON contains the nonstandard numeric value {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Change JSON contains duplicate object keys")
        value[key] = item
    return value


def _read_change(stream) -> object:
    """Bound decoded input to 1,048,576 Unicode characters before JSON parsing."""
    raw = stream.read(MAX_INPUT_CHARACTERS + 1)
    if len(raw) > MAX_INPUT_CHARACTERS:
        raise ValueError(f"Change JSON exceeds {MAX_INPUT_CHARACTERS:,} characters")
    try:
        return json.loads(
            raw, parse_constant=_reject_constant, object_pairs_hook=_unique_object
        )
    except RecursionError as exc:
        raise ValueError("Change JSON nesting is too deep") from exc


def _load_change(source: str, evals_dir: Path) -> dict:
    if source == "-":
        change = _read_change(sys.stdin)
    elif re.fullmatch(r"CHG-\d+", source):
        cases = json.loads((evals_dir / "cases.json").read_text(encoding="utf-8"))
        change = next((case["change"] for case in cases if case["id"] == source), None)
        if change is None:
            raise ValueError(f"Unknown sample case {source!r}")
    else:
        with Path(source).open(encoding="utf-8") as stream:
            change = _read_change(stream)
    if not isinstance(change, dict):
        raise ValueError("Change JSON must be an object")
    return change


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="cra2", description="Advisory-only change-risk assessment."
    )
    p.add_argument(
        "change",
        help="an eval case ID such as CHG-01, a change JSON file, or - for stdin",
    )
    p.add_argument(
        "--mode",
        choices=["fast", "auto", "deep"],
        help="assessment mode (default: CRA2_MODE or auto)",
    )
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = p.parse_args(argv)
    try:
        # Defer imports so bad configuration produces a CLI error, and --help
        # works without loading settings, the catalog, or the Groq SDK.
        from cra2 import config
        from cra2.advisor import assess, render

        change = _load_change(args.change, config.EVALS_DIR)
        result = assess(change, args.mode or config.MODE)
    except (OSError, ValueError) as exc:
        p.error(str(exc))
    print(json.dumps(result, indent=2) if args.json else render(result))


if __name__ == "__main__":
    main()
