"""El instalador admite ejecución por archivo y por stdin sin instalar nada."""

import json
import os
import subprocess
from pathlib import Path

import pytest

INSTALL_SH = Path(__file__).resolve().parent.parent / "scripts" / "install.sh"


@pytest.mark.parametrize("via_stdin", [False, True])
def test_manifest_entrypoint(via_stdin, tmp_path):
    env = {**os.environ, "HERMES_HOME": str(tmp_path / "hermes-home")}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    command = ["bash", "-s", "--", "--manifest"] if via_stdin else [
        "bash", str(INSTALL_SH), "--manifest",
    ]
    result = subprocess.run(
        command,
        input=INSTALL_SH.read_text(encoding="utf-8") if via_stdin else None,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout), "El entrypoint debe emitir el manifiesto"
