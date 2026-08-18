"""Tests for research ingestion and finalize (resume/draft regeneration)."""

import json

import pytest

from mazdoor import db, research
from mazdoor.scoring import geo_eligibility


@pytest.fixture()
def store(tmp_path):
    s = db.Store(tmp_path / "r.db")
    job = {
        "source": "remotive", "source_id": "42", "external_url": "https://x/42",
        "title": "Platform Engineer", "company": "Acme", "location": "Remote",
        "description": "Terraform, AWS, Kubernetes, CI/CD, Linux, Docker",
        "description_url": None, "posted_at": None, "salary": None,
        "raw_json": None, "source_error": None,
    }
    jid = s.upsert_job(job)
    s.update_curation(jid, role_family="devops_sre_platform", geo_tag="possible_exception",
                      geo_confidence=0.45, geo_notes="JD says remote only",
                      score=85.0, score_breakdown=None, rationale="strong infra JD")
    yield s
    s.close()


def test_ingest_research_applies_geo_citations_and_contacts(store, tmp_path):
    jid = store.get_jobs()[0]["id"]
    rec = {
        "job_id": jid,
        "company_summary": "Cloud infra company with global remote team",
        "evidence_urls": json.dumps(["https://acme.com/careers"]),
        "evidence_notes": ("careers page (2026-08-18): 'hiring worldwide across "
                           "APAC, EMEA, Americas'"),
        "funding": "Series B",
        "headcount": "150 employees",
        "remote_policy": "Remote-first, hires worldwide",
        "geo": {
            "tag": "confirmed_eligible",
            "confidence": 0.8,
            "citations": [
                {"url": "https://acme.com/careers", "accessed": "2026-08-18",
                 "note": "Careers page says hiring worldwide including APAC"},
                {"url": "https://acme.com/hiring", "accessed": "2026-08-18",
                 "note": "Engineering blog: 20% of team based in South Asia"},
            ],
        },
        "contacts": [{
            "name": "Mira Chen", "role": "Head of Platform", "source": "team page",
            "email": "mira@acme.com", "email_label": "public", "email_confidence": 0.95,
            "evidence_url": "https://acme.com/team", "note": "Public team page",
            "confidence_label": "high", "hiring_influence": "Hiring manager for platform roles",
            "role_is_current": 1,
        }],
    }
    applied = research.ingest_research(store, [rec], geo=True, gen_drafts=False)
    assert applied == 1
    job = store.get_job(jid)
    assert job["geo_tag"] == "confirmed_eligible"
    assert job["geo_confidence"] == pytest.approx(0.8)
    assert "acme.com/careers" in job["geo_notes"]
    assert "2026-08-18" in job["geo_notes"]
    contacts = store.get_contacts(jid)
    assert len(contacts) == 1
    assert contacts[0]["confidence_label"] == "high"
    assert contacts[0]["email_label"] == "public"


def test_ingest_geo_derives_citations_from_evidence_when_absent(store, tmp_path):
    jid = store.get_jobs()[0]["id"]
    rec = {
        "job_id": jid,
        "company_summary": "x", "evidence_urls": "[]",
        "evidence_notes": "hiring worldwide including Pakistan (careers page, accessed 2026-08-18)",
        "funding": None, "headcount": None, "remote_policy": None,
        "geo": None,  # derive from evidence_notes
        "contacts": [],
    }
    research.ingest_research(store, [rec], geo=True, gen_drafts=False)
    job = store.get_job(jid)
    assert job["geo_tag"] == "confirmed_eligible"
    assert job["geo_confidence"] >= 0.5


def test_finalize_regenerates_artifacts_and_drafts(store, tmp_path, monkeypatch):
    from mazdoor import pipeline
    jid = store.get_jobs()[0]["id"]
    artifacts = tmp_path / "art"
    store.upsert_contact(jid, name="Mira", role="Head of Platform", source="team page",
                         email="mira@acme.com", email_label="public", email_confidence=0.95,
                         evidence_url="https://acme.com/team", note="public",
                         confidence_label="high", hiring_influence="hiring",
                         role_is_current=1)
    state = pipeline.finalize(store, artifacts_dir=artifacts)
    assert state["resumes_generated"] == 1
    assert state["drafts_generated"] == 1
    assert list(artifacts.glob("*.pdf")), "PDF must exist"
    assert list(artifacts.glob("outreach_*.md")), "draft must exist"
    job = store.get_job(jid)
    assert job["tailoring_plan"] is not None
    app = store.get_application(jid)
    assert app["status"] == "prepared"
    assert app["resume_path"]
