"""Tests for the job collector: honest sources, no fabrication, error capture."""

import pytest

from mazdoor import collect


def test_remotive_normalizer_maps_fields():
    raw = {
        "id": 12345,
        "title": "DevOps Engineer",
        "company_name": "Acme Remote",
        "candidate_required_location": "Worldwide",
        "url": "https://remotive.com/remote-jobs/devops-engineer-12345",
        "description": "We are looking for a DevOps Engineer... Terraform, AWS",
        "publication_date": "2026-08-10T10:00:00.000Z",
        "salary": "100k-130k",
    }
    job = collect.normalize_remotive(raw)
    assert job["source"] == "remotive"
    assert job["source_id"] == "12345"
    assert job["title"] == "DevOps Engineer"
    assert job["company"] == "Acme Remote"
    assert job["external_url"].startswith("https://remotive.com")
    assert job["description"] == "We are looking for a DevOps Engineer... Terraform, AWS"
    assert job["raw_json"] is not None


def test_remotive_normalizer_never_fabricates_missing_fields():
    raw = {"id": 1, "title": "X", "company_name": "Y"}
    job = collect.normalize_remotive(raw)
    assert job["external_url"]  # derived from id, not fabricated
    assert job["description"] == ""
    assert job["location"] is None or job["location"] == ""
    assert job["salary"] is None


def test_greenhouse_normalizer_maps_fields():
    raw = {
        "id": 8503792002,
        "title": "Platform Engineer",
        "company_name": "GitLab",
        "location": {"name": "Remote"},
        "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/8503792002",
        "content": "<p>You will build platform tooling with Terraform.</p>",
        "updated_at": "2026-08-12",
    }
    job = collect.normalize_greenhouse(raw, board="gitlab")
    assert job["source"] == "greenhouse"
    assert job["source_id"] == "8503792002"
    assert job["title"] == "Platform Engineer"
    assert "Terraform" in job["description"]
    assert "gitlab" in job["external_url"]


def test_collector_returns_errors_honestly(monkeypatch):
    """A failing source must produce a recorded error, not fabricated jobs."""

    def fake_get(*args, **kwargs):
        raise Exception("HTTP 429 Too Many Requests")

    monkeypatch.setattr(collect.requests, "get", fake_get)
    runner = collect.Collector(timeout=1)
    result = runner.fetch_source("remotive", {"search": "devops"})
    assert result["ok"] is False
    assert "429" in result["error"]
    assert result["jobs"] == []


def test_curate_selects_target_count_and_records_scores(monkeypatch):
    """curate() must pick jobs, score them, and keep evidence; never invent jobs."""
    jobs = []
    for i in range(12):
        jobs.append({
            "source": "test", "source_id": f"j{i}", "external_url": f"https://x/{i}",
            "title": "DevOps Engineer" if i % 2 == 0 else "Frontend Designer",
            "company": f"Co{i}", "location": "Worldwide", "description": (
                "Terraform, AWS, Kubernetes, CI/CD" if i % 2 == 0
                else "Figma, CSS animations, landing pages"),
            "description_url": None, "posted_at": None, "salary": None,
            "raw_json": None, "source_error": None,
        })
    curated = collect.curate(jobs, target=5)
    assert len(curated) == 5
    titles = [c["title"] for c in curated]
    assert all("DevOps" in t for t in titles), "frontend-heavy roles must lose curation"
    for c in curated:
        assert 0 <= c["score"] <= 100
        assert c["role_family"]
        assert c["geo_tag"]


def test_curate_requires_minimum_descriptions():
    jobs = [{
        "source": "test", "source_id": "x", "external_url": "https://x",
        "title": "Engineer", "company": "Co", "location": "Remote", "description": "",
        "description_url": None, "posted_at": None, "salary": None,
        "raw_json": None, "source_error": None,
    }]
    curated = collect.curate(jobs, target=5)
    assert curated == []
