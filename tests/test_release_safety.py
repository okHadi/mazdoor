"""Release-safety regressions found during parent integration review."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mazdoor import cli, db, pipeline, profile, research, resume


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_sync_repository_fetches_and_fast_forwards_clean_clone(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    clone = tmp_path / "clone"
    _git(["init", "--bare", str(remote)], tmp_path)
    _git(["init", "-b", "main", str(seed)], tmp_path)
    _git(["config", "user.name", "Test"], seed)
    _git(["config", "user.email", "test@example.com"], seed)
    (seed / "evidence.txt").write_text("v1")
    _git(["add", "evidence.txt"], seed)
    _git(["commit", "-m", "v1"], seed)
    _git(["remote", "add", "origin", str(remote)], seed)
    _git(["push", "-u", "origin", "main"], seed)
    _git(["symbolic-ref", "HEAD", "refs/heads/main"], remote)
    _git(["clone", str(remote), str(clone)], tmp_path)

    (seed / "evidence.txt").write_text("v2")
    _git(["commit", "-am", "v2"], seed)
    _git(["push"], seed)
    wanted = _git(["rev-parse", "HEAD"], seed)

    assert profile.sync_repository(clone) == wanted
    assert (clone / "evidence.txt").read_text() == "v2"


def test_sync_repository_refuses_dirty_worktree(tmp_path):
    repo = tmp_path / "repo"
    _git(["init", "-b", "main", str(repo)], tmp_path)
    _git(["config", "user.name", "Test"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    (repo / "evidence.txt").write_text("clean")
    _git(["add", "evidence.txt"], repo)
    _git(["commit", "-m", "clean"], repo)
    (repo / "evidence.txt").write_text("dirty")

    with pytest.raises(profile.SourceSyncError, match="dirty"):
        profile.sync_repository(repo)


def test_job_records_exact_source_commit(tmp_path):
    store = db.Store(tmp_path / "commit.db")
    try:
        job_id = store.upsert_job({
            "source": "verified", "source_id": "one",
            "external_url": "https://example.com/job",
            "title": "Backend Engineer", "company": "Example",
            "location": "Pakistan", "description": "Node.js",
            "description_url": "https://example.com/job", "posted_at": None,
            "salary": None, "raw_json": None, "source_error": None,
        })
        store.set_job_source_commit(job_id, "abc123")
        assert store.get_job(job_id)["source_commit"] == "abc123"
    finally:
        store.close()


def test_research_never_guesses_company_domain_from_name():
    job = {
        "company": "Totally Different Holdings",
        "external_url": "https://pk.linkedin.com/jobs/view/123",
        "description_url": "https://pk.linkedin.com/jobs/view/123",
    }
    assert research._candidate_urls(job) == []


def test_research_uses_only_explicit_official_company_url():
    job = {
        "company": "Acme",
        "external_url": "https://pk.linkedin.com/jobs/view/123",
        "company_url": "https://engineering.acme.example/team",
    }
    urls = research._candidate_urls(job)
    assert urls
    assert all("engineering.acme.example" in url for url in urls)


def test_jd_keyword_surfacing_requires_canonical_evidence():
    p = profile.load()
    text = "Kafka Jenkins Redis Prometheus Grafana Argo Terraform AWS"
    matched = resume.jd_keywords_matched(p, "devops_sre_platform", text)
    assert "terraform" in matched
    assert "aws" in matched
    for unsupported in ("kafka", "jenkins", "redis", "prometheus", "grafana", "argo"):
        assert unsupported not in matched


def test_generate_accepts_string_path(tmp_path):
    path = str(tmp_path / "resume.pdf")
    result = resume.generate(path, family="backend_api", job={
        "title": "Backend Engineer", "company": "Acme",
        "description": "Node.js AWS REST APIs",
    })
    assert Path(result).exists()
    assert (tmp_path / "resume_tailoring.md").exists()


def test_pakistan_listing_is_not_restricted_by_timezone_overlap():
    from mazdoor.scoring import geo_eligibility

    result = geo_eligibility(
        "Pakistan",
        "Remote role requiring four hours of CET timezone overlap.",
    )
    assert result["tag"] == "confirmed_eligible"


def test_explicit_legal_region_restriction_beats_listing_location():
    from mazdoor.scoring import geo_eligibility

    result = geo_eligibility(
        "Pakistan",
        "Remote role. United States only. Must be authorized to work in the US.",
    )
    assert result["tag"] == "restricted"


def test_candidates_syncs_source_and_stamps_each_evaluation(tmp_path, monkeypatch):
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([{
        "source": "verified", "source_id": "one",
        "external_url": "https://example.com/job",
        "title": "Backend Engineer", "company": "Example",
        "location": "Pakistan", "description": (
            "Node.js AWS REST APIs Python TypeScript automation serverless "
            "event-driven microservices SQL MongoDB backend integration"
        ),
        "description_url": "https://example.com/job", "posted_at": None,
        "salary": None, "raw_json": None, "source_error": None,
    }]))
    monkeypatch.setattr(profile, "sync_repository", lambda: "sha-candidates")
    args = SimpleNamespace(
        db=str(tmp_path / "jobs.db"), artifacts=str(tmp_path / "artifacts"),
        file=str(candidates),
    )
    assert cli.cmd_candidates(args) == 0
    store = db.Store(args.db)
    try:
        assert store.get_meta("okhadi_git_sha") == "sha-candidates"
        assert store.get_jobs()[0]["source_commit"] == "sha-candidates"
    finally:
        store.close()


def test_finalize_stamps_commit_used_for_each_resume(tmp_path, monkeypatch):
    store = db.Store(tmp_path / "finalize.db")
    try:
        job_id = store.upsert_job({
            "source": "verified", "source_id": "one",
            "external_url": "https://example.com/job",
            "title": "Backend Engineer", "company": "Example",
            "location": "Pakistan", "description": "Node.js",
            "description_url": "https://example.com/job", "posted_at": None,
            "salary": None, "raw_json": None, "source_error": None,
        })
        store.update_curation(
            job_id, role_family="backend_api", geo_tag="confirmed_eligible",
            geo_confidence=1.0, geo_notes="Pakistan listing", score=80,
            score_breakdown=None, rationale="fit",
        )
        monkeypatch.setattr(pipeline, "_process_job", lambda *args: (1, 0))
        result = pipeline.finalize(
            store, artifacts_dir=tmp_path / "artifacts",
            okhadi_sha="sha-finalize",
        )
        assert result["resumes_generated"] == 1
        assert store.get_meta("okhadi_git_sha") == "sha-finalize"
        assert store.get_job(job_id)["source_commit"] == "sha-finalize"
    finally:
        store.close()


def test_structured_research_payload_persists_evidence_and_contact(tmp_path):
    store = db.Store(tmp_path / "research.db")
    try:
        job_id = store.upsert_job({
            "source": "verified", "source_id": "one",
            "external_url": "https://jobs.example/job",
            "title": "Backend Engineer", "company": "Example",
            "location": "Pakistan", "description": "Node.js",
            "description_url": "https://jobs.example/job", "posted_at": None,
            "salary": None, "raw_json": None, "source_error": None,
        })
        record = {
            "job_id": job_id,
            "company": {
                "official_domain": "example.com",
                "summary": "Global backend company.",
                "hook": "Its event pipeline maps to Hadi's AWS work.",
            },
            "geo": {
                "tag": "confirmed_eligible", "confidence": 0.95,
                "summary": "Fact: the role explicitly lists Pakistan.",
                "evidence_urls": ["https://jobs.example/job", "https://example.com/about"],
            },
            "contacts": [{
                "name": "Mira", "role": "Engineering Manager",
                "linkedin_url": "https://linkedin.com/in/mira",
                "email": None, "email_status": "unverified",
                "source_url": "https://example.com/team",
            }],
        }
        assert research.ingest_research(store, [record]) == 1
        details = store.jobs_with_details()[0]
        assert details["research"]["company_summary"].startswith("Global backend")
        assert "event pipeline" in details["research"]["evidence_notes"]
        assert "example.com/about" in details["research"]["evidence_urls"]
        assert details["geo_tag"] == "confirmed_eligible"
        assert "jobs.example/job" in details["geo_notes"]
        assert details["contacts"][0]["name"] == "Mira"
        assert details["contacts"][0]["evidence_url"] == "https://example.com/team"
        assert details["contacts"][0]["email_label"] == "unverified"
        research.ingest_research(store, [record])
        assert len(store.get_contacts(job_id)) == 1
    finally:
        store.close()


def test_contact_discovery_never_synthesizes_inboxes(monkeypatch):
    engine = research.ResearchEngine()
    monkeypatch.setattr(
        engine, "fetch_page", lambda url: (200, "<html><p>No email here</p></html>"),
    )
    contacts = engine.find_contacts({
        "company": "Example", "company_url": "https://example.com",
        "external_url": "https://jobs.example/job", "description_url": None,
    })
    assert contacts == []


def test_named_public_contact_gets_dm_draft_without_email(tmp_path):
    store = db.Store(tmp_path / "draft.db")
    try:
        job_id = store.upsert_job({
            "source": "verified", "source_id": "one",
            "external_url": "https://jobs.example/job",
            "title": "Backend Engineer", "company": "Example",
            "location": "Pakistan", "description": "Node.js AWS REST APIs",
            "description_url": "https://jobs.example/job", "posted_at": None,
            "salary": None, "raw_json": None, "source_error": None,
        })
        store.update_curation(
            job_id, role_family="backend_api", geo_tag="confirmed_eligible",
            geo_confidence=0.95, geo_notes="Pakistan listing", score=80,
            score_breakdown=None, rationale="fit",
        )
        store.upsert_company_research(
            job_id, "Global backend company.",
            ["https://example.com/about"],
            "The event pipeline maps directly to Hadi's AWS work.\nFact: Pakistan eligible.",
            None, None, "Fact: Pakistan eligible.",
        )
        store.upsert_contact(
            job_id, name="Mira", role="CEO", source="company about page",
            email=None, email_label="unverified", email_confidence=0.0,
            evidence_url="https://example.com/about", note=None,
            confidence_label="high", hiring_influence="executive sponsor",
            role_is_current=1,
        )
        resumes, drafts = pipeline._process_job(
            store, job_id, artifacts_dir=tmp_path / "artifacts",
        )
        assert resumes == 1
        assert drafts == 1
        body = store.get_outreach(job_id)[0]["body"]
        assert "Hey Mira," in body
        assert "event pipeline maps directly" in body
        assert "Saw your work as CEO at Example." not in body
        assert "Hope to talk to you :)" in body
        assert "lead CEO" not in body
    finally:
        store.close()


def test_resume_filenames_are_unique_per_job_title(tmp_path):
    first = resume.default_filename(
        "ai_first_product", "IgniteTech", tmp_path,
        title="Senior Software Engineer",
    )
    second = resume.default_filename(
        "ai_first_product", "IgniteTech", tmp_path,
        title="Customer Enablement Engineer",
    )
    assert first != second


def test_verifier_requires_expected_pdf_count(tmp_path):
    store = db.Store(tmp_path / "verify.db")
    try:
        job_id = store.upsert_job({
            "source": "verified", "source_id": "one",
            "external_url": "https://jobs.example/job",
            "title": "Backend Engineer", "company": "Example",
            "location": "Pakistan", "description": "Node.js",
            "description_url": "https://jobs.example/job", "posted_at": None,
            "salary": None, "raw_json": None, "source_error": None,
        })
        store.update_curation(
            job_id, role_family="backend_api", geo_tag="confirmed_eligible",
            geo_confidence=0.95, geo_notes="Pakistan listing", score=80,
            score_breakdown=None, rationale="fit",
        )
    finally:
        store.close()
    args = SimpleNamespace(
        db=str(tmp_path / "verify.db"), artifacts=str(tmp_path / "artifacts"),
        expect=1, render=None,
    )
    assert cli.cmd_verify(args) == 1


def test_resume_text_is_focused_and_readable():
    text = resume.render_text(
        family="ai_first_product",
        job={
            "title": "AI Product Engineer", "company": "Example",
            "description": "Claude Code Codex AI agents Python AWS customer product",
        },
    )
    lines = text.splitlines()
    bullets = [line for line in lines if line.startswith("- ")]
    experience_headers = [
        line for line in lines
        if "(" in line and any(company in line for company in (
            "Syslify", "Parhlai", "Vfairs", "Imagine.art / Vyro.ai",
        ))
    ]
    assert "+923****3633" not in text
    assert "Targeting AI Product Engineer at Example" not in text
    assert "Projects" not in lines
    assert len(bullets) <= 10
    assert len(experience_headers) <= 4
    assert "Claude Code" in text


def test_resume_pdf_keeps_readable_font_floor(tmp_path):
    path = resume.generate(
        tmp_path / "focused.pdf", family="backend_api",
        job={
            "title": "Senior Integration Engineer", "company": "Example",
            "description": "AWS Lambda Node.js Python serverless event-driven APIs",
        },
    )
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) == 1
    assert len(text) < 4500
    assert "booked revenue" in text.lower()
    assert resume._STYLES["body"].fontSize >= 9.0
    assert resume._STYLES["bullet"].fontSize >= 9.0
    flowables = resume._flowables(resume.render_text(
        family="backend_api",
        job={"title": "Backend Engineer", "company": "Example", "description": "AWS"},
    ))
    assert flowables[0].style.name == "name"
    assert flowables[1].style.name == "contact"
