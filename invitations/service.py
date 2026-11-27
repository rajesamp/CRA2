"""Owner-controlled invitation delivery and admission to a synthetic workspace."""

import hashlib
import hmac
import secrets

from .admission import Admission, Closed, is_banned, require_owner
from .fixtures import LocalServices
from .policy import DAY, WEEK, WINDOW, address
from .store import Store, budget, event


class Pilot:
    def __init__(self, directory, owner, **settings):
        self.store = Store(directory, owner, **settings)
        self.owner = owner
        self.admission = Admission(self.store, owner)
        self.local = LocalServices(self.store)

    def hold(self, actor, enabled):
        require_owner(actor, self.owner)
        if type(enabled) is not bool:
            raise ValueError("A boolean hold is required")
        with self.store.write() as (db, now):
            db.execute("UPDATE settings SET held=?", (enabled,))
            event(db, now, "", "hold", "paused" if enabled else "opened_locally", source="owner")

    def held(self):
        with self.store.write() as (db, _):
            return bool(db.execute("SELECT held FROM settings").fetchone()[0])

    def send(self, actor, recipient, *, request=None):
        require_owner(actor, self.owner)
        email = address(recipient)
        with self.store.write() as (db, now):
            if db.execute("SELECT held FROM settings").fetchone()[0] or email == self.owner.email:
                raise Closed("Sending is unavailable")
            app = db.execute("SELECT * FROM applications WHERE email=?", (email,)).fetchone()
            if request is not None and (not app or app["ref"] != request or app["state"] != "approved"):
                raise Closed("An approved request is required")
            if app and app["state"] in {"pending", "denied"}:
                raise Closed("Review or reopen the existing request first")
            subject = app["subject"] if app and app["state"] == "approved" else None
            if (
                is_banned(db, subject, email, now)
                or db.execute(
                    "SELECT 1 FROM members WHERE email=? AND state!='revoked'", (email,)
                ).fetchone()
            ):
                raise Closed("Recipient is unavailable")
            previous = db.execute(
                "SELECT * FROM invites WHERE email=? ORDER BY created DESC,rowid DESC LIMIT 1", (email,)
            ).fetchone()
            if previous:
                if previous["state"] in {"queued", "unknown"} or (
                    previous["state"] == "sent" and now < previous["expires"]
                ):
                    return previous["id"]
                receipt = self.local.receipt(previous["id"])
                last = previous["sent"] if previous["sent"] is not None else receipt
                if now < (last if last is not None else previous["created"]) + DAY:
                    raise Closed("Replacement cooldown is active")
                db.execute(
                    "UPDATE invites SET state='expired',payload=NULL WHERE id=? AND state='sent'",
                    (previous["id"],),
                )
            if not budget(db, "owner", "mail", now, 100, DAY):
                raise Closed("Daily pilot mail budget reached")
            code = secrets.token_urlsafe(24)
            ref = secrets.token_urlsafe(18)
            source = "interest" if request is not None else "owner-direct"
            db.execute(
                """INSERT INTO invites(id,email,subject,state,created,digest,payload,source)
                          VALUES(?,?,?,'queued',?,?,?,?)""",
                (
                    ref,
                    email,
                    subject,
                    now,
                    hashlib.sha256(code.encode()).hexdigest(),
                    self.store.cipher.encrypt(code.encode()),
                    source,
                ),
            )
            event(db, now, email, "queued", "owner_send", source=source, ref=ref)
            return ref

    def dispatch(self, ref):
        # The two local databases give the fixture an independent durable receipt.
        # Serialize the final hold check and side effect with pause/revoke operations.
        with self.store.write() as (db, now):
            row = db.execute("SELECT * FROM invites WHERE id=?", (ref,)).fetchone()
            if not row or row["state"] not in {"queued", "unknown"}:
                return
            accepted = self.local.receipt(ref)
            if accepted is None:
                if now >= row["created"] + 30 * DAY:
                    db.execute("UPDATE invites SET state='expired',payload=NULL WHERE id=?", (ref,))
                    return
                if (
                    row["state"] == "unknown"
                    or db.execute("SELECT held FROM settings").fetchone()[0]
                    or is_banned(db, row["subject"], row["email"], now)
                ):
                    return
                try:
                    accepted = self.local.accept(ref, row["payload"])
                except TimeoutError:
                    db.execute("UPDATE invites SET state='unknown',payload=NULL WHERE id=?", (ref,))
                    event(
                        db,
                        now,
                        row["email"],
                        "unknown",
                        "reconcile_delivery",
                        source=row["source"],
                        ref=ref,
                    )
                    return
            expires = accepted + WINDOW
            state = "sent" if self.store.clock() < expires else "expired"
            db.execute(
                "UPDATE invites SET state=?,sent=?,expires=?,payload=NULL WHERE id=?",
                (state, accepted, expires, ref),
            )
            event(db, now, row["email"], state, "original_receipt", source=row["source"], ref=ref)

    def invitation(self, actor):
        with self.store.write() as (db, now):
            row = db.execute(
                """SELECT id,state,expires FROM invites WHERE email=? AND (subject IS NULL OR subject=?)
                                ORDER BY created DESC,rowid DESC LIMIT 1""",
                (actor.email, actor.subject),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            if result["state"] == "sent" and now >= result["expires"]:
                result["state"] = "expired"
            return result

    def redeem(self, actor, code):
        if not isinstance(code, str) or not 1 <= len(code) <= 128:
            return False
        digest = hashlib.sha256(code.encode()).hexdigest()
        with self.store.write() as (db, now):
            if db.execute("SELECT held FROM settings").fetchone()[0] or is_banned(
                db, actor.subject, actor.email, now
            ):
                return False
            if not budget(db, actor.subject, "redeem", now, 12, WINDOW):
                return False
            row = db.execute(
                "SELECT * FROM invites WHERE email=? ORDER BY created DESC,rowid DESC LIMIT 1",
                (actor.email,),
            ).fetchone()
            if (
                not row
                or row["subject"] not in {None, actor.subject}
                or not budget(db, row["id"], "code", now, 12, WINDOW)
                or not hmac.compare_digest(row["digest"], digest)
            ):
                return False
            if row["state"] == "redeemed":
                return bool(
                    db.execute(
                        "SELECT 1 FROM members WHERE subject=? AND invite=? AND state!='revoked'",
                        (actor.subject, row["id"]),
                    ).fetchone()
                )
            if row["state"] != "sent" or not row["sent"] <= now < row["expires"]:
                return False
            other = db.execute(
                "SELECT * FROM members WHERE email=? OR subject=?", (actor.email, actor.subject)
            ).fetchall()
            if any(
                r["state"] != "revoked" or r["subject"] != actor.subject or r["email"] != actor.email
                for r in other
            ):
                return False
            db.execute(
                "UPDATE invites SET state='redeemed',subject=? WHERE id=?", (actor.subject, row["id"])
            )
            db.execute(
                "INSERT OR REPLACE INTO members VALUES(?,?,?,'provisioning')",
                (actor.subject, actor.email, row["id"]),
            )
            db.execute(
                "UPDATE applications SET state='closed',updated=? WHERE email=?", (now, actor.email)
            )
            event(
                db,
                now,
                actor.email,
                "redeemed",
                "matched_recipient",
                source=row["source"],
                ref=row["id"],
            )
            return True

    def provision(self, ref):
        with self.store.write() as (db, now):
            row = db.execute(
                "SELECT * FROM members WHERE invite=? AND state='provisioning'", (ref,)
            ).fetchone()
            if (
                not row
                or db.execute("SELECT held FROM settings").fetchone()[0]
                or is_banned(db, row["subject"], row["email"], now)
            ):
                return
            self.local.grant(row["subject"], ref)
            db.execute("UPDATE members SET state='active' WHERE invite=?", (ref,))
            event(db, now, row["email"], "active", "local_grant", source="membership", ref=ref)

    def access(self, actor):
        if actor == self.owner:
            return "owner"
        with self.store.write() as (db, _):
            row = db.execute(
                "SELECT * FROM members WHERE email=? AND subject=?", (actor.email, actor.subject)
            ).fetchone()
            if row and row["state"] == "active" and self.local.granted(actor.subject, row["invite"]):
                return "user"
            return None

    def revoke(self, actor, email):
        require_owner(actor, self.owner)
        email = address(email)
        with self.store.write() as (db, now):
            db.execute(
                "UPDATE invites SET state='revoked',payload=NULL WHERE email=? AND state IN ('queued','unknown','sent','redeemed')",
                (email,),
            )
            db.execute("UPDATE applications SET state='closed',updated=? WHERE email=?", (now, email))
            member = db.execute("SELECT subject,invite FROM members WHERE email=?", (email,)).fetchone()
            if member:
                db.execute("UPDATE members SET state='revoked' WHERE email=?", (email,))
                db.execute("INSERT OR REPLACE INTO removals VALUES(?,?)", tuple(member))
            event(db, now, email, "revoked", "owner_revoke", source="owner")
        if member:
            self.remove_grant(*member)

    def remove_grant(self, subject, ref):
        with self.store.write() as (db, _):
            # Version the removal itself. A retry cannot delete a later grant.
            if self.local.granted(subject, ref):
                self.local.revoke(subject)
            db.execute("DELETE FROM removals WHERE subject=? AND invite=?", (subject, ref))

    def maintain(self, *, cursor=0, batch=100):
        if type(batch) is not int or not 1 <= batch <= 250:
            raise ValueError("Invalid report batch")
        with self.store.write() as (db, now):
            cutoff = now - 30 * DAY
            db.execute(
                "UPDATE invites SET state='expired',payload=NULL WHERE state='sent' AND expires<=?",
                (now,),
            )
            db.execute(
                "DELETE FROM targets WHERE subject IN (SELECT subject FROM warnings WHERE start+?<=?)",
                (WINDOW, now),
            )
            db.execute("DELETE FROM warnings WHERE updated<?", (now - WEEK,))
            db.execute("DELETE FROM strikes WHERE at<=?", (now - WEEK,))
            db.execute("DELETE FROM bans WHERE until<=?", (now,))
            db.execute("DELETE FROM seen WHERE at<?", (now - DAY,))
            db.execute("DELETE FROM attempts WHERE start<?", (now - DAY,))
            db.execute(
                "DELETE FROM applications WHERE state IN ('closed','denied') AND updated<?", (cutoff,)
            )
            db.execute(
                """DELETE FROM members WHERE state='revoked' AND invite IN
                          (SELECT id FROM invites WHERE created<?)""",
                (cutoff,),
            )
            db.execute(
                """DELETE FROM invites WHERE state IN ('expired','revoked','redeemed') AND created<?
                          AND NOT EXISTS(SELECT 1 FROM members WHERE members.invite=invites.id)""",
                (cutoff,),
            )
            db.execute("DELETE FROM events WHERE at<?", (cutoff,))
            rows = list(
                db.execute("SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?", (cursor, batch))
            )
        self.local.expire(now, cutoff)
        self.local.project(rows)
        return rows[-1]["id"] if rows else cursor
