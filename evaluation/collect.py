"""Run frozen synthetic cases with the application's real offline BGE retriever."""
from evaluation.offline import ATTEMPTS

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from week1.chat import INDEX
from week1.retrieval import search, _documents, _corpus_digest, _open_index

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evaluation/retrieval-cases-v1.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect():
    manifest = json.loads(CASES.read_text())
    for name, digest in manifest["source_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("Reference source changed; review and version labels")
    connection, metadata = _open_index(INDEX)
    connection.close()
    if metadata["corpus_digest"] != _corpus_digest(_documents(Path(metadata["corpus_dir"]))):
        raise ValueError("Stale evaluation index")
    rows = []
    for case in manifest["cases"]:
        hits = search(case["query"], INDEX, limit=manifest["k_chunks"], service=case["service"])
        rows.append({"id": case["id"], "retrieved_ids": list(dict.fromkeys(h["doc_id"] for h in hits)),
                     "chunk_count": len(hits)})
    if ATTEMPTS:
        raise ValueError("Unexpected egress attempt")
    return {"schema": 1, "cases_sha256": sha(CASES), "corpus_digest": metadata["corpus_digest"],
            "encoder_fingerprint": metadata["encoder_fingerprint"], "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "collector_sha256": sha(Path(__file__)), "network_attempts": len(ATTEMPTS),
            "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = collect()
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Collected {len(report['cases'])} frozen retrieval cases; no prompt or source text exported")
