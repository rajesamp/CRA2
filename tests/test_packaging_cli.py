"""CLI/config regressions, all offline and isolated from the user's environment."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cra2 import config
from cra2.__main__ import MAX_INPUT_CHARACTERS, main

ROOT = Path(__file__).resolve().parents[1]
CHANGE = {
    "service": "notification-service",
    "change_type": "Code deploy",
    "summary": "Batch email sends in groups of 50.",
    "rollback_plan": "Redeploy the previous image.",
}


def run_cli(tmp_path, *args, settings=None, stdin=None):
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("CRA2_")
    }
    env.pop("GROQ_API_KEY", None)
    env["PYTHONPATH"] = str(ROOT)
    env.update(settings or {})
    return subprocess.run(
        [sys.executable, "-m", "cra2", *args],
        cwd=tmp_path,
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("source", ["file", "stdin"])
def test_custom_change_does_not_need_sample_cases(
    tmp_path, monkeypatch, capsys, source
):
    monkeypatch.setattr(config, "EVALS_DIR", tmp_path / "missing-evals")
    if source == "stdin":
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(CHANGE)))
        change_arg = "-"
    else:
        path = tmp_path / "change.json"
        path.write_text(json.dumps(CHANGE), encoding="utf-8")
        change_arg = str(path)
    main([change_arg, "--mode", "fast", "--json"])
    assert json.loads(capsys.readouterr().out)["service"] == CHANGE["service"]


@pytest.mark.parametrize("body", ["", "[]", "null", '"text"', '{"service": NaN}'])
def test_invalid_stdin_is_a_usage_error(tmp_path, body):
    result = run_cli(tmp_path, "-", "--mode", "fast", stdin=body)
    assert result.returncode == 2
    assert "cra2: error:" in result.stderr
    assert "Traceback" not in result.stderr
    assert "No such file" not in result.stderr


def test_unknown_sample_case_is_clear(tmp_path):
    result = run_cli(tmp_path, "CHG-999", "--mode", "fast")
    assert result.returncode == 2
    assert "Unknown sample case 'CHG-999'" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CRA2_MODE", "invalid"),
        ("CRA2_MODEL", "  "),
        ("CRA2_SEED", "invalid"),
        ("CRA2_MAX_TOKENS", "0"),
        ("CRA2_MAX_TOKENS", "-1"),
        ("CRA2_MAX_TOKENS", "1.5"),
        ("CRA2_TIMEOUT_S", "0"),
        ("CRA2_TIMEOUT_S", "-1"),
        ("CRA2_TIMEOUT_S", "nan"),
        ("CRA2_TIMEOUT_S", "inf"),
        ("CRA2_TIMEOUT_S", "not-a-number"),
        ("CRA2_ENV_FILE", ""),
        ("CRA2_ENV_FILE", "missing.env"),
    ],
)
def test_invalid_configuration_is_a_usage_error(tmp_path, name, value):
    result = run_cli(tmp_path, "CHG-02", settings={name: value})
    assert result.returncode == 2
    assert name in result.stderr
    assert "Traceback" not in result.stderr


def test_help_does_not_load_invalid_settings(tmp_path):
    result = run_cli(tmp_path, "--help", settings={"CRA2_SEED": "bad"})
    assert result.returncode == 0
    assert "Advisory-only" in result.stdout


def test_dotenv_requires_explicit_opt_in_and_exports_win(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("CRA2_MODE=fast\nCRA2_SEED=invalid\n", encoding="utf-8")
    # An arbitrary working-directory dotenv cannot silently influence CRA2.
    implicit = run_cli(tmp_path, "CHG-02", "--mode", "fast", "--json")
    assert implicit.returncode == 0
    explicit = run_cli(tmp_path, "CHG-02", settings={"CRA2_ENV_FILE": str(dotenv)})
    assert explicit.returncode == 2
    assert "CRA2_SEED" in explicit.stderr
    overridden = run_cli(
        tmp_path,
        "CHG-02",
        "--json",
        settings={"CRA2_ENV_FILE": str(dotenv), "CRA2_SEED": "7"},
    )
    assert overridden.returncode == 0
    assert json.loads(overridden.stdout)["path"] == "system1"


def test_dotenv_next_to_package_is_not_implicitly_loaded(tmp_path):
    package = tmp_path / "isolated" / "cra2"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "config.py").write_bytes((ROOT / "cra2" / "config.py").read_bytes())
    (package / "secrets.py").write_bytes((ROOT / "cra2" / "secrets.py").read_bytes())
    (package.parent / ".env").write_text("CRA2_SEED=invalid\n", encoding="utf-8")
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("CRA2_")
    }
    env["PYTHONPATH"] = str(package.parent)
    result = subprocess.run(
        [sys.executable, "-c", "from cra2 import config; print(config.SEED)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "7"


def test_non_utf8_file_is_a_usage_error(tmp_path):
    path = tmp_path / "change.json"
    path.write_bytes(b"\xff\xfe")
    result = run_cli(tmp_path, str(path), "--mode", "fast")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("source", ["file", "stdin"])
@pytest.mark.parametrize("case", ["oversized", "deeply-nested", "duplicate-keys"])
def test_adversarial_json_is_a_bounded_usage_error(tmp_path, source, case):
    body, expected = {
        "oversized": (" " * (MAX_INPUT_CHARACTERS + 1), "exceeds 1,048,576 characters"),
        "deeply-nested": ("[" * 50_000 + "]" * 50_000, "nesting is too deep"),
        "duplicate-keys": (
            '{"service":"billing","service":"notification-service"}',
            "duplicate object keys",
        ),
    }[case]
    if source == "stdin":
        change_arg, stdin = "-", body
    else:
        path = tmp_path / "change.json"
        path.write_text(body, encoding="utf-8")
        change_arg, stdin = str(path), None
    result = run_cli(tmp_path, change_arg, "--mode", "fast", stdin=stdin)
    assert result.returncode == 2
    assert expected in result.stderr
    assert "Traceback" not in result.stderr


def test_credential_cannot_be_used_as_model_id(tmp_path):
    fake_key = "gsk_CRA2_FAKE_MODEL_ID_SENTINEL"
    result = run_cli(
        tmp_path, "CHG-02", settings={"GROQ_API_KEY": fake_key, "CRA2_MODEL": fake_key}
    )
    assert result.returncode == 2
    assert fake_key not in result.stderr + result.stdout
    assert "credentials" in result.stderr
