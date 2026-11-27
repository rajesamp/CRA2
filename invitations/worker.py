"""One bounded pass over pending local work. Restart-safe and safe to run twice."""


class Worker:
    def __init__(self, pilot):
        self.pilot = pilot
        self.retry_after = 0
        self.retry_delay = 1
        self.delivery_cursor = 0

    def tick(self):
        store = self.pilot.store
        with store.write() as (db, _):
            pending = list(
                db.execute(
                    "SELECT rowid,id FROM invites WHERE state IN ('queued','unknown') ORDER BY (rowid<=?),rowid LIMIT 100",
                    (self.delivery_cursor,),
                )
            )
            removals = list(db.execute("SELECT subject,invite FROM removals LIMIT 100"))
            grants = list(db.execute("SELECT invite FROM members WHERE state='provisioning' LIMIT 100"))
            db.execute(
                "CREATE TABLE IF NOT EXISTS report_progress(id INTEGER PRIMARY KEY,cursor INTEGER, sweep REAL)"
            )
            db.execute("INSERT OR IGNORE INTO report_progress VALUES(1,0,0)")
            cursor, sweep = db.execute("SELECT cursor,sweep FROM report_progress").fetchone()
        for rowid, ref in pending:
            self.pilot.dispatch(ref)
            self.delivery_cursor = rowid
        for subject, ref in removals:
            self.pilot.remove_grant(subject, ref)
        for (ref,) in grants:
            self.pilot.provision(ref)
        # Periodic replay repairs edited or lost Sheet rows using the same event IDs.
        now = store.clock()
        if now < self.retry_after:
            return
        replay = now >= sweep + 3600
        try:
            new = self.pilot.maintain(cursor=0 if replay else cursor)
        except TimeoutError:
            self.retry_after = now + self.retry_delay
            self.retry_delay = min(self.retry_delay * 2, 60)
            return
        self.retry_delay = 1
        with store.write() as (db, _):
            db.execute(
                "UPDATE report_progress SET cursor=?,sweep=? WHERE cursor=? AND sweep=?",
                (new, now if replay else sweep, cursor, sweep),
            )
