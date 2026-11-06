"""Explicit Google Cloud feed import into a local, review-only staging file.

Use --input for an offline response or --fetch for the single official endpoint.
Nothing is promoted into CRA2's canonical corpus or retrieval index by this CLI.
"""

import argparse
from http.client import HTTPException
import json
import os
from pathlib import Path
import ssl
import stat
import tempfile
from time import monotonic
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from cra2.google_incidents import (
    FEED_URL, MAX_FEED_BYTES, GoogleIncidentError, stage_feed, validate_staging,
)
from cra2.public_evidence import load_public_evidence
from cra2.secrets import reject_credentials

MAX_STAGING_BYTES = 4 * 1024 * 1024
NETWORK_TIMEOUT_SECONDS = 10
READ_DEADLINE_SECONDS = 30
ERROR = "Google incident import failed; review the input, destination and source availability."
PROTECTED_NAMES = {
    "public_evidence.json", "incidents.json", "sample_incidents.json",
    "checkout_system.json", "team_settings.json", "rules.json", "manifest.json", "cases.json",
}


def _fail():
    raise GoogleIncidentError(ERROR) from None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _fail()


def fetch_feed():
    """Read one fixed public HTTPS endpoint; never forward credentials or redirects."""
    try:
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirect())
        request = Request(FEED_URL, headers={"Accept": "application/json",
            "Accept-Encoding": "identity", "User-Agent": "CRA2-public-evidence/1"})
        deadline = monotonic() + READ_DEADLINE_SECONDS
        with opener.open(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != FEED_URL:
                _fail()
            if response.headers.get_content_type() != "application/json":
                _fail()
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                _fail()
            declared = response.headers.get("Content-Length")
            if declared is not None:
                if (not declared.isascii() or not declared.isdigit() or len(declared) > 10
                        or int(declared) > MAX_FEED_BYTES):
                    _fail()
                declared = int(declared)
            parts, size = [], 0
            while True:
                if monotonic() >= deadline:
                    _fail()
                # HTTPResponse.read1 performs at most one underlying read, so
                # the total deadline is checked between bounded socket reads.
                block = response.read1(min(65536, MAX_FEED_BYTES + 1 - size))
                if monotonic() >= deadline or not isinstance(block, bytes):
                    _fail()
                if not block:
                    break
                size += len(block)
                if size > MAX_FEED_BYTES:
                    _fail()
                parts.append(block)
            if declared is not None and size != declared:
                _fail()
            return b"".join(parts)
    except (OSError, ValueError, HTTPError, URLError, HTTPException):
        _fail()


def _path(value, *, output=False):
    try:
        if not isinstance(value, (str, os.PathLike)):
            _fail()
        path = Path(os.path.abspath(value))
        if len(str(path)) > 4096 or any(unicodedata.category(c).startswith("C") for c in str(path)):
            _fail()
        reject_credentials(str(path))
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            _fail()
        if output and (path.suffix != ".json" or path.name.casefold() in PROTECTED_NAMES):
            _fail()
        return path
    except (OSError, ValueError):
        _fail()


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read(path, limit):
    """Capture a bounded regular file and its identity without following a symlink."""
    path = _path(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                _fail()
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        if len(raw) > limit or _identity(info) != _identity(after) or _identity(path.lstat()) != _identity(after):
            _fail()
        return raw, after
    except (OSError, ValueError):
        _fail()


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _fail()
        value[key] = item
    return value


def _previous(path):
    if not path.exists():
        return None, None
    raw, info = _read(path, MAX_STAGING_BYTES)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=lambda _value: _fail())
        return validate_staging(value), (raw, info)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        _fail()


def _unchanged(path, snapshot):
    _path(path, output=True)
    if snapshot is None:
        if path.exists():
            _fail()
        return
    raw, info = _read(path, MAX_STAGING_BYTES)
    if raw != snapshot[0] or _identity(info) != _identity(snapshot[1]):
        _fail()


def _publish(path, encoded, snapshot):
    """Publish under a cooperative lock; refuse changed or unrelated destinations."""
    lock_path = path.with_name("." + path.name + ".lock")
    temporary, lock_info = None, None
    try:
        _path(path, output=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        _path(path, output=True)
        lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                       | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(lock, "wb") as lock_file:
            lock_info = os.fstat(lock_file.fileno())
            _unchanged(path, snapshot)
            if snapshot is not None and encoded == snapshot[0]:
                return False
            descriptor, filename = tempfile.mkstemp(prefix=".cra2-google-stage-", suffix=".json", dir=path.parent)
            temporary = Path(filename)
            with os.fdopen(descriptor, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            _unchanged(path, snapshot)
            if snapshot is None:
                # Atomic no-clobber publication if another writer appeared.
                os.link(temporary, path)
            else:
                os.replace(temporary, path)
            return True
    except (OSError, ValueError):
        _fail()
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        if lock_info is not None:
            try:
                if _identity(lock_path.lstat()) == _identity(lock_info):
                    lock_path.unlink()
            except FileNotFoundError:
                pass


def import_incidents(*, output, input_path=None, fetch=False):
    """Validate everything before publishing; an existing valid stage is merged."""
    if type(fetch) is not bool or fetch == (input_path is not None):
        _fail()
    destination = _path(output, output=True)
    previous, snapshot = _previous(destination)
    public_records = load_public_evidence()
    raw = fetch_feed() if fetch else _read(_path(input_path), MAX_FEED_BYTES)[0]
    staged = stage_feed(raw, previous=previous, public_records=public_records)
    validate_staging(staged)
    encoded = (json.dumps(staged, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(encoded) > MAX_STAGING_BYTES:
        _fail()
    changed = _publish(destination, encoded, snapshot)
    records = staged["records"]
    return {"status": "staged" if changed else "unchanged", "source_url": FEED_URL,
            "records": len(records), "pending_review": len(records),
            "canonical_source_matches": sum(record["canonical_record_id"] is not None for record in records),
            "promoted_records": 0, "network_requests": int(fetch)}


def main(argv=None):
    class ProtectedParser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(2, "Choose exactly one of --fetch or --input, and supply a staging --output.\n")

    parser = ProtectedParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fetch", action="store_true", help="Fetch the fixed official HTTPS feed once")
    source.add_argument("--input", type=Path, help="Read a saved feed response without network access")
    parser.add_argument("--output", required=True, type=Path, help="Review-only JSON staging file; existing valid staging is merged")
    args = parser.parse_args(argv)
    try:
        result = import_incidents(output=args.output, input_path=args.input, fetch=args.fetch)
    except (OSError, ValueError, TypeError, RecursionError):
        parser.exit(1, ERROR + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
