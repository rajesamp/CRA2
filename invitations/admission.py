"""Verified interest, owner review and moderation."""

import secrets

from .policy import WEEK, WINDOW, Decision, Evidence, Outcome, address, classify
from .store import budget, event


class Closed(ValueError):
    pass


class Busy(ValueError):
    pass


def require_owner(actor, owner):
    if actor != owner:
        raise PermissionError("Owner session required")


def is_banned(db, actor, email, now):
    return bool(
        db.execute(
            "SELECT 1 FROM bans WHERE (subject=? OR email=?) AND until>?", (actor, email, now)
        ).fetchone()
    )


def blockout(db, subject, email, now):
    db.execute("INSERT OR REPLACE INTO bans VALUES(?,?,?,0)", (subject, email, now + WEEK))
    db.execute(
        "UPDATE applications SET state='closed',updated=? WHERE subject=? AND state IN ('pending','approved','held')",
        (now, subject),
    )
    db.execute(
        """UPDATE invites SET state='revoked',payload=NULL WHERE (subject=? OR email=?)
                  AND state IN ('queued','sent','unknown')""",
        (subject, email),
    )
    pending = db.execute(
        "SELECT invite FROM members WHERE subject=? AND state='provisioning'", (subject,)
    ).fetchone()
    if pending:
        db.execute("UPDATE members SET state='revoked' WHERE subject=?", (subject,))
        db.execute("UPDATE invites SET state='revoked' WHERE id=?", (pending["invite"],))
        db.execute("INSERT OR REPLACE INTO removals VALUES(?,?)", (subject, pending["invite"]))
    event(db, now, email, "ban", "three_distinct_windows", source="moderation")


def abuse(db, store, actor, typed, now):
    """Anchor nonoverlapping windows on verified post-warning activity."""
    row = db.execute("SELECT * FROM warnings WHERE subject=?", (actor.subject,)).fetchone()
    if row is None:
        db.execute("INSERT INTO warnings VALUES(?,NULL,0,?)", (actor.subject, now))
        return False
    if row["start"] is None or now >= row["start"] + WINDOW:
        db.execute("DELETE FROM targets WHERE subject=?", (actor.subject,))
        db.execute(
            "UPDATE warnings SET start=?,struck=0,updated=? WHERE subject=?", (now, now, actor.subject)
        )
    elif row["struck"]:
        return True
    db.execute("INSERT OR IGNORE INTO targets VALUES(?,?)", (actor.subject, store.fingerprint(typed)))
    count = db.execute("SELECT count(*) FROM targets WHERE subject=?", (actor.subject,)).fetchone()[0]
    if count < 3:
        return False
    db.execute("UPDATE warnings SET struck=1 WHERE subject=?", (actor.subject,))
    db.execute("INSERT INTO strikes VALUES(?,?)", (actor.subject, now))
    recent = db.execute(
        "SELECT count(*) FROM strikes WHERE subject=? AND at>?", (actor.subject, now - WEEK)
    ).fetchone()[0]
    if recent >= 3:
        blockout(db, actor.subject, actor.email, now)
    return True


class Admission:
    def __init__(self, store, owner):
        self.store = store
        self.owner = owner

    def submit(self, actor, typed, submission):
        typed = address(typed)
        if not isinstance(submission, str) or not 0 < len(submission) <= 100:
            raise ValueError("Invalid request reference")
        with self.store.write() as (db, now):
            if db.execute("SELECT held FROM settings").fetchone()[0]:
                raise Closed("Intake is paused")
            if not budget(db, actor.subject, "intake", now, 150, WINDOW):
                return Decision(Outcome.HOLD, "intake_limit")
            seen = db.execute(
                "SELECT outcome,reason FROM seen WHERE subject=? AND id=?", (actor.subject, submission)
            ).fetchone()
            banned = is_banned(db, actor.subject, actor.email, now)
            if seen and banned:
                return Decision(Outcome.SPAM, "active_ban")
            if seen:
                return Decision(Outcome(seen[0]), seen[1])
            app = db.execute("SELECT * FROM applications WHERE email=?", (actor.email,)).fetchone()
            member = db.execute(
                "SELECT * FROM members WHERE (email=? OR subject=?) AND state!='revoked'",
                (actor.email, actor.subject),
            ).fetchone()
            invite = db.execute(
                """SELECT * FROM invites WHERE email=? AND (state IN ('queued','unknown')
                                OR (state='sent' AND expires>?))""",
                (actor.email, now),
            ).fetchone()
            matches = typed == actor.email
            reliable = not (
                (app and app["subject"] != actor.subject)
                or (invite and invite["subject"] and invite["subject"] != actor.subject)
                or (member and (member["subject"] != actor.subject or member["email"] != actor.email))
            )
            duplicate = bool(
                actor == self.owner
                or invite
                or member
                or (
                    app
                    and (
                        app["state"] in {"pending", "approved"}
                        or (app["state"] == "denied" and app["updated"] + WEEK > now)
                    )
                )
            )
            qualified = bool(
                not banned and reliable and not matches and abuse(db, self.store, actor, typed, now)
            )
            decision = classify(Evidence(banned, matches, qualified, duplicate, reliable))
            ref = app["ref"] if app else ""
            if decision.outcome == Outcome.VALID:
                if (
                    db.execute("SELECT count(*) FROM applications WHERE state='pending'").fetchone()[0]
                    >= 1500
                ):
                    raise Busy("Intake queue full")
                ref = secrets.token_urlsafe(16)
                db.execute(
                    "INSERT OR REPLACE INTO applications VALUES(?,?,'pending',?,?)",
                    (actor.email, actor.subject, now, ref),
                )
            db.execute(
                "INSERT INTO seen VALUES(?,?,?,?,?)",
                (actor.subject, submission, now, decision.outcome, decision.reason),
            )
            event(db, now, actor.email, decision.outcome, decision.reason, ref=ref)
            return decision

    def preview(self, actor):
        require_owner(actor, self.owner)
        with self.store.write() as (db, _):
            return [
                dict(r)
                for r in db.execute("""SELECT email,state,updated,ref FROM applications
                   WHERE state IN ('pending','approved') ORDER BY updated,ref""")
            ]

    def denied(self, actor):
        require_owner(actor, self.owner)
        with self.store.write() as (db, _):
            return [
                dict(r)
                for r in db.execute(
                    "SELECT email,ref FROM applications WHERE state='denied' ORDER BY updated"
                )
            ]

    def decide(self, actor, ref, action):
        require_owner(actor, self.owner)
        states = {
            "approve": ("pending", "approved"),
            "deny": ("pending", "denied"),
            "reopen": ("denied", "pending"),
        }
        before, after = states[action]
        with self.store.write() as (db, now):
            row = db.execute("SELECT * FROM applications WHERE ref=?", (ref,)).fetchone()
            if not row or row["state"] not in {before, after}:
                raise Closed("Refresh the request")
            if row["state"] == after:
                return
            if is_banned(db, row["subject"], row["email"], now):
                raise Closed("Request is unavailable")
            new_ref = secrets.token_urlsafe(16) if action == "reopen" else ref
            db.execute(
                "UPDATE applications SET state=?,updated=?,ref=? WHERE ref=?",
                (after, now, new_ref, ref),
            )
            event(db, now, row["email"], after, "owner_" + action, ref=ref)

    def appeal(self, actor):
        with self.store.write() as (db, now):
            changed = db.execute(
                "UPDATE bans SET appealed=1 WHERE subject=? AND until>? AND appealed=0",
                (actor.subject, now),
            ).rowcount
            if changed:
                event(db, now, actor.email, "appeal", "owner_review", source="moderation")

    def appeals(self, actor):
        require_owner(actor, self.owner)
        with self.store.write() as (db, now):
            return [
                dict(r)
                for r in db.execute(
                    "SELECT subject,email,until,appealed FROM bans WHERE until>?", (now,)
                )
            ]

    def lift(self, actor, subject):
        require_owner(actor, self.owner)
        with self.store.write() as (db, now):
            row = db.execute("SELECT email FROM bans WHERE subject=?", (subject,)).fetchone()
            if row:
                for table in ("bans", "strikes", "warnings", "targets"):
                    db.execute(f"DELETE FROM {table} WHERE subject=?", (subject,))
                event(db, now, row["email"], "lift", "owner_correction", source="moderation")
