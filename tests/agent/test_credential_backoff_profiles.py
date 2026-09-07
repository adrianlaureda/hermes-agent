"""El backoff debe respetar perfiles y detectar credenciales recuperadas."""

from contextlib import contextmanager

import pytest

from agent import credential_pool as pool_mod
from agent.credential_pool import CredentialPool, PooledCredential
from hermes_constants import reset_hermes_home_override, set_hermes_home_override


@contextmanager
def profile(home):
    token = set_hermes_home_override(home)
    try:
        yield
    finally:
        reset_hermes_home_override(token)


@pytest.fixture(autouse=True)
def isolated_backoff(monkeypatch):
    monkeypatch.setattr(pool_mod, "_EMPTY_POOL_BACKOFF_UNTIL", {})
    monkeypatch.delenv("HERMES_SHARED_BACKOFF", raising=False)


def test_shared_backoff_path_uses_active_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SHARED_BACKOFF", "1")
    with profile(tmp_path / "secondary"):
        path = pool_mod._shared_empty_pool_backoff_path("openai-codex")
    assert path == tmp_path / "secondary/state/credential-backoff/openai-codex.json"


def test_memory_backoff_does_not_cross_context_profiles(tmp_path):
    with profile(tmp_path / "first"):
        pool_mod._set_empty_pool_backoff("openai-codex")
        assert pool_mod._empty_pool_backoff_active("openai-codex")
    with profile(tmp_path / "second"):
        assert not pool_mod._empty_pool_backoff_active("openai-codex")
    with profile(tmp_path / "first"):
        assert pool_mod._empty_pool_backoff_active("openai-codex")


@pytest.mark.parametrize("probe", ["has_available", "peek"])
def test_recovered_entry_is_visible_during_backoff(probe):
    assert CredentialPool("openai-codex", []).select() is None
    entry = PooledCredential(id="recovered", provider="openai-codex", label="test", auth_type="api_key", priority=0, source="manual", access_token="test-only")
    recovered = CredentialPool("openai-codex", [entry])
    result = getattr(recovered, probe)()
    assert result is True if probe == "has_available" else result is entry


def test_shared_backoff_survives_process_restart_without_crossing_profiles(tmp_path, monkeypatch):
    """Un proceso nuevo comparte solo el backoff de su mismo perfil."""
    import os
    import subprocess
    import sys

    monkeypatch.setenv("HERMES_SHARED_BACKOFF", "1")
    first = tmp_path / "first"
    second = tmp_path / "second"
    with profile(first):
        pool_mod._set_empty_pool_backoff("openai-codex")
    code = (
        "from agent.credential_pool import _empty_pool_backoff_active; "
        "print(_empty_pool_backoff_active('openai-codex'))"
    )
    for home, expected in [(first, "True"), (second, "False")]:
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "HERMES_HOME": str(home)},
            capture_output=True, text=True, timeout=15, check=True,
        )
        assert result.stdout.strip() == expected


@pytest.mark.windows_only
def test_windows_persists_backoff_without_posix_fd_operations(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_SHARED_BACKOFF", "1")
    with profile(tmp_path):
        pool_mod._set_empty_pool_backoff("openai-codex")
        assert pool_mod._read_shared_empty_pool_backoff("openai-codex") is not None
        pool_mod._clear_empty_pool_backoff("openai-codex")
        assert pool_mod._read_shared_empty_pool_backoff("openai-codex") is None


def test_concurrent_profile_backoffs_are_independent(tmp_path):
    """Los ContextVar de dos hilos no deben heredar el estado del otro."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ready = Barrier(2)

    def check(index):
        with profile(tmp_path / str(index)):
            if index == 0:
                pool_mod._set_empty_pool_backoff("openai-codex")
            ready.wait(timeout=5)
            return pool_mod._empty_pool_backoff_active("openai-codex")

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(check, [0, 1])) == [True, False]
