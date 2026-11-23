"""Integrity checks shared by offline public controls and future browser collection."""
from hashlib import sha256
import json


class Incomplete(ValueError):
    """Required evidence cannot be matched to the submission being graded."""


def require(condition, message):
    if not condition:
        raise Incomplete(message)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check_family_splits(development, reserved):
    overlap = set(development) & set(reserved)
    require(not overlap, "Previously exposed family in reserved split")


def grade_binding(case_digest, answer, sources, known_sources, rubric_digest):
    require(isinstance(answer, str) and bool(answer.strip()), "Missing visible answer")
    require(isinstance(sources, list), "Missing evidence trace")
    require(len(sources) == len(set(sources)) and set(sources) <= known_sources.keys(),
            "Duplicate or unknown captured source")
    return {"case_sha256": case_digest, "rubric_sha256": rubric_digest,
            "answer_sha256": sha256(answer.encode()).hexdigest(),
            "evidence_sha256": digest({ref: known_sources[ref] for ref in sources})}


def bind_capture(submission, attempts, known_sources, rubric_digest):
    """Bind exactly one capture to an expected attempt. Return only opaque grading digests."""
    require(len(attempts) == 1, "Missing or duplicate capture")
    capture = attempts[0]
    for field in ("case_sha256", "attempt", "session", "event"):
        require(submission.get(field) and capture.get(field) == submission[field], f"Unmatched {field}")
    return grade_binding(submission["case_sha256"], capture.get("answer"), capture.get("sources"),
                         known_sources, rubric_digest)


def verify_binding(current, frozen):
    require(digest(current) == frozen, "Answer, evidence, case or rubric changed after grading")
