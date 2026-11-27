"""Run the isolated pilot or inspect its synthetic mailbox from the local shell."""

import argparse
import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from .identity import ACCOUNTS, Login, OWNER
from .service import Pilot
from .web import create_app
from .worker import Worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="Private directory for pilot data")
    cmds = parser.add_subparsers(dest="command", required=True)
    serve = cmds.add_parser("serve")
    serve.add_argument("--port", type=int, default=8098)
    for cmd in ("signin-key", "mailbox"):
        cmds.add_parser(cmd).add_argument("email", choices=[p.email for p in ACCOUNTS])
    args = parser.parse_args()
    pilot = Pilot(args.state, OWNER)
    if args.command != "serve":
        actor = next(p for p in ACCOUNTS if p.email == args.email)
        if args.command == "signin-key":
            print(Login(pilot.store).key(actor))
        else:
            row = pilot.invitation(actor)
            if not row or row["state"] != "sent":
                parser.exit(1, "No current synthetic invitation.\n")
            print("Local invitation. Redeem within ten minutes of sending.")
            print("Deadline (UTC):", datetime.fromtimestamp(row["expires"], timezone.utc).isoformat())
            print("Code:", pilot.local.read_code(row["id"]))
        return
    app = create_app(args.state, pilot=pilot)
    worker = Worker(pilot)

    @asynccontextmanager
    async def lifespan(_):
        async def run():
            while True:
                try:
                    await asyncio.to_thread(worker.tick)
                except (sqlite3.OperationalError, TimeoutError):
                    logging.getLogger(__name__).warning(
                        "Invitation worker deferred a local service operation"
                    )
                await asyncio.sleep(1)

        task = asyncio.create_task(run())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
