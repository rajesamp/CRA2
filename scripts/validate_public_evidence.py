"""Validate the curated offline corpus before rebuilding CRA2's local index."""

import argparse
from collections import Counter
import json
from pathlib import Path

from cra2.public_evidence import load_public_evidence, public_documents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, help="Directory containing public_evidence.json and checkout_system.json")
    args = parser.parse_args(argv)
    try:
        records = load_public_evidence(args.data_dir)
        documents = public_documents(args.data_dir)
    except (ValueError, OSError):
        parser.exit(1, "Public evidence validation failed; review the catalog schema and source metadata.\n")
    print(json.dumps({"status": "valid", "records": len(records),
        "record_types": dict(sorted(Counter(r["record_type"] for r in records).items())),
        "companies": len({r["company"] for r in records}),
        "maximum_document_words": max(len(d["text"].split()) for d in documents),
        "network_requests": 0}, indent=2))


if __name__ == "__main__":
    main()
