"""End-to-end pipeline test with a mock source: collect, curate, research,
score, resume, outreach, persist. No live network, no fabrication."""

import json

import pytest

from mazdoor import pipeline


class FakeSource:
    """Deterministic fake remote source returning two job postings."""

    def fetch(self):
        return {
            "ok": True,
            "source": "fake-remote",
            "jobs": [
                {
                    "source": "fake-remote", "source_id": "f1",
                    "external_url": "https://fake.example/jobs/1",
                    "title": "Senior DevOps Engineer",
                    "company": "FakeCloud",
                    "location": "Worldwide",
                    "description": (
                        "Remote DevOps role: Terraform across AWS accounts, "
                        "Kubernetes, CI/CD, Control Tower, OpenShift."
                    ),
                    "description_url": "https://fake.example/jobs/1",
                    "posted_at": "2026-08-10", "salary": None,
                    "raw_json": json.dumps({"id": "f1"}),
                    "source_error": None,
                },
                {
                    "source": "fake-remote", "source_id": "f2",
                    "external_url": "https://fake.example/jobs/2",
                    "title": "Frontend Designer",
                    "company": "FakeCloud",
                    "location": "Worldwide",
                    "description": "Figma mockups and CSS landing pages.",
                    "description_url": None, "posted_at": None, "salary": None,
                    "raw_json": None, "source_error": None,
                },
            ],
        }


def test_pipeline_runs_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "capture_okhadi_sha", lambda: "sha-0123456789")
    state = pipeline.run(
        db_path=tmp_path / "pipeline.db",
        artifacts_dir=tmp_path / "artifacts",
        sources=[FakeSource()],
        target=1,
        research_fn=lambda job: {
            "company_summary": "Cloud infra startup",
            "evidence_urls": json.dumps(["https://fake.example/about"]),
            "evidence_notes": "Public about page",
            "funding": "Seed",
            "headcount": "20",
            "remote_policy": "Remote-first worldwide",
            "contacts": [{
                "name": "Mira", "role": "CTO", "source": "public team page",
                "email": "mira@fake.example", "email_label": "public",
                "email_confidence": 1.0, "evidence_url": "https://fake.example/team",
                "note": "Listed on team page",
                "confidence_label": "high", "hiring_influence": "Hiring manager for this role",
                "role_is_current": 1,
            }],
        },
    )
    assert state["jobs_collected"] == 2
    assert state["jobs_curated"] == 1
    assert state["jobs_researched"] == 1
    assert state["resumes_generated"] == 1
    assert state["drafts_generated"] >= 1

    from mazdoor import db
    store = db.Store(tmp_path / "pipeline.db")
    jobs = store.get_jobs()
    assert len(jobs) == 2  # both raw jobs persisted (errors/skips honest)
    curated = [j for j in jobs if j["score"] is not None]
    assert len(curated) == 1
    assert curated[0]["title"] == "Senior DevOps Engineer"
    # okHadi source SHA recorded in meta
    assert store.get_meta("okhadi_git_sha") == "sha-0123456789"
    # tailoring plan persisted per curated job
    assert curated[0]["tailoring_plan"] is not None
    # contact has confidence label + hiring influence
    contacts = store.get_contacts(curated[0]["id"])
    assert contacts[0]["confidence_label"] == "high"
    assert contacts[0]["hiring_influence"] == "Hiring manager for this role"
    # artifacts exist
    pdfs = list((tmp_path / "artifacts").glob("*.pdf"))
    assert pdfs, "resume PDF must exist"
    drafts = list((tmp_path / "artifacts").glob("*.md"))
    assert drafts, "outreach draft must exist"
    store.close()


def test_pipeline_records_source_failures(tmp_path):
    class BrokenSource:
        def fetch(self):
            return {
                "ok": False, "source": "broken",
                "error": "Connection refused",
                "jobs": [],
            }

    state = pipeline.run(
        db_path=tmp_path / "p.db",
        artifacts_dir=tmp_path / "a",
        sources=[BrokenSource()],
        target=1,
        research_fn=lambda job: {},
    )
    assert state["source_errors"] == ["broken: Connection refused"]
    assert state["jobs_curated"] == 0
    assert state["resumes_generated"] == 0
