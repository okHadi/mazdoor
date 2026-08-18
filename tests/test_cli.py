"""CLI integration test: candidates -> research -> finalize -> verify -> export.

Exercises the exact ingest contract documented in docs/OPERATIONS.md with
synthetic data (the real first-10 batch is ingested by the parent).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run(args, cwd):
    repo = str(Path(__file__).resolve().parents[1])
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = repo + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.run(
        [sys.executable, "-m", "mazdoor.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=env,
    )


CANDIDATES = [
    {
        "source": "verified", "source_id": "synthetic-1",
        "external_url": "https://example.com/jobs/1",
        "title": "Senior DevOps Engineer",
        "company": "SyntheticCloud",
        "location": "Worldwide",
        "description": (
            "Remote DevOps role: Terraform across AWS accounts, Kubernetes, "
            "CI/CD with GitHub Actions, Docker, Linux, Control Tower, OpenShift."
        ),
        "description_url": "https://example.com/jobs/1",
        "posted_at": "2026-08-18", "salary": None, "raw_json": None,
        "source_error": None,
    },
    {
        "source": "verified", "source_id": "synthetic-2",
        "external_url": "https://example.com/jobs/2",
        "title": "AI Product Engineer",
        "company": "SyntheticAI",
        "location": "Pakistan",
        "description": (
            "Build AI features with Claude Code and Codex agents, LLM APIs, "
            "prompt engineering, RAG, agentic workflows."
        ),
        "description_url": "https://example.com/jobs/2",
        "posted_at": "2026-08-17", "salary": None, "raw_json": None,
        "source_error": None,
    },
]

RESEARCH = [
    {
        "job_id": 1,
        "company_summary": "SyntheticCloud is a cloud infra provider",
        "evidence_urls": json.dumps(["https://example.com/about"]),
        "evidence_notes": "careers page (2026-08-18): hiring worldwide including APAC",
        "funding": "Series B", "headcount": "120 employees",
        "remote_policy": "Remote-first worldwide",
        "geo": {"tag": "confirmed_eligible", "confidence": 0.85,
                "citations": [{"url": "https://example.com/careers",
                               "accessed": "2026-08-18",
                               "note": "hiring worldwide including APAC"}]},
        "contacts": [{
            "name": "Mira Chen", "role": "Head of Platform",
            "source": "team page", "email": "mira@example.com",
            "email_label": "public", "email_confidence": 0.95,
            "evidence_url": "https://example.com/team",
            "note": "listed on public team page",
            "confidence_label": "high",
            "hiring_influence": "hiring manager for this role",
            "role_is_current": 1,
        }],
    },
    {
        "job_id": 2,
        "company_summary": "SyntheticAI builds AI products",
        "evidence_urls": json.dumps(["https://example.ai/about"]),
        "evidence_notes": "about page (2026-08-18): team across Pakistan and US",
        "funding": None, "headcount": None, "remote_policy": None,
        "geo": None,
        "contacts": [],
    },
]


def test_cli_full_ingest_contract(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "candidates.json").write_text(json.dumps(CANDIDATES))
    (data / "research.json").write_text(json.dumps(RESEARCH))

    db = data / "mazdoor.db"
    artifacts = tmp_path / "artifacts"

    r = _run(["candidates", "--db", str(db), "--artifacts", str(artifacts),
              "--file", str(data / "candidates.json")], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "curated 2" in r.stdout

    r = _run(["research", "--db", str(db), "--file", str(data / "research.json")],
             cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "applied research to 2 jobs" in r.stdout

    r = _run(["finalize", "--db", str(db), "--artifacts", str(artifacts)], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    state = json.loads(r.stdout)
    assert state["resumes_generated"] == 2
    assert state["drafts_generated"] == 1  # only the job with a real contact

    r = _run(["verify", "--db", str(db), "--artifacts", str(artifacts), "--expect", "2"],
             cwd=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr

    r = _run(["export", "--db", str(db), "--artifacts", str(artifacts),
              "--out", str(data / "jobs.json")], cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    exported = json.loads((data / "jobs.json").read_text())
    assert len(exported["jobs"]) == 2

    pdfs = list(artifacts.glob("*.pdf"))
    assert len(pdfs) == 2
    drafts = list(artifacts.glob("outreach_*.md"))
    assert len(drafts) == 1
    draft = drafts[0].read_text()
    assert "Hey Mira," in draft
    assert "mira@example.com" in draft
    assert "public" in draft
