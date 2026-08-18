"""Tests for role-family classification and match scoring."""

from mazdoor import scoring
from mazdoor.profile import load


FAMILIES = {
    "devops_sre_platform",
    "backend_api",
    "product_engineering",
    "ai_first_product",
    "technical_pm",
    "ai_training",
}


def test_classify_devops_titles():
    for title in [
        "Senior DevOps Engineer",
        "SRE",
        "Site Reliability Engineer",
        "Platform Engineer",
        "Cloud Infrastructure Engineer",
        "Staff SRE (Remote)",
    ]:
        fam = scoring.classify_role(title, "Kubernetes, Terraform, AWS, CI/CD")
        assert fam == "devops_sre_platform", title


def test_classify_backend_titles():
    for title in ["Backend Engineer", "API Engineer", "Senior Backend Developer (Python)",
                  "Automation Engineer", "Integration Engineer"]:
        fam = scoring.classify_role(title, "Python, FastAPI, PostgreSQL")
        assert fam == "backend_api", title


def test_classify_ai_first_product():
    for title in ["AI Engineer", "AI Product Engineer", "Prompt Engineer",
                  "AI Application Engineer"]:
        fam = scoring.classify_role(title, "Claude Code, Codex, AI agents, LLM APIs")
        assert fam == "ai_first_product", title


def test_classify_technical_pm():
    for title in ["Technical Product Manager", "Product Owner", "Sprint Lead",
                  "Product Manager (AI)", "AI Product Manager"]:
        fam = scoring.classify_role(title, "roadmap, sprints, stakeholders")
        assert fam == "technical_pm", title


def test_classify_ai_training_contracts():
    for title in ["AI Trainer", "Coding Evaluator", "Code Review Evaluator (Contract)",
                  "AI Training Contractor", "RLHF Data Annotator (Coding)"]:
        fam = scoring.classify_role(title, "evaluate model outputs, write code samples")
        assert fam == "ai_training", title


def test_frontend_heavy_is_penalized_but_not_excluded():
    desc = "Build beautiful React UIs with CSS animations, Figma handoff, and design systems"
    fam = scoring.classify_role("Frontend Engineer", desc)
    # Never excluded based on title alone, but penalized in scoring
    assert fam in FAMILIES
    breakdown = scoring.score_job(title="Frontend Engineer", description=desc,
                                  company="X", profile=load())
    assert breakdown["frontend_penalty"] > 0
    assert breakdown["score"] < 50


def test_adjacent_title_not_excluded_by_title_alone():
    # "Software Engineer" with infra-heavy description must classify as devops family
    fam = scoring.classify_role("Software Engineer",
                                "AWS, Terraform, Kubernetes, CI/CD pipelines, Linux")
    assert fam == "devops_sre_platform"
    # "Product Engineer" with AI-agent description
    fam2 = scoring.classify_role("Product Engineer",
                                 "Build features using Claude Code and Codex agents")
    assert fam2 == "ai_first_product"


def test_cloud_operations_title_beats_ai_assisted_description():
    title = "Senior Cloud Operations Engineer"
    desc = "Use AI-assisted troubleshooting and agentic automation in AWS operations"
    assert scoring.classify_role(title, desc) == "devops_sre_platform"


def test_match_score_maps_to_family_weights():
    p = load()
    res = scoring.score_job(
        title="Senior DevOps Engineer",
        description=(
            "AWS Control Tower, Terraform across 100+ accounts, Kubernetes, "
            "CI/CD with GitHub Actions, Docker, Linux, OpenShift"
        ),
        company="Syslify-like", profile=p,
    )
    assert res["family"] == "devops_sre_platform"
    assert res["score"] >= 80


def test_mid_seniority_preferred():
    p = load()
    junior = scoring.score_job(title="Junior DevOps Engineer",
                               description="AWS, Terraform, CI/CD", company="X", profile=p)
    senior = scoring.score_job(title="Senior DevOps Engineer",
                               description="AWS, Terraform, CI/CD", company="X", profile=p)
    assert senior["score"] >= junior["score"]


def test_geo_research_classification_rules():
    g = scoring.geo_eligibility(
        location="Worldwide",
        description="This is a fully remote role open to candidates worldwide",
    )
    assert g["tag"] == "confirmed_eligible"

    g = scoring.geo_eligibility(
        location="Europe",
        description="Remote within Europe (CET +/- 2h)",
    )
    assert g["tag"] in ("possible_exception", "restricted")

    g = scoring.geo_eligibility(
        location="US Only",
        description="Must be authorized to work in the US without sponsorship",
    )
    assert g["tag"] == "restricted"

    g = scoring.geo_eligibility(location="Remote", description="")
    assert g["tag"] in ("unknown", "possible_exception")

    g = scoring.geo_eligibility(
        location="Remote (Pakistan-friendly)",
        description="Open to candidates in Pakistan, India, and UAE",
    )
    assert g["tag"] == "confirmed_eligible"


def test_citations_and_confidence_required_for_geo():
    g = scoring.geo_eligibility("Worldwide", "Remote worldwide")
    assert g["citations"]
    assert 0 <= g["confidence"] <= 1


def test_remote_first_or_fully_remote_alone_is_not_confirmed():
    """'Fully remote' / 'remote-first' / '100% remote' without an explicit
    worldwide/anywhere/Pakistan/APAC term must NOT confirm eligibility."""
    for loc, desc in [
        ("Remote", "Fully remote, remote-first company"),
        ("Remote", "100% remote. Remote-first culture."),
        ("Remote - Global", "Remote-first team across the company"),
    ]:
        g = scoring.geo_eligibility(loc, desc)
        assert g["tag"] != "confirmed_eligible", (loc, desc)


def test_only_explicit_terms_confirm_from_jd():
    for loc, desc in [
        ("Worldwide", "Open to candidates worldwide"),
        ("Anywhere", "Work from anywhere"),
        ("Remote (Pakistan-friendly)", "Hiring in Pakistan, India, UAE"),
        ("APAC", "Remote across APAC timezones"),
    ]:
        g = scoring.geo_eligibility(loc, desc)
        assert g["tag"] == "confirmed_eligible", (loc, desc)
