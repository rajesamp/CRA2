"""CRA2 command line:  cra2 CHG-01 | change.json | -  [--mode fast|auto|deep] [--json]"""

import argparse
import json
import sys
from pathlib import Path

from cra2 import config
from cra2.advisor import assess, render


def main(argv=None):
    p = argparse.ArgumentParser(prog="cra2", description="Advisory-only change-risk assessment.")
    p.add_argument("change", help="an eval case ID such as CHG-01, a change JSON file, or - for stdin")
    p.add_argument("--mode", choices=["fast", "auto", "deep"], default=config.MODE)
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = p.parse_args(argv)
    cases = {c["id"]: c["change"] for c in json.loads((config.PKG_DIR.parent / "evals" / "cases.json").read_text())}
    try:
        raw = sys.stdin.read() if args.change == "-" else None
        change = cases.get(args.change) or json.loads(raw or Path(args.change).read_text())
        result = assess(change, args.mode)
    except (OSError, ValueError) as exc:  # bad path, bad JSON, unknown service, missing field
        p.error(str(exc))
    print(json.dumps(result, indent=2) if args.json else render(result))


if __name__ == "__main__":
    main()
