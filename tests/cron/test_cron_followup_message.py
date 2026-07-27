"""Contrato de persistencia y superficies del follow-up de cron."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    """Aísla el almacén cron sin tocar los jobs reales."""
    home = tmp_path / ".hermes"
    cron_dir = home / "cron"
    cron_dir.mkdir(parents=True)

    import cron.jobs as jobs

    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(jobs, "HERMES_DIR", home)
    monkeypatch.setattr(jobs, "CRON_DIR", cron_dir)
    monkeypatch.setattr(jobs, "JOBS_FILE", cron_dir / "jobs.json")
    monkeypatch.setattr(jobs, "OUTPUT_DIR", cron_dir / "output")
    return home


def test_create_update_and_json_roundtrip(cron_env):
    from cron.jobs import create_job, get_job, load_jobs, update_job

    job = create_job(
        prompt="daily brief",
        schedule="every 1h",
        followup_message="  - Sueño:\n- Prioridad:  ",
    )
    assert job["followup_message"] == "- Sueño:\n- Prioridad:"
    assert get_job(job["id"])["followup_message"] == "- Sueño:\n- Prioridad:"
    assert load_jobs()[0]["followup_message"] == "- Sueño:\n- Prioridad:"

    updated = update_job(job["id"], {"followup_message": "  - Energía:  "})
    assert updated["followup_message"] == "- Energía:"
    assert get_job(job["id"])["followup_message"] == "- Energía:"

    cleared = update_job(job["id"], {"followup_message": ""})
    assert cleared["followup_message"] is None


def test_cronjob_tool_create_update_list_roundtrip(cron_env, monkeypatch):
    monkeypatch.setenv("HERMES_INTERACTIVE", "1")
    from tools.cronjob_tools import cronjob

    created = json.loads(cronjob(
        action="create",
        schedule="every 1h",
        prompt="daily brief",
        followup_message="- Sueño:\n- Prioridad:",
    ))
    assert created["success"] is True
    assert created["job"]["followup_message"] == "- Sueño:\n- Prioridad:"

    updated = json.loads(cronjob(
        action="update",
        job_id=created["job_id"],
        followup_message="- Energía:",
    ))
    assert updated["job"]["followup_message"] == "- Energía:"

    listed = json.loads(cronjob(action="list"))
    assert listed["jobs"][0]["followup_message"] == "- Energía:"
