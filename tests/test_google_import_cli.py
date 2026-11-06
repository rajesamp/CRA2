"""Explicit fetch and review-only atomic staging; all network responses are fake."""

from copy import deepcopy
from email.message import Message
from http.client import BadStatusLine, IncompleteRead
import io
import json
import os
from secrets import token_hex
import ssl
from urllib.error import URLError

import pytest

from cra2 import import_google_incidents as cli
from cra2.google_incidents import GoogleIncidentError


def incident(identifier="FixtureA"):
    update = {"created": "2026-01-01T02:05:00Z", "modified": "2026-01-01T02:10:00Z",
              "when": "2026-01-01T02:00:00Z", "text": "Synthetic fixture: replication capacity recovered after a controlled restart.",
              "status": "AVAILABLE", "affected_locations": []}
    return {"id": identifier, "uri": "incidents/" + identifier,
            "begin": "2026-01-01T01:00:00Z", "created": "2026-01-01T01:05:00Z",
            "modified": "2026-01-01T02:10:00Z", "end": "2026-01-01T02:00:00Z",
            "external_desc": "Synthetic database disruption", "severity": "low",
            "status_impact": "SERVICE_DISRUPTION", "affected_products": [{"id": "sql", "title": "Cloud SQL"}],
            "currently_affected_locations": [], "previously_affected_locations": [],
            "updates": [update], "most_recent_update": deepcopy(update)}


def feed_bytes(records=None):
    return json.dumps([incident()] if records is None else records).encode()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(cli, "load_public_evidence", lambda: [])
    monkeypatch.setattr(cli, "build_opener", lambda *_a: pytest.fail("Unexpected network access"))


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "response.json"
    path.write_bytes(feed_bytes())
    return path


class Response(io.BytesIO):
    def __init__(self, body=b"[]", *, status=200, url=cli.FEED_URL, headers=None):
        super().__init__(body)
        self.status, self.url = status, url
        self.headers = Message()
        for key, value in (headers or {"Content-Type": "application/json"}).items():
            self.headers[key] = value

    def geturl(self):
        return self.url


def transport(monkeypatch, response):
    calls = []

    class Opener:
        def open(self, request, *, timeout):
            calls.append((request, timeout))
            return response

    def build(*handlers):
        assert handlers[0].proxies == {}
        assert handlers[1]._context.verify_mode == ssl.CERT_REQUIRED
        assert handlers[1]._context.check_hostname is True
        assert isinstance(handlers[2], cli._NoRedirect)
        return Opener()

    monkeypatch.setattr(cli, "build_opener", build)
    return calls


def test_offline_import_creates_private_stage_without_touching_input(source, tmp_path, capsys):
    original = source.read_bytes()
    output = tmp_path / "new" / "candidates.json"
    assert cli.main(["--input", str(source), "--output", str(output)]) is None
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "staged", "source_url": cli.FEED_URL, "records": 1,
                      "pending_review": 1, "canonical_source_matches": 0, "promoted_records": 0, "network_requests": 0}
    staged = json.loads(output.read_text())
    assert staged["records"][0]["review_status"] == "pending_review"
    assert staged["records"][0]["prospective_cra2_risk"] is None
    assert source.read_bytes() == original
    assert output.stat().st_mode & 0o777 == 0o600
    assert sorted(p.name for p in output.parent.iterdir()) == ["candidates.json"]


def test_reimport_is_byte_and_inode_idempotent_and_preserves_absent_records(source, tmp_path):
    output = tmp_path / "candidates.json"
    cli.import_incidents(input_path=source, output=output)
    before = output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns
    result = cli.import_incidents(input_path=source, output=output)
    assert result["status"] == "unchanged"
    assert (output.read_bytes(), output.stat().st_ino, output.stat().st_mtime_ns) == before
    source.write_bytes(feed_bytes([]))
    result = cli.import_incidents(input_path=source, output=output)
    assert result["status"] == "unchanged" and result["records"] == 1


def test_curated_source_match_is_reported_without_promotion(source, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_public_evidence", lambda: [
        {"id": "public-reviewed-fixture", "source_url": "https://status.cloud.google.com/incidents/FixtureA"}])
    output = tmp_path / "candidates.json"
    result = cli.import_incidents(input_path=source, output=output)
    assert result["canonical_source_matches"] == 1 and result["promoted_records"] == 0


@pytest.mark.parametrize("raw", [b"not JSON", b"[]", b'{"schema_version":1,"schema_version":1}', b'{"a":NaN}', b'\xff'])
def test_unrecognized_existing_output_is_preserved(source, tmp_path, raw):
    output = tmp_path / "candidates.json"
    output.write_bytes(raw)
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert output.read_bytes() == raw


@pytest.mark.parametrize("name", sorted(cli.PROTECTED_NAMES) + ["Public_evidence.json", "index.sqlite3"])
def test_canonical_and_index_destinations_are_rejected_before_fetch(tmp_path, monkeypatch, name):
    monkeypatch.setattr(cli, "fetch_feed", lambda: pytest.fail("Invalid destination must precede fetch"))
    output = tmp_path / name
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(output=output, fetch=True)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["input", "output", "parent", "broken_output"])
def test_symlinks_are_rejected_without_modifying_targets(source, tmp_path, kind):
    output = tmp_path / "candidates.json"
    target = tmp_path / "target.json"
    target.write_text("private target")
    if kind == "input":
        alias = tmp_path / "input-alias.json"
        alias.symlink_to(source)
        source = alias
    elif kind == "output":
        output.symlink_to(target)
    elif kind == "broken_output":
        output.symlink_to(tmp_path / "missing.json")
    else:
        alias = tmp_path / "parent-alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        output = alias / "candidates.json"
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert target.read_text() == "private target"


def test_nonregular_input_is_rejected_without_blocking(tmp_path):
    source = tmp_path / "feed.fifo"
    os.mkfifo(source)
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=tmp_path / "stage.json")


def test_bad_or_oversized_input_never_creates_destination(source, tmp_path, monkeypatch):
    output = tmp_path / "new" / "candidates.json"
    source.write_bytes(b"PRIVATE INVALID INPUT")
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert not output.parent.exists()
    monkeypatch.setattr(cli, "MAX_FEED_BYTES", 3)
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert not output.exists()


@pytest.mark.parametrize("existing", [False, True])
def test_concurrent_destination_change_is_left_untouched(source, tmp_path, monkeypatch, existing):
    output = tmp_path / "candidates.json"
    if existing:
        cli.import_incidents(input_path=source, output=output)
    original = cli.stage_feed

    def concurrent(raw, **kwargs):
        output.write_text("concurrent writer")
        return original(raw, **kwargs)

    monkeypatch.setattr(cli, "stage_feed", concurrent)
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert output.read_text() == "concurrent writer"
    assert not output.with_name("." + output.name + ".lock").exists()


def test_new_destination_publication_does_not_clobber_last_moment_writer(source, tmp_path, monkeypatch):
    output = tmp_path / "candidates.json"
    original = os.link

    def concurrent_link(src, dst):
        output.write_text("late writer")
        return original(src, dst)

    monkeypatch.setattr(cli.os, "link", concurrent_link)
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert output.read_text() == "late writer"


def test_existing_lock_is_not_removed_or_bypassed(source, tmp_path):
    output = tmp_path / "candidates.json"
    lock = output.with_name("." + output.name + ".lock")
    lock.write_text("another writer")
    with pytest.raises(GoogleIncidentError):
        cli.import_incidents(input_path=source, output=output)
    assert lock.read_text() == "another writer" and not output.exists()


def test_fetch_only_requests_fixed_endpoint_and_counts_one_request(tmp_path, monkeypatch):
    response = Response(feed_bytes(), headers={"Content-Type": "application/json; charset=utf-8",
                                             "Content-Length": str(len(feed_bytes()))})
    calls = transport(monkeypatch, response)
    result = cli.import_incidents(output=tmp_path / "stage.json", fetch=True)
    request, timeout = calls[0]
    assert len(calls) == 1 and request.full_url == cli.FEED_URL
    assert request.data is None and request.get_header("Authorization") is None
    assert timeout == cli.NETWORK_TIMEOUT_SECONDS and response.closed
    assert result["network_requests"] == 1 and result["promoted_records"] == 0


@pytest.mark.parametrize("options", [
    {"status": 302}, {"status": 500}, {"url": "https://untrusted.example/"},
    {"headers": {"Content-Type": "text/html"}},
    {"headers": {"Content-Type": "application/json", "Content-Encoding": "gzip"}},
    {"headers": {"Content-Type": "application/json", "Content-Length": "99999999999"}},
    {"headers": {"Content-Type": "application/json", "Content-Length": "-1"}},
    {"headers": {"Content-Type": "application/json", "Content-Length": "100"}},
])
def test_fetch_rejects_redirect_or_malformed_response(monkeypatch, options):
    response = Response(**options)
    transport(monkeypatch, response)
    with pytest.raises(GoogleIncidentError):
        cli.fetch_feed()
    assert response.closed


def test_redirect_handler_never_follows_location():
    with pytest.raises(GoogleIncidentError):
        cli._NoRedirect().redirect_request(None, None, 302, "", {}, "https://untrusted.example/")


def test_fetch_bounds_bytes_even_without_length_and_checks_deadline(monkeypatch):
    monkeypatch.setattr(cli, "MAX_FEED_BYTES", 2)
    response = Response(b"[ ]")
    transport(monkeypatch, response)
    with pytest.raises(GoogleIncidentError):
        cli.fetch_feed()
    response = Response()
    transport(monkeypatch, response)
    clock = iter([0, cli.READ_DEADLINE_SECONDS + 1])
    monkeypatch.setattr(cli, "monotonic", lambda: next(clock))
    with pytest.raises(GoogleIncidentError):
        cli.fetch_feed()


def test_deadline_is_rechecked_after_final_eof_read(monkeypatch):
    clock = [0]

    class SlowEOF(Response):
        def read1(self, _size):
            clock[0] = cli.READ_DEADLINE_SECONDS + 1
            return b""

    response = SlowEOF()
    transport(monkeypatch, response)
    monkeypatch.setattr(cli, "monotonic", lambda: clock[0])
    with pytest.raises(GoogleIncidentError):
        cli.fetch_feed()
    assert response.closed


def test_network_errors_are_protected_and_do_not_write(tmp_path, monkeypatch, capsys):
    private = token_hex(24)

    class Unavailable:
        def open(self, *args, **kwargs):
            raise URLError(private)

    monkeypatch.setattr(cli, "build_opener", lambda *_handlers: Unavailable())
    output = tmp_path / "stage.json"
    with pytest.raises(SystemExit) as caught:
        cli.main(["--fetch", "--output", str(output)])
    assert caught.value.code == 1 and not output.exists()
    captured = capsys.readouterr()
    assert captured.out == "" and private not in captured.err and captured.err.strip() == cli.ERROR


@pytest.mark.parametrize("error", [IncompleteRead(b"private incomplete payload"), BadStatusLine("private malformed response")])
def test_http_protocol_failures_are_protected(monkeypatch, error):
    class BrokenResponse(Response):
        def read1(self, _size):
            raise error

    response = BrokenResponse()
    transport(monkeypatch, response)
    with pytest.raises(GoogleIncidentError) as caught:
        cli.fetch_feed()
    assert str(caught.value) == cli.ERROR and response.closed


def test_invalid_arguments_do_not_echo_received_secrets(capsys):
    private = token_hex(24)
    with pytest.raises(SystemExit) as caught:
        cli.main(["--unrecognized", private])
    assert caught.value.code == 2 and private not in capsys.readouterr().err
