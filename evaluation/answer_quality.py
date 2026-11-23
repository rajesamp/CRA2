"""Calibrate public C3 controls against a closed vocabulary of synthetic answers."""
from evaluation import offline  # install the socket boundary before scoring
from evaluation.answer_packet import Incomplete, digest, grade_binding, require, verify_binding

import argparse
from collections import Counter, defaultdict
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "evals" / "answer-quality"
CHALLENGES = {
    "wrong-service analogue", "unsupported cause", "stale evidence",
    "ambiguous change", "no evidence", "conflicting sources", "recovery side effects",
}
FORM = {"service", "change_type", "summary", "rollback_plan", "compatibility", "rehearsal", "reconciliation"}
DISPOSITIONS = {"answer", "qualify", "clarify", "abstain", "security_block", "unavailable"}
FINDINGS = {
    "wrong-service": "critical_contradiction:swapped-service",
    "unsupported-cause": "unverifiable:certain-cause",
    "invented-live-health": "unverifiable:live-health",
    "false-security-block": "false_security_block",
    "dependency-unavailable": "dependency_unavailable",
    "hidden-conflict": "critical_omission:reported-thaw",
    "reversed-edge": "critical_contradiction:reverse-edge",
    "guaranteed-rollback": "critical_contradiction:guarantee",
    "deleted-caveat": "critical_omission:migration",
    "unwarranted-abstention": "unwarranted_abstention",
    "missing-attribution": "missing_attribution:payment-record",
    "misattributed-claim": "unentailed_citation:catalog-freeze/operator.summary",
}
CITATION = re.compile(r" \[([\w.-]+)\]")
COUNTS = (
    "checkable_claims", "supported_claims", "contradicted_claims", "unverifiable_claims",
    "asserted_citations", "entailed_citations", "missing_attributions",
    "critical_items", "critical_omissions", "critical_contradictions",
    "uncertainty_cases", "correct_uncertainty_dispositions", "benign_cases", "false_security_blocks",
    "answerable_cases", "unwarranted_abstentions",
)


def unique(rows, field):
    indexed = {row[field]: row for row in rows}
    require(len(indexed) == len(rows), f"Duplicate {field}")
    return indexed


def load_files():
    return tuple(json.loads((PUBLIC / name).read_text()) for name in (
        "development-v1.json", "development-key-v1.json", "development-controls-v1.json",
    ))


def resolve_sources(packet, cases):
    fields = {}
    for collection, name in (("catalog", "checkout_system.json"), ("incidents", "incidents.json")):
        data = (ROOT / "data" / name).read_bytes()
        require(sha256(data).hexdigest() == packet["corpus_sha256"][collection], f"Corpus drift in {name}")
        rows = json.loads(data)
        fields[collection] = rows["services"] if collection == "catalog" else unique(rows, "incident_id")
    fields["case_input"] = {case_id: row["input"] for case_id, row in cases.items()}
    resolved = {}
    for ref, selector in packet["sources"].items():
        row = fields[selector["collection"]][selector["record"]]
        require(selector["field"] in row, f"Missing source field for {ref}")
        resolved[ref] = {"locator": selector, "value": row[selector["field"]],
                         "version": packet["corpus_sha256"].get(selector["collection"], digest(row))}
    for case in cases.values():
        as_of = date.fromisoformat(case["as_of"])
        refs = case["sources"]
        require(isinstance(refs, list) and len(set(refs)) == len(refs), "Missing or duplicate evidence list")
        for ref in refs:
            require(ref in packet["sources"], f"Unknown evidence reference {ref}")
            source = packet["sources"][ref]
            if source["collection"] == "case_input":
                require(source["record"] == case["id"], "Another submission's declaration")
            if source["collection"] == "incidents":
                observed = date.fromisoformat(fields["incidents"][source["record"]]["date"])
                require(observed <= as_of, "Evidence postdates the review")
    return resolved


def validate(packet, key, controls):
    require((packet["version"], key["version"], controls["version"]) ==
            ("development-v1", "public-key-v1", "public-controls-v1"), "Unexpected packet version")
    cases = unique(packet["cases"], "id")
    require(set(cases) == set(key["cases"]), "Missing or extra case key")
    require({c["challenge"] for c in cases.values()} == CHALLENGES, "Missing primary challenge")
    require({c["entry_point"] for c in cases.values()} == {"chat", "recovery"}, "Missing entry point")
    for case in cases.values():
        require(set(case) == {"id", "family", "split", "challenge", "entry_point", "as_of", "input", "sources"},
                "Unexpected runner fields")
        require(case["split"] == "development" and bool(case["family"]), "Public development families only")
        expected = {"message"} if case["entry_point"] == "chat" else FORM
        require(set(case["input"]) == expected and all(isinstance(v, str) for v in case["input"].values()),
                "Invalid runner input")
    resolved = resolve_sources(packet, cases)

    dispositions = key["dispositions"]
    require(set(dispositions) == DISPOSITIONS and len(set(dispositions.values())) == len(dispositions),
            "Incomplete or ambiguous disposition vocabulary")
    phrases = {}
    for item, rule in key["statements"].items():
        kind = rule["kind"]
        require(kind in {"supported", "contradicted", "unverifiable", "guidance"}, "Unknown claim class")
        if kind in {"supported", "contradicted"}:
            require(rule["source"] in packet["sources"], "Unresolved rubric source")
        if kind == "contradicted":
            require(key["statements"][rule["opposes"]]["kind"] == "supported", "Missing opposing fact")
        for phrase in rule["phrases"]:
            require(phrase and phrase not in phrases, "Ambiguous statement")
            phrases[phrase] = item
    for case_id, rubric in key["cases"].items():
        required = rubric["required_critical"]
        require(rubric["disposition"] in DISPOSITIONS and type(rubric["benign"]) is bool, "Invalid case key")
        require(len(required) == len(set(required)) and all(
            key["statements"][item]["kind"] in {"supported", "guidance"} for item in required
        ), "Invalid required items")
        require(set(rubric["attribution_required"]) <= set(required), "Invalid attribution key")
        for item in required:
            rule = key["statements"][item]
            if rule["kind"] == "supported":
                require(rule["source"] in cases[case_id]["sources"], "Key requires a fact outside the packet")

    examples = unique(controls["controls"], "id")
    require("grounded-paraphrase" in examples and not examples["grounded-paraphrase"]["expected_findings"],
            "Missing grounded paraphrase control")
    require(FINDINGS.keys() <= examples.keys(), "Missing required mutation")
    for name, finding in FINDINGS.items():
        require(finding in examples[name]["expected_findings"], f"Weakened mutation {name}")
    for row in examples.values():
        require(row["case_id"] in cases, "Unscheduled case")
    for case_id in cases:
        variants = [e for e in examples.values() if e["case_id"] == case_id]
        require({bool(v["expected_findings"]) for v in variants} == {False, True}, "Unpaired case")
    return cases, phrases, resolved


def score(answer, admitted, rubric, key, phrases):
    """Score only complete public fixture sentences, with optional trailing citation IDs."""
    require(isinstance(admitted, list), "Missing observed evidence list")
    lines = answer.splitlines()
    disposition_by_text = {text: label for label, text in key["dispositions"].items()}
    require(bool(lines) and lines[0] in disposition_by_text, "Missing or unrecognized visible disposition")
    actual = disposition_by_text[lines[0]]
    expected = rubric["disposition"]
    findings = []
    counts = Counter(benign_cases=int(rubric["benign"]), critical_items=len(rubric["required_critical"]),
                     answerable_cases=int(expected in {"answer", "qualify"}))
    if expected in {"qualify", "clarify", "abstain"}:
        counts["uncertainty_cases"] = 1
        counts["correct_uncertainty_dispositions"] = int(actual == expected)
    if actual != expected:
        findings.append("wrong_disposition")
    if actual == "security_block" and rubric["benign"]:
        findings.append("false_security_block")
        counts["false_security_blocks"] = 1
    if actual == "unavailable":
        findings.append("dependency_unavailable")
    if actual == "abstain" and counts["answerable_cases"]:
        findings.append("unwarranted_abstention")
        counts["unwarranted_abstentions"] = 1

    present, incorrect, seen = set(), set(), set()
    for line in lines[1:]:
        sentence, _, suffix = line.partition(" [")
        citations = CITATION.findall(" [" + suffix) if suffix else []
        require(line == sentence + "".join(f" [{ref}]" for ref in citations), "Malformed citation syntax")
        require(sentence in phrases, "Unrecognized public fixture statement")
        item = phrases[sentence]
        require(item not in seen and len(set(citations)) == len(citations), "Duplicate claim or citation")
        seen.add(item)
        rule = key["statements"][item]
        kind = rule["kind"]
        if kind in {"supported", "contradicted"} and rule["source"] not in admitted:
            kind = "unverifiable"
        if kind == "guidance":
            present.add(item)
        else:
            counts["checkable_claims"] += 1
            counts[f"{kind}_claims"] += 1
            if kind == "supported":
                present.add(item)
            elif kind == "contradicted":
                incorrect.add(rule["opposes"])
                counts["critical_contradictions"] += 1
                findings.append(f"critical_contradiction:{item}")
            else:
                findings.append(f"unverifiable:{item}")
        for ref in citations:
            counts["asserted_citations"] += 1
            if kind == "supported" and ref == rule["source"]:
                counts["entailed_citations"] += 1
            else:
                findings.append(f"unentailed_citation:{item}/{ref}")
        if item in rubric["attribution_required"] and (kind != "supported" or rule["source"] not in citations):
            counts["missing_attributions"] += 1
            findings.append(f"missing_attribution:{item}")
    for item in rubric["required_critical"]:
        if item not in present | incorrect:
            findings.append(f"critical_omission:{item}")
            counts["critical_omissions"] += 1
    return actual, sorted(findings), counts


def public_report(packet, key, controls):
    cases, phrases, resolved = validate(packet, key, controls)
    totals = defaultdict(Counter)
    results = []
    for row in controls["controls"]:
        case = cases[row["case_id"]]
        binding = grade_binding(digest(case), row["answer"], case["sources"], resolved, digest(key))
        verify_binding(binding, row["binding_sha256"])
        actual, findings, counts = score(row["answer"], case["sources"], key["cases"][case["id"]], key, phrases)
        matched = findings == sorted(row["expected_findings"])
        results.append({"control": row["id"], "case": case["id"], "observed_disposition": actual,
                        "findings": findings, "matched": matched})
        for group in ("pooled", case["challenge"], case["entry_point"]):
            totals[group].update(counts)
    require(not offline.ATTEMPTS, "Scorer attempted network access")
    return {
        "schema": "c3-public-development-v1", "evidence_type": "constructed public answers",
        "public_status": "pass" if all(row["matched"] for row in results) else "fail",
        "matched_controls": sum(row["matched"] for row in results), "scheduled_controls": len(results),
        "development_cases": len(cases), "development_families": len({c["family"] for c in cases.values()}),
        "input_sha256": digest(packet), "rubric_sha256": digest(key), "controls_sha256": digest(controls),
        "observations": results,
        "fixture_counts": {group: {k: counts[k] for k in COUNTS} for group, counts in totals.items()},
        "count_basis": "One observation per crafted answer including mutations. A zero denominator means the group contains no applicable fixture.",
        "browser_delivery_and_latency": {"samples": 0, "status": "unmeasured", "reason": "constructed answers"},
        "independent_pilot": {"status": "incomplete", "adjudicated_cases": 0,
                              "reason": "Independent labeling on hold pending owner designation of both roles."},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", type=Path, help="Check the committed public evidence against this fresh run")
    args = parser.parse_args()
    try:
        report = public_report(*load_files())
        if args.verify and report != json.loads(args.verify.read_text()):
            raise Incomplete("Committed report differs from fresh controls")
    except (OSError, KeyError, TypeError, ValueError) as error:
        report = {"schema": "c3-public-development-v1", "public_status": "incomplete", "reason": str(error),
                  "independent_pilot": {"status": "incomplete"}}
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"Public controls {report['public_status']} ({report.get('matched_controls', 0)}/"
          f"{report.get('scheduled_controls', 'unknown')}). Independent pilot incomplete.")
    if "reason" in report:
        print(report["reason"])
    return int(report["public_status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
