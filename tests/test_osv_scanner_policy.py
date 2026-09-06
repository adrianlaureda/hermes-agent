"""Contratos de las excepciones OSV temporales del escritorio."""

from datetime import date
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "osv-scanner.toml"

EXPECTED_EXCEPTIONS = {
    "CVE-2026-56876",
    "CVE-2026-70606",
    "CVE-2026-70608",
}


def test_osv_exceptions_are_specific_and_expire() -> None:
    policy = tomllib.loads(POLICY.read_text(encoding="utf-8"))
    exceptions = policy.get("IgnoredVulns", [])

    assert {entry["id"] for entry in exceptions} == EXPECTED_EXCEPTIONS
    assert all(entry.get("reason", "").strip() for entry in exceptions)
    assert all(entry.get("ignoreUntil") == date(2026, 12, 1) for entry in exceptions)


def test_electron_runtime_mitigates_the_ignored_advisories() -> None:
    main = (ROOT / "apps/desktop/electron/main.ts").read_text(encoding="utf-8")
    media_protocol = (ROOT / "apps/desktop/electron/media-protocol.ts").read_text(encoding="utf-8")

    # CVE-2026-70608 no afecta a aplicaciones que deniegan la creación de
    # ventanas mediante setWindowOpenHandler.
    assert "setWindowOpenHandler" in main
    assert "return { action: 'deny' }" in main

    # CVE-2026-70606 exige devolver ProtocolResponse.url sin una sesión. El
    # protocolo de Hermes devuelve objetos Response y nunca usa esa API.
    assert "Promise<Response>" in media_protocol
    assert "ProtocolResponse" not in media_protocol
