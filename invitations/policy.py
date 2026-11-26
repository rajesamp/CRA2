"""Typed decisions and abstention, following the Laya System 1 contract.

Reference: https://github.com/NandhaKishorM/laya/tree/073afac82616383088943b95ab4412b9324a9449
The evidence here is verified account behavior. No prompt, model or network call.
"""

from dataclasses import dataclass
from enum import StrEnum
import re

VERSION = "invitation-system1/1"
WINDOW = 600
DAY = 86400
WEEK = 7 * DAY


class Outcome(StrEnum):
    VALID = "valid"
    SPAM = "spam"
    HOLD = "hold"
    DUPLICATE = "duplicate"
    CORRECT = "correct"


@dataclass(frozen=True)
class Evidence:
    banned: bool
    matches: bool
    abuse_window: bool
    duplicate: bool
    reliable: bool


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str
    version: str = VERSION


def classify(facts: Evidence) -> Decision:
    if any(type(v) is not bool for v in vars(facts).values()):
        return Decision(Outcome.HOLD, "incomplete_evidence")
    if facts.banned:
        return Decision(Outcome.SPAM, "active_ban")
    if not facts.reliable:
        return Decision(Outcome.HOLD, "unresolved_identity")
    if facts.abuse_window:
        return Decision(Outcome.SPAM, "repeated_third_party")
    if not facts.matches:
        return Decision(Outcome.CORRECT, "self_request_only")
    if facts.duplicate:
        return Decision(Outcome.DUPLICATE, "already_recorded")
    return Decision(Outcome.VALID, "verified_self")


def address(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid email address")
    local, at, domain = value.strip().rpartition("@")
    labels = domain.split(".")
    if (
        not at
        or len(local) > 64
        or len(local) + len(domain) > 253
        or not re.fullmatch(r"[A-Za-z0-9_+.%'-]+", local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or len(labels) < 2
        or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in labels
        )
    ):
        raise ValueError("Enter a valid email address")
    return f"{local}@{domain.lower()}"


@dataclass(frozen=True)
class Principal:
    """Construct only after authentication at the admission boundary."""

    subject: str
    email: str

    def __post_init__(self):
        if not isinstance(self.subject, str) or not 0 < len(self.subject) <= 255:
            raise ValueError("Verified subject required")
        object.__setattr__(self, "email", address(self.email))
