"""Pruebas funcionales del watchdog de timeout del instalador."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

# Estos tests lanzan señuelos en sesiones y grupos de procesos propios para
# probar señales reales sin tocar procesos del runner.
pytestmark = pytest.mark.live_system_guard_bypass


def _run_timeout(tmp_path: Path, command: str) -> subprocess.CompletedProcess[str]:
    """Carga install.sh sin ejecutar main y ejecuta un escenario aislado."""
    script = f"source {shlex.quote(str(INSTALL_SH))}\n{command}\n"
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path / "hermes-home")
    process = subprocess.Popen(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        env=env,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=12)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=2)
        raise AssertionError("el harness de timeout quedó bloqueado") from None
    return subprocess.CompletedProcess(
        process.args, process.returncode, stdout, stderr,
    )


def _write_probe(path: Path) -> None:
    path.write_text(
        """#!/bin/sh
sentinel=$1
(sleep 2; printf alive > "$sentinel") &
child=$!
printf '%s' "$child" > "$sentinel.pid"
wait "$child"
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_timeout_returns_124_and_cleans_descendants(tmp_path: Path) -> None:
    """Un proceso hijo tipo npm no puede sobrevivir al deadline."""
    probe = tmp_path / "spawn-child.sh"
    sentinel = tmp_path / "child-survived"
    _write_probe(probe)

    started = time.monotonic()
    result = _run_timeout(
        tmp_path,
        "run_with_timeout 1 "
        f"{shlex.quote(str(probe))} {shlex.quote(str(sentinel))}",
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 124, result.stderr
    assert elapsed < 7, f"el watchdog tardó demasiado: {elapsed:.1f}s"
    time.sleep(2.3)
    assert not sentinel.exists()


def test_timeout_delivers_sigterm_before_escalation(tmp_path: Path) -> None:
    """La cancelación notifica al proceso antes de la limpieza forzada."""
    probe = tmp_path / "trap-term.sh"
    term_marker = tmp_path / "term-received"
    probe.write_text(
        """#!/bin/sh
marker=$1
trap 'printf term > "$marker"; exit 143' TERM
while :; do sleep 1; done
""",
        encoding="utf-8",
    )
    probe.chmod(0o755)

    result = _run_timeout(
        tmp_path,
        "run_with_timeout 1 "
        f"{shlex.quote(str(probe))} {shlex.quote(str(term_marker))}",
    )

    assert result.returncode == 124, result.stderr
    assert term_marker.read_text(encoding="utf-8") == "term"


@pytest.mark.parametrize(
    ("signal_to_send", "expected_marker", "expected_rc"),
    [
        (signal.SIGINT, "int", 130),
        (signal.SIGTERM, "term", 143),
    ],
    ids=["sigint", "sigterm"],
)
def test_external_signal_is_forwarded_to_watched_group(
    tmp_path: Path,
    signal_to_send: signal.Signals,
    expected_marker: str,
    expected_rc: int,
) -> None:
    """Una interrupción externa cancela el grupo vigilado sin quedar colgada."""
    probe = tmp_path / "trap-signal.sh"
    int_marker = tmp_path / "int-received"
    probe.write_text(
        """#!/bin/sh
marker=$1
printf ready > "$marker.ready"
trap 'printf int > "$marker"; exit 130' INT
trap 'printf term > "$marker"; exit 143' TERM
while :; do sleep 1; done
""",
        encoding="utf-8",
    )
    probe.chmod(0o755)
    script = (
        f"source {shlex.quote(str(INSTALL_SH))}\n"
        "set +e\n"
        "run_with_timeout 30 "
        f"{shlex.quote(str(probe))} {shlex.quote(str(int_marker))}\n"
        "printf 'WATCHDOG_RC=%s\\n' \"$?\"\n"
    )
    process = subprocess.Popen(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        env={**os.environ, "HERMES_HOME": str(tmp_path / "hermes-home")},
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not int_marker.with_name(f"{int_marker.name}.ready").exists():
            if process.poll() is not None:
                break
            if time.monotonic() >= deadline:
                raise AssertionError("el señuelo no arrancó")
            time.sleep(0.05)
        os.killpg(process.pid, signal_to_send)
        stdout, stderr = process.communicate(timeout=6)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)

    assert f"WATCHDOG_RC={expected_rc}" in stdout, stderr
    assert int_marker.read_text(encoding="utf-8") == expected_marker


def test_external_sigint_cleans_descendant_after_leader_exit(tmp_path: Path) -> None:
    """La limpieza alcanza a un hijo que sobrevive a la salida del líder."""
    probe = tmp_path / "leader-exits-on-int.sh"
    ready_marker = tmp_path / "leader-ready"
    escaped_marker = tmp_path / "escaped"
    probe.write_text(
        """#!/bin/sh
ready=$1
escaped=$2
(trap '' INT TERM; sleep 4; printf escaped > "$escaped") &
printf ready > "$ready"
trap 'exit 130' INT
wait
""",
        encoding="utf-8",
    )
    probe.chmod(0o755)
    script = (
        f"source {shlex.quote(str(INSTALL_SH))}\n"
        "set +e\n"
        "run_with_timeout 30 "
        f"{shlex.quote(str(probe))} {shlex.quote(str(ready_marker))} "
        f"{shlex.quote(str(escaped_marker))}\n"
        "printf 'WATCHDOG_RC=%s\\n' \"$?\"\n"
    )
    process = subprocess.Popen(
        ["bash", "-c", script],
        cwd=REPO_ROOT,
        env={**os.environ, "HERMES_HOME": str(tmp_path / "hermes-home")},
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not ready_marker.exists():
            if process.poll() is not None:
                break
            if time.monotonic() >= deadline:
                raise AssertionError("el líder no arrancó")
            time.sleep(0.05)
        os.killpg(process.pid, signal.SIGINT)
        stdout, stderr = process.communicate(timeout=7)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)

    assert "WATCHDOG_RC=130" in stdout, stderr
    time.sleep(1.5)
    assert not escaped_marker.exists()


def test_timeout_does_not_kill_unrelated_process(tmp_path: Path) -> None:
    """El grupo aislado del instalador no incluye procesos del llamador."""
    probe = tmp_path / "spawn-child.sh"
    _write_probe(probe)
    command = f"""
sleep 10 &
unrelated=$!
set +e
run_with_timeout 1 {shlex.quote(str(probe))} {shlex.quote(str(tmp_path / 'child'))}
timeout_rc=$?
set -e
if kill -0 "$unrelated" 2>/dev/null; then
    echo UNRELATED_ALIVE
    kill "$unrelated" 2>/dev/null || true
else
    echo UNRELATED_DEAD
fi
exit "$timeout_rc"
"""
    result = _run_timeout(tmp_path, command)

    assert result.returncode == 124, result.stderr
    assert "UNRELATED_ALIVE" in result.stdout


def test_timeout_preserves_completed_exit_status(tmp_path: Path) -> None:
    """Un comando que termina a tiempo conserva su código real."""
    result = _run_timeout(tmp_path, "run_with_timeout 5 sh -c 'exit 37'")

    assert result.returncode == 37, result.stderr


def test_timeout_cleans_function_descendants(tmp_path: Path) -> None:
    """La ruta para funciones cubre los helpers internos del instalador."""
    sentinel = tmp_path / "function-child-survived"
    command = f"""
probe() {{
    (sleep 2; printf alive > {shlex.quote(str(sentinel))}) &
    wait
}}
run_with_timeout 1 probe
"""
    result = _run_timeout(tmp_path, command)

    assert result.returncode == 124, result.stderr
    time.sleep(2.3)
    assert not sentinel.exists()
