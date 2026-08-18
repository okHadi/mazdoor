"""Tests for the local dashboard server (stdlib http.server, no secrets)."""

import json

import pytest

from mazdoor import db, dashboard


@pytest.fixture()
def store(tmp_path):
    s = db.Store(tmp_path / "dash.db")
    job = {
        "source": "test", "source_id": "dash1", "external_url": "https://x/dash1",
        "title": "Platform Engineer", "company": "Acme", "location": "Worldwide",
        "description": "Terraform, Kubernetes", "description_url": None,
        "posted_at": None, "salary": None, "raw_json": None, "source_error": None,
    }
    job_id = s.upsert_job(job)
    s.update_curation(job_id, role_family="devops_sre_platform",
                      geo_tag="confirmed_eligible", geo_confidence=0.9,
                      geo_notes="Worldwide remote", score=82.0, score_breakdown=None)
    s.upsert_company_research(job_id, company_summary="Cloud infra company",
                              evidence_urls='["https://acme.com/about"]',
                              evidence_notes="Founded 2019", funding="Series A",
                              headcount="100", remote_policy="Remote-first")
    s.upsert_contact(job_id, name="Mira", role="CTO", source="public team page",
                     email="mira@acme.com", email_label="public", email_confidence=1.0,
                     evidence_url="https://acme.com/team", note="Listed on team page",
                     confidence_label="high", hiring_influence="Hiring manager",
                     role_is_current=1)
    s.upsert_outreach(job_id=job_id, contact_id=1, subject="Quick intro",
                      body="Hey Mira,\nI'm Hadi. Product Engineer.\n\n...")
    s.update_application(job_id, status="applied", applied_at="2026-08-18",
                         resume_path="artifacts/Hadi_Khan_Platform_Acme.pdf",
                         outreach_path=None, notes="Applied on site", outcome=None)
    yield s
    s.close()


@pytest.fixture()
def server(store):
    handle = dashboard.make_server(store, host="127.0.0.1", port=0)
    yield handle
    handle.stop()


def _get(server, path):
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{server.port}{path}") as r:
        return r.read().decode()


def test_index_lists_jobs(server):
    html = _get(server, "/")
    assert "Platform Engineer" in html
    assert "Acme" in html
    assert "82" in html  # score shown
    assert "confirmed_eligible" in html


def test_job_detail_exposes_evidence_and_artifacts(server):
    html = _get(server, "/job/1")
    assert "https://x/dash1" in html          # apply link
    assert "https://acme.com/about" in html   # evidence
    assert "mira@acme.com" in html            # contact email
    assert "public" in html                   # email label
    assert "resume" in html.lower()           # PDF link
    assert "Hey Mira" in html                 # copyable draft


def test_api_json_has_curated_fields(server):
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/api/jobs") as r:
        data = json.load(r)
    assert len(data["jobs"]) == 1
    j = data["jobs"][0]
    assert j["title"] == "Platform Engineer"
    assert j["role_family"] == "devops_sre_platform"
    assert j["geo_tag"] == "confirmed_eligible"
    assert j["score"] == pytest.approx(82.0)
    assert j["status"] == "applied"


def test_status_update_post(server, tmp_path, store):
    import urllib.request
    req = urllib.request.Request(
        f"http://127.0.0.1:{server.port}/api/job/1/status",
        data=json.dumps({"status": "interview", "outcome": "Recruiter call scheduled"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        resp = json.load(r)
    assert resp["ok"] is True
    app = store.get_application(1)
    assert app["status"] == "interview"
    assert app["outcome"] == "Recruiter call scheduled"


def test_no_write_actions_exposed(server):
    """Dashboard must never expose send/apply endpoints."""
    html = _get(server, "/")
    low = html.lower()
    for action in ["send-email", "submit-application", "auto-apply", "/api/send"]:
        assert action not in low
