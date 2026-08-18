"""Tests for the SQLite storage layer (WAL mode)."""

import os
import sqlite3

import pytest

from mazdoor import db


@pytest.fixture()
def store(tmp_path):
    s = db.Store(tmp_path / "test.db")
    yield s
    s.close()


def test_wal_mode_enabled(store):
    assert store.journal_mode() == "wal"


def test_foreign_keys_enforced(tmp_path):
    s = db.Store(tmp_path / "fk.db")
    with pytest.raises(sqlite3.IntegrityError):
        s.upsert_contact(
            job_id=9999, name="Nobody", role="X", source="test",
            email=None, email_label=None, email_confidence=None,
            evidence_url=None, note=None,
        )
    s.close()


def test_upsert_job_idempotent(store):
    job = {
        "source": "test-src", "source_id": "abc", "external_url": "https://x/job",
        "title": "Backend Engineer", "company": "Acme", "location": "Remote",
        "description": "Build APIs", "description_url": "https://x/job",
        "posted_at": "2026-08-01", "salary": None, "raw_json": '{"a":1}',
        "source_error": None,
    }
    job_id = store.upsert_job(job)
    again = store.upsert_job(job)
    assert job_id == again
    rows = store.get_jobs()
    assert len(rows) == 1


def test_job_survives_roundtrip(store):
    job = {
        "source": "test-src", "source_id": "xyz", "external_url": "https://x/job2",
        "title": "SRE", "company": "Beta", "location": "Worldwide",
        "description": "Reliability work", "description_url": None,
        "posted_at": None, "salary": "100k", "raw_json": None, "source_error": None,
    }
    job_id = store.upsert_job(job)
    row = store.get_job(job_id)
    assert row["title"] == "SRE"
    assert row["company"] == "Beta"
    assert row["salary"] == "100k"


def test_curation_fields_roundtrip(store):
    job = {
        "source": "test-src", "source_id": "cur", "external_url": "https://x/c",
        "title": "Platform Engineer", "company": "Gamma", "location": "Remote",
        "description": "Kubernetes", "description_url": None, "posted_at": None,
        "salary": None, "raw_json": None, "source_error": None,
    }
    job_id = store.upsert_job(job)
    store.update_curation(
        job_id,
        role_family="devops_sre_platform",
        geo_tag="confirmed_eligible",
        geo_confidence=0.9,
        geo_notes="Worldwide remote",
        score=81.5,
        score_breakdown={"required": 0.8, "preferred": 0.7},
    )
    row = store.get_job(job_id)
    assert row["role_family"] == "devops_sre_platform"
    assert row["geo_tag"] == "confirmed_eligible"
    assert row["geo_confidence"] == pytest.approx(0.9)
    assert row["score"] == pytest.approx(81.5)


def test_company_research_roundtrip(store):
    job = _mk_job(store, "co")
    store.upsert_company_research(
        job_id=job,
        company_summary="Does infra tooling",
        evidence_urls=['["https://company.com/about", "https://news.example/funding"]'],
        evidence_notes="Series B announced 2026",
        funding="Series B",
        headcount="50-100",
        remote_policy="Remote-first",
    )
    row = store.get_company_research(job)
    assert row["company_summary"].startswith("Does infra")
    assert "Series B" in row["funding"]


def test_contact_roundtrip_and_labeling(store):
    job = _mk_job(store, "ct")
    store.upsert_contact(
        job_id=job, name="Ada Lovelace", role="Head of Eng", source="team page",
        email="ada@company.com", email_label="public", email_confidence=1.0,
        evidence_url="https://company.com/team", note="Listed on public team page",
    )
    rows = store.get_contacts(job)
    assert len(rows) == 1
    assert rows[0]["email_label"] == "public"
    assert rows[0]["email_confidence"] == 1.0


def test_application_status_and_outcome_roundtrip(store):
    job = _mk_job(store, "app")
    store.update_application(
        job_id=job, status="applied", applied_at="2026-08-18",
        resume_path="artifacts/x.pdf", outreach_path="artifacts/x.md",
        notes="Applied via company site", outcome=None,
    )
    row = store.get_application(job)
    assert row["status"] == "applied"
    assert row["resume_path"] == "artifacts/x.pdf"

    store.update_application(
        job_id=job, status="interview", applied_at="2026-08-18",
        resume_path=None, outreach_path=None,
        notes=None, outcome="Screen scheduled",
    )
    row = store.get_application(job)
    assert row["status"] == "interview"
    assert row["outcome"] == "Screen scheduled"


def test_outreach_draft_roundtrip(store):
    job = _mk_job(store, "od")
    contact_id = store.upsert_contact(
        job_id=job, name="Ada", role="Founder", source="twitter",
        email="ada@company.com", email_label="guessed", email_confidence=0.5,
        evidence_url=None, note=None,
    )
    store.upsert_outreach(job_id=job, contact_id=contact_id,
                          subject="Quick intro", body="Hey Ada,\n\n...")
    drafts = store.get_outreach(job)
    assert len(drafts) == 1
    assert drafts[0]["subject"] == "Quick intro"
    assert drafts[0]["body"].startswith("Hey Ada")


def test_filters_and_order(store):
    j1 = _mk_job(store, "f1", title="DevOps Engineer")
    j2 = _mk_job(store, "f2", title="Backend Engineer")
    store.update_curation(j1, role_family="devops_sre_platform", geo_tag="confirmed_eligible",
                          geo_confidence=0.9, geo_notes=None, score=80.0,
                          score_breakdown=None)
    store.update_curation(j2, role_family="backend_api", geo_tag="restricted",
                          geo_confidence=0.4, geo_notes=None, score=60.0,
                          score_breakdown=None)
    by_family = store.get_jobs(role_family="devops_sre_platform")
    assert [r["title"] for r in by_family] == ["DevOps Engineer"]
    by_geo = store.get_jobs(geo_tag="restricted")
    assert [r["title"] for r in by_geo] == ["Backend Engineer"]
    ordered = store.get_jobs(order_by="score", desc=True)
    assert ordered[0]["title"] == "DevOps Engineer"


def test_application_update_with_none_preserves_existing_fields(store):
    job = _mk_job(store, "preserve")
    store.update_application(job_id=job, status="applied", applied_at="2026-08-18",
                             resume_path="artifacts/x.pdf", outreach_path="artifacts/x.md",
                             notes="Applied via site", outcome="submitted")
    # status-only update with None values must not wipe artifacts/notes
    store.update_application(job_id=job, status="interview", applied_at=None,
                             resume_path=None, outreach_path=None, notes=None,
                             outcome=None)
    row = store.get_application(job)
    assert row["status"] == "interview"
    assert row["resume_path"] == "artifacts/x.pdf"
    assert row["outreach_path"] == "artifacts/x.md"
    assert row["notes"] == "Applied via site"
    assert row["outcome"] == "submitted"


def test_new_statuses_prepared_replied_ghosted(store):
    job = _mk_job(store, "st")
    for status in ("prepared", "replied", "ghosted"):
        store.update_application(job_id=job, status=status)
        assert store.get_application(job)["status"] == status


def test_meta_roundtrip(store):
    store.set_meta("okhadi_git_sha", "abc123def456")
    assert store.get_meta("okhadi_git_sha") == "abc123def456"
    assert store.get_meta("missing") is None


def test_tailoring_plan_roundtrip(store):
    job = _mk_job(store, "tp")
    plan = {"family": "devops_sre_platform", "jd_keywords": ["terraform", "aws"],
            "summary": "DevOps engineer targeting X", "bullets": {"Syslify": 3}}
    store.set_tailoring_plan(job, plan)
    row = store.get_job(job)
    import json as _json
    assert _json.loads(row["tailoring_plan"])["family"] == "devops_sre_platform"


def test_contact_confidence_label_and_influence(store):
    job = _mk_job(store, "cl")
    store.upsert_contact(
        job_id=job, name="Ada Lovelace", role="Head of Eng", source="team page",
        email="ada@company.com", email_label="public", email_confidence=1.0,
        evidence_url="https://company.com/team", note="Listed on public team page",
        confidence_label="high", hiring_influence="Hiring manager for this role",
        role_is_current=1,
    )
    rows = store.get_contacts(job)
    assert rows[0]["confidence_label"] == "high"
    assert rows[0]["hiring_influence"] == "Hiring manager for this role"
    assert rows[0]["role_is_current"] == 1


def test_source_error_is_stored_honestly(store):
    job = {
        "source": "flaky", "source_id": "err", "external_url": "https://x/e",
        "title": "", "company": "", "location": None, "description": "",
        "description_url": None, "posted_at": None, "salary": None,
        "raw_json": None,
        "source_error": "HTTP 429 from flaky source; no jobs fetched this run",
    }
    store.upsert_job(job)
    rows = [r for r in store.get_jobs() if r["source"] == "flaky"]
    assert len(rows) == 1
    assert rows[0]["source_error"].startswith("HTTP 429")


def _mk_job(store, key, title="Engineer"):
    job = {
        "source": "test", "source_id": key, "external_url": f"https://x/{key}",
        "title": title, "company": "Acme", "location": "Remote",
        "description": "desc", "description_url": None, "posted_at": None,
        "salary": None, "raw_json": None, "source_error": None,
    }
    return store.upsert_job(job)
