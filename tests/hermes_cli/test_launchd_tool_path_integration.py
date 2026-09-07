"""Comprueba el PATH generado ejecutando herramientas desde el entorno plist."""

import plistlib
import subprocess

import pytest


@pytest.mark.macos_only
def test_launchd_environment_resolves_managed_node_and_shell_ffmpeg(tmp_path, monkeypatch):
    from hermes_cli.gateway import generate_launchd_plist
    from hermes_constants import reset_hermes_home_override, set_hermes_home_override

    home = tmp_path / "profile"
    managed = home / "node/bin"
    brew = tmp_path / "brew/bin"
    managed.mkdir(parents=True)
    brew.mkdir(parents=True)
    for directory, name in ((managed, "node"), (brew, "ffmpeg")):
        executable = directory / name
        executable.write_text(f"#!/bin/sh\necho {name}-probe\n", encoding="utf-8")
        executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{brew}:/usr/bin:/bin")
    token = set_hermes_home_override(home)
    try:
        plist = plistlib.loads(generate_launchd_plist().encode())
    finally:
        reset_hermes_home_override(token)
    env = plist["EnvironmentVariables"]
    assert env["HERMES_HOME"] == str(home.resolve())
    for name in ("node", "ffmpeg"):
        result = subprocess.run(
            [name], env=env, capture_output=True, text=True, check=True, timeout=5,
        )
        assert result.stdout.strip() == f"{name}-probe"
