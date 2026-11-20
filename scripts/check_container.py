"""Verify an already-built Podman image with networking disabled; never deploy."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/app/week2/.venv/bin/python"
READY = """import sys, urllib.request, urllib.error
try:
    urllib.request.urlopen('http://127.0.0.1:8087/config', timeout=1).close()
except (urllib.error.URLError, TimeoutError):
    sys.exit(75)
"""
HTTP = """import json, urllib.request, urllib.error
from pathlib import Path
with urllib.request.urlopen('http://127.0.0.1:8087/config', timeout=2) as response:
    config = json.load(response)
    assert response.status == 200 and config['components']
    result = {'config_status': response.status, 'component_count': len(config['components']),
              'port': 8087, 'transport': 'container loopback, networking disabled'}
assert any(line.split()[1] == '00000000:1F97' and line.split()[3] == '0A'
           for line in Path('/proc/net/tcp').read_text().splitlines()[1:])
result['listen_address'] = '0.0.0.0'
try:
    urllib.request.urlopen('http://127.0.0.1:8087/gradio_api/file=/app/data/team_settings.json', timeout=2)
except urllib.error.HTTPError as error:
    result['application_file_status'] = error.code
else:
    raise AssertionError('application file exposed')
assert result['application_file_status'] in (403, 404)
print(json.dumps(result))
"""
CLOUD_HTTP = """import json, urllib.request, urllib.error
results = {}
for path in ('/', '/config', '/gradio_api/queue/join', '/gradio_api/queue/data?session_hash=other'):
    request = urllib.request.Request('http://127.0.0.1:8087' + path,
        headers={'x-goog-authenticated-user-email': 'owner@example.test'})
    try:
        urllib.request.urlopen(request, timeout=2)
    except urllib.error.HTTPError as error:
        assert error.code == 401
        results[path] = error.code
    else:
        raise AssertionError('unsigned identity was admitted')
with urllib.request.urlopen('http://127.0.0.1:8087/healthz', timeout=2) as response:
    assert json.load(response) == {'status': 'ok'}
print(json.dumps({'health_status': 200, 'unsigned_identity_routes': results,
                  'live_google_identity_tested': False}))
"""
LANDING_HTTP = """import json, urllib.request, urllib.error
base='http://127.0.0.1:8087'
with urllib.request.urlopen(base+'/',timeout=2) as response:
    page=response.read().decode()
    assert response.status==200 and 'Sign in with Google' in page
    assert 'Logged in users' not in page and '@' not in page
    assert 'set-cookie' not in response.headers
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
try:
    urllib.request.build_opener(NoRedirect).open(base+'/signin?next=https://attacker.example.test',timeout=2)
except urllib.error.HTTPError as response:
    assert response.code==303 and response.headers['Location']=='https://protected-synthetic.a.run.app/'
else: raise AssertionError('Sign-in redirect missing')
denied={}
for path in ('/users','/config','/upload','/gradio_api/queue/join','/gradio_api/file=/app/data/team_settings.json'):
    try: urllib.request.urlopen(base+path,timeout=2)
    except urllib.error.HTTPError as response:
        assert response.code==404
        denied[path]=response.code
    else: raise AssertionError('Private route exposed')
print(json.dumps({'anonymous_intro_status':200,'fixed_signin_redirect':True,'identity_content_exposed':False,'private_routes':denied}))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--connection", help="Optional Podman connection; does not change its default")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prefix = ["podman"] + (["--connection", args.connection] if args.connection else [])

    def command(arguments, *, check=True):
        result = subprocess.run(prefix + arguments, capture_output=True, text=True, timeout=180)
        if check and result.returncode:
            raise RuntimeError(f"Podman {arguments[0]} failed: {result.stderr.strip()}")
        return result

    info = json.loads(command(["image", "inspect", args.image]).stdout)[0]
    # Use the immutable local ID throughout, even if the tag changes meanwhile.
    image = info["Id"]
    report = {"image_id": image, "os": info["Os"], "architecture": info["Architecture"],
              "user": info["Config"]["User"]}
    assert (report["os"], report["architecture"], report["user"]) == ("linux", "amd64", "65532:65532")
    probe = ("import json,sys; from week3.acceptance import run; r=run(); "
             "print(json.dumps(r)); sys.exit(0 if r['passed']==r['total'] else 1)")
    report["offline_six_intents"] = json.loads(command([
        "run", "--rm", "--network", "none", "--entrypoint", PYTHON, image, "-c", probe,
    ]).stdout)
    assert report["offline_six_intents"]["passed"] == report["offline_six_intents"]["total"] == 6
    def verify_http(arguments, ready_probe, http_probe):
        container = command(["run", "-d", "--network", "none", "-e", "PORT=8087", *arguments]).stdout.strip()
        try:
            deadline = time.monotonic() + 60
            while True:
                ready = command(["exec", container, PYTHON, "-c", ready_probe], check=False)
                if ready.returncode == 0:
                    break
                if ready.returncode != 75 or time.monotonic() >= deadline:
                    logs = command(["logs", container], check=False)
                    raise RuntimeError("Container startup failed:\n" + ready.stderr + logs.stdout + logs.stderr)
                time.sleep(.5)
            # Assertions run once after readiness; failures cannot masquerade as startup retries.
            return json.loads(command(["exec", container, PYTHON, "-c", http_probe]).stdout)
        finally:
            command(["stop", "--time", "5", container], check=False)
            command(["rm", container])

    report["http"] = verify_http([image], READY, HTTP)
    report["cloud_entrypoint"] = verify_http([
        "-e", "K_SERVICE=synthetic-service", "-e", "CRA2_OWNER_EMAIL=owner@example.test",
        "-e", "CRA2_IAP_AUDIENCE=/projects/123456789/locations/test-region/services/test-service",
        "-e", "CRA2_STATE_BUCKET=state-synthetic", "-e", "CRA2_AUDIT_BUCKET=audit-synthetic",
        "--entrypoint", PYTHON, image, "-m", "week2.cloud_app",
    ], READY.replace("/config", "/healthz"), CLOUD_HTTP)
    report["public_intro"] = verify_http([
        "-e", "CRA2_APP_URL=https://protected-synthetic.a.run.app/",
        "--entrypoint", PYTHON, image, "-m", "week2.landing",
    ], READY.replace("/config", "/healthz"), LANDING_HTTP)
    report["source_hashes"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("Containerfile", ".dockerignore", "week2/app.py", "week3/guardrails.py",
                     "week2/iap.py", "week2/cloud_app.py", "week2/cloud_storage.py", "week2/uv.lock",
                     "week2/landing.py", "week2/presence.py", "week2/welcome.py",
                     "scripts/check_container.py")
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"offline_six_intents", "source_hashes"}}))
    print("Offline graph intents: 6/6; network disabled. Evidence:", args.out)


if __name__ == "__main__":
    main()
