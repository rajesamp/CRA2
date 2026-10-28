"""Local semantic abuse screening; never learn from private runtime questions."""

import json
import hashlib
import hmac
import math
import secrets
import threading
import time
import re
from pathlib import Path

import numpy as np

from week1.responses import guard
from cra2.secrets import reject_credentials
from week1.retrieval import _default_encoder, _embed
from week1.routing import active_request
from week2.owner_audit import OwnerAuditStore
from week2.help import admin_navigation

EXAMPLES = Path(__file__).with_name("abuse_examples.json")
MIN_SIMILARITY = 0.60
MIN_MARGIN = 0.035  # Chosen on validation, before examining held-out test rows.
COOLDOWN_SECONDS = 15


def prohibited_request(question):
    """Independent contract check for explicit actions on protected resources.

    Teaching/definition requests are not execution requests. The semantic model
    still screens them; this check is not a claim of general injection detection.
    """
    for clause in re.split(r"[.;!?\n,]|\b(?:and|then)\b", active_request(question)):
        text = clause.strip()
        text = re.sub(r"^(?:please\s+|(?:can|could|will|would)\s+you\s+|i (?:want|need) you to\s+)", "", text)
        if re.match(r"(?:explain|describe|define)\b|tell me about\b|(?:show|give)(?: me)? (?:an? |some )?(?:examples?|explanation|definition|format|overview|guidance)\b", text):
            continue
        if (re.match(r"(?:print|reveal|fetch|return|show|send|export|dump|read|give|display|open|tell)\b", text)
                and re.search(r"\b(?:credentials?|passwords?|secrets?|api[ _-]?(?:keys?|tokens?|credentials?)|provider token|system (?:prompt|message)|hidden (?:prompt|instructions)|owner.{0,50}(?:audit|logs?|records?|questions?|data)|other (?:users?|people).{0,40}(?:data|questions|history)|dotenv|environment variables)\b", text)):
            return True
        if (re.match(r"(?:ignore|disregard|forget|override|bypass|disable|turn off)\b", text)
                and re.search(r"\b(?:instructions?|rules|guardrails|security|logging|audit|authentication|tool contracts)\b", text)):
            return True
    return False


def examples():
    raw = EXAMPLES.read_text(encoding="utf-8")
    if len(raw) > 100_000:
        raise ValueError("Invalid classifier examples")
    data = json.loads(raw)
    rows = data["examples"]
    if data["version"] != 1 or not 10 <= len(rows) <= 200:
        raise ValueError("Invalid classifier examples")
    identities = set()
    for row in rows:
        if (set(row) != {"id", "split", "label", "text"}
                or row["id"] in identities or row["split"] not in {"train", "validation", "test"}
                or row["label"] not in {"adversarial", "benign"}
                or not isinstance(row["text"], str) or not 1 <= len(row["text"]) <= 4000):
            raise ValueError("Invalid classifier examples")
        identities.add(row["id"])
    guard(rows)
    return rows


class AbuseClassifier:
    """Frozen BGE features + training-only nearest-prototype classifier.

    Similarity/margin is not calibrated confidence or proof of a user's intent.
    Its empirical limits are measured on separate synthetic validation/test rows.
    """

    def __init__(self, *, encoder=None):
        self.encoder = encoder
        self.rows = examples()
        self.vectors = None

    def scores(self, question):
        guard(question)
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 4000:
            raise ValueError("Invalid classifier input")
        if self.vectors is None:
            self.encoder = self.encoder or _default_encoder()
            train = [row for row in self.rows if row["split"] == "train"]
            self.labels = np.array([row["label"] == "adversarial" for row in train])
            if not self.labels.any() or self.labels.all():
                raise ValueError("Missing classifier class")
            self.vectors = np.stack(_embed(self.encoder, "passage_embed", [row["text"] for row in train]))
        query = _embed(self.encoder, "query_embed", question.strip())[0]
        scores = self.vectors @ query
        attack = float(scores[self.labels].max())
        benign = float(scores[~self.labels].max())
        return {"attack_similarity": attack, "benign_similarity": benign, "margin": attack - benign}

    def classify(self, question):
        scores = self.scores(question)
        blocked = scores["attack_similarity"] >= MIN_SIMILARITY and scores["margin"] >= MIN_MARGIN
        return {"classification": "suspected_adversarial" if blocked else "benign",
                "severity": "M3" if blocked else "M0", "action": "BLOCK" if blocked else "ALLOW",
                "reason": "prohibited_action_similarity" if blocked else "no_adversarial_match",
                "classifier_used": True,
                **scores}


class AbuseGate:
    """Server-owned client cooldowns. No browser state can clear or choose them."""

    def __init__(self, *, store=None, classifier=None, clock=time.monotonic, additional_credentials=()):
        self.store = store if store is not None else OwnerAuditStore()
        self.classifier = classifier if classifier is not None else AbuseClassifier()
        self.clock = clock
        self.additional_credentials = tuple(additional_credentials)
        self.secret = secrets.token_bytes(32)
        self.bans = {}
        self.lock = threading.RLock()

    def _key(self, client):
        if not isinstance(client, str) or not client or len(client) > 200:
            raise ValueError("Missing trusted client identity")
        return hmac.new(self.secret, client.encode(), hashlib.sha256).hexdigest()

    def remaining(self, client):
        with self.lock:
            until, reason = self.bans.get(self._key(client), (0, ""))
            seconds = max(0, math.ceil(until - self.clock()))
            return seconds, reason if seconds else ""

    def pause(self, client, reason="unavailable"):
        with self.lock:
            key = self._key(client)
            # Rejected retries do not extend the original timeout.
            if self.bans.get(key, (0,))[0] <= self.clock():
                if len(self.bans) >= 5000:
                    self.bans = {key: value for key, value in self.bans.items() if value[0] > self.clock()}
                if len(self.bans) >= 5000:
                    raise ValueError("Cooldown capacity unavailable")
                self.bans[key] = (self.clock() + COOLDOWN_SECONDS, reason)
            return {"blocked": True, "reason": self.bans[key][1]}

    def admit(self, question, client):
        with self.lock:
            if self.remaining(client)[0]:
                return {"blocked": True, "reason": self.remaining(client)[1]}
            try:
                self.store.ensure()
                try:
                    guard(question)
                    reject_credentials(question, additional=self.additional_credentials)
                except ValueError:
                    self.store.append("Input withheld: configured credential", self._key(client), "sensitive_input",
                        {"classification": "sensitive_input", "severity": "M3", "action": "BLOCK"})
                    return self.pause(client, "sensitive")
                if not isinstance(question, str) or not 1 <= len(question.strip()) <= 4000:
                    return {"blocked": False, "verdict": {"classification": "invalid_input", "severity": "M0", "action": "ALLOW"}}
                if prohibited_request(question):
                    verdict = {"classification": "suspected_adversarial", "severity": "M3", "action": "BLOCK",
                        "reason": "protected_action_contract", "classifier_used": False,
                        "attack_similarity": 0., "benign_similarity": 0., "margin": 0.}
                elif admin_navigation(question):
                    # Public demo navigation is in-contract. Whole-question
                    # matching prevents an appended instruction bypass.
                    verdict = {"classification": "benign", "severity": "M0", "action": "ALLOW",
                        "reason": "app_navigation_contract", "classifier_used": False,
                        "attack_similarity": 0., "benign_similarity": 0., "margin": 0.}
                else:
                    verdict = self.classifier.classify(question)
                guard(verdict)
                if (not isinstance(verdict, dict) or verdict.get("action") not in {"ALLOW", "BLOCK"}
                        or verdict.get("classification") not in {"benign", "suspected_adversarial"}
                        or verdict.get("severity") not in {"M0", "M3"}
                        or (verdict["action"] == "BLOCK") != (verdict["classification"] == "suspected_adversarial")
                        or any(not isinstance(verdict.get(key), (int, float)) or not math.isfinite(verdict[key])
                               for key in ("attack_similarity", "benign_similarity", "margin"))):
                    raise ValueError("Invalid classifier verdict")
                if verdict["action"] == "BLOCK":
                    self.store.append(question, self._key(client), "suspected_adversarial", verdict)
                    return self.pause(client, "adversarial")
                return {"blocked": False, "verdict": verdict}
            except Exception:
                # No exception body, question or owner metadata crosses this boundary.
                return self.pause(client, "unavailable")

    def record_out_of_scope(self, question, client, verdict):
        try:
            self.store.append(question, self._key(client), "out_of_scope", verdict)
        except Exception:
            self.pause(client, "unavailable")
            return False
        return True
