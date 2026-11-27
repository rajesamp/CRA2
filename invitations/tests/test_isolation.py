import ast
from pathlib import Path
import subprocess
import sys
import tomllib


def test_invitation_runtime_has_no_cra2_import_or_runtime_hook():
    root = Path(__file__).resolve().parents[2]
    legacy = {"cra2", "week1", "week2", "week3", "week4", "evaluation"}

    def imports(path):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                yield from (item.name.split(".")[0] for item in node.names)
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                yield node.module.split(".")[0]

    for path in (root / "invitations").glob("*.py"):
        assert legacy.isdisjoint(imports(path)), path
    for directory in legacy:
        for path in (root / directory).glob("*.py"):
            assert "invitations" not in imports(path), path
    build = tomllib.loads((root / "pyproject.toml").read_text())
    assert build["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["cra2"]
    assert not any(
        line.startswith("!invitations") for line in (root / ".dockerignore").read_text().splitlines()
    )
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from invitations.web import create_app; "
            "assert not {'cra2','week2','gradio','laya'} & sys.modules.keys()",
        ],
        check=True,
        cwd=root,
    )
