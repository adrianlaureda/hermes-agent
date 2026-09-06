"""TLS trust contract for Node processes inside the development sandbox."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE2 = REPO_ROOT / "scripts" / "sandbox" / "stage2-run.sh"


def test_node_trusts_the_sandbox_mitm_ca() -> None:
    script = STAGE2.read_text(encoding="utf-8")

    assert "--setenv NODE_EXTRA_CA_CERTS /work/certs/ca.pem" in script
    assert "--setenv NODE_EXTRA_CA_CERTS /work/certs/real-ca.pem" not in script
