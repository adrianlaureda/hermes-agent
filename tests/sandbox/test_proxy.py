"""Regresiones del proxy de red usado por el sandbox de instalación."""

from __future__ import annotations

import importlib.util
import pathlib
import ssl
import sys
from unittest.mock import MagicMock, patch


def _load_proxy():
    path = pathlib.Path(__file__).parents[2] / "scripts" / "sandbox" / "proxy.py"
    spec = importlib.util.spec_from_file_location("hermes_sandbox_proxy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "argv", [str(path), "/tmp/http", "/tmp/certs", "/tmp/ca"]):
        spec.loader.exec_module(module)
    return module


def test_open_upstream_retries_transient_tls_eof():
    """Un EOF de TLS del registro no debe abortar el instalador al primer intento."""
    proxy = _load_proxy()
    context = MagicMock()
    first_raw = MagicMock()
    second_raw = MagicMock()
    expected = MagicMock()
    context.wrap_socket.side_effect = [
        ssl.SSLEOFError("unexpected eof"),
        expected,
    ]

    with (
        patch.object(proxy.ssl, "create_default_context", return_value=context),
        patch.object(
            proxy.socket,
            "create_connection",
            side_effect=[first_raw, second_raw],
        ),
        patch.object(proxy.time, "sleep") as sleep,
    ):
        result = proxy._open_upstream("registry.npmjs.org", 443, tls=True)

    assert result is expected
    assert context.wrap_socket.call_count == 2
    first_raw.close.assert_called_once_with()
    sleep.assert_called_once_with(proxy.UPSTREAM_RETRY_DELAY_SECONDS)


def test_open_upstream_closes_failed_socket_and_raises_after_budget():
    proxy = _load_proxy()
    context = MagicMock()
    raws = [MagicMock() for _ in range(proxy.UPSTREAM_MAX_ATTEMPTS)]
    context.wrap_socket.side_effect = [
        ssl.SSLEOFError("unexpected eof")
    ] * proxy.UPSTREAM_MAX_ATTEMPTS

    with (
        patch.object(proxy.ssl, "create_default_context", return_value=context),
        patch.object(proxy.socket, "create_connection", side_effect=raws),
        patch.object(proxy.time, "sleep") as sleep,
    ):
        try:
            proxy._open_upstream("registry.npmjs.org", 443, tls=True)
        except ssl.SSLEOFError:
            pass
        else:
            raise AssertionError("expected the final upstream error")

    for raw in raws:
        raw.close.assert_called_once_with()
    assert sleep.call_count == proxy.UPSTREAM_MAX_ATTEMPTS - 1
