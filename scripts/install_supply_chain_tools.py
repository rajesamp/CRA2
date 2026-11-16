"""Install exact publisher release assets into a task directory, never globally."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile

LOCK = Path(__file__).with_name("supply-chain-tools.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    system = platform.system().lower()
    if system not in {"linux", "darwin"} or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise SystemExit("Only the reviewed Linux/macOS amd64 assets are pinned")
    args.dest.mkdir(parents=True, exist_ok=True)
    lock = json.loads(LOCK.read_text())
    installed = {}
    with tempfile.TemporaryDirectory(prefix="cra2-security-tools-") as directory:
        for repo, spec in lock["tools"].items():
            name = repo.split("/")[1]
            suffix = f"{system}_amd64.tar.gz" if name != "cosign" else f"cosign-{system}-amd64"
            assets = [a for a in spec["assets"] if a["name"].endswith(suffix)
                      or "checksums.txt" in a["name"]]
            if len(assets) != 3:
                raise ValueError("Missing binary/checksum/signature pins")
            for asset in assets:
                if not asset["url"].startswith(f"https://github.com/{repo}/releases/download/{spec['tag']}/"):
                    raise ValueError("Unexpected release asset source")
                target = Path(directory) / asset["name"]
                subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                    "--proto", "=https", "--proto-redir", "=https", "--max-time", "180",
                    "--max-filesize", str(asset["size"]), "--output", str(target), asset["url"]], check=True)
                raw = target.read_bytes()
                if len(raw) != asset["size"] or hashlib.sha256(raw).hexdigest() != asset["sha256"]:
                    raise ValueError("Release asset checksum/size mismatch")
                if "checksums.txt" in asset["name"]:
                    shutil.copyfile(target, args.dest / asset["name"])
                    continue
                binary = args.dest / name
                if target.name.endswith(".tar.gz"):
                    with tarfile.open(target, "r:gz") as archive:
                        member = archive.getmember(name)
                        if not member.isfile() or member.size > 300_000_000:
                            raise ValueError("Invalid binary archive entry")
                        with archive.extractfile(member) as source, binary.open("wb") as output:
                            shutil.copyfileobj(source, output)
                else:
                    shutil.copyfile(target, binary)
                binary.chmod(0o755)
                installed[name] = {"version": spec["tag"], "asset_name": asset["name"], "asset_sha256": asset["sha256"],
                    "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    # Publisher identities come from Sigstore's installation documentation and
    # Anchore's install.sh at the pinned release, not from an untrusted bundle.
    for repo, spec in lock["tools"].items():
        name = repo.split("/")[1]
        checksum = next(a for a in spec["assets"] if a["name"].endswith("checksums.txt"))
        identity = ("keyless@projectsigstore.iam.gserviceaccount.com" if name == "cosign"
                    else f"https://github.com/{repo}/.github/workflows/release.yaml@refs/heads/main")
        issuer = "https://accounts.google.com" if name == "cosign" else "https://token.actions.githubusercontent.com"
        subprocess.run([str(args.dest / "cosign"), "verify-blob", "--bundle",
            str(args.dest / (checksum["name"] + ".sigstore.json")),
            "--certificate-identity", identity, "--certificate-oidc-issuer", issuer,
            str(args.dest / checksum["name"])], check=True)
        entries = [line.split() for line in (args.dest / checksum["name"]).read_text().splitlines()]
        expected = installed[name]
        if [expected["asset_sha256"], expected["asset_name"]] not in entries:
            raise ValueError("Binary archive is absent from the signed publisher checksums")
        installed[name]["publisher_signature_verified"] = True
    report = {"lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(), "installed": installed,
              "signature_status": "Publisher signatures and binary archive checksums verified"}
    (args.dest / "install.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
