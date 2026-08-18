"""Tests for the canonical profile (single source of truth, no fabrication)."""

from mazdoor import profile


def test_name_and_contact():
    p = profile.load()
    assert p["name"] == "Hadi Khan"
    assert p["email"] == "hello@mhadi.dev"
    assert "linkedin.com/in/okhadi" in p["links"]["linkedin"].lower()
    assert "github.com/okhadi" in p["links"]["github"].lower()
    assert p["links"]["website"].replace("www.", "") == "https://mhadi.dev"


def test_parhlai_metrics_are_verified_wording():
    p = profile.load()
    parhlai = [r for r in p["experience"] if r["company"] == "Parhlai"][0]
    assert parhlai["metrics"]["users"] == 8281
    assert parhlai["metrics"]["mau"] == 5276
    # Booked revenue, never ARR
    assert parhlai["metrics"]["booked_revenue_pkr"] == 500079
    assert "arr" not in parhlai["metrics"].keys()
    assert parhlai["metrics"]["funding_pkr"] == 1000000
    assert parhlai["metrics"]["impressions"] == 4570000
    assert parhlai["metrics"]["clicks"] == 162233


def test_metrics_match_okhadi_canonical_source():
    """Every metric must match the okHadi site/content/jobs files exactly."""
    p = profile.load()
    # Spot-check against the canonical wording from okHadi
    text = p["experience_evidence_text"]
    assert "8,281" in text
    assert "5,276" in text
    assert "PKR 500,079" in text
    assert "4.57M" in text or "4,570,000" in text
    assert "162,233" in text
    assert "100+ AWS accounts" in text
    assert "Control Tower" in text


def test_role_families_defined():
    p = profile.load()
    families = p["role_families"]
    assert "devops_sre_platform" in families
    assert "backend_api" in families
    assert "product_engineering" in families
    assert "ai_first_product" in families
    assert "technical_pm" in families
    assert "ai_training" in families


def test_every_family_has_keywords_and_weight():
    p = profile.load()
    for fam, spec in p["role_families"].items():
        assert spec["keywords"], fam
        assert 0 < spec["weight"] <= 1, fam


def test_experience_has_bullets_for_every_company():
    p = profile.load()
    companies = {r["company"] for r in p["experience"]}
    assert {"Syslify", "Parhlai", "Imagine.art / Vyro.ai", "Vfairs"} <= companies
    for role in p["experience"]:
        for block in role["titles"]:
            assert block["bullets"], f"{role['company']} / {block['title']}"


def test_education_present():
    p = profile.load()
    assert "NUST" in p["education"][0]["school"] or "NUST" in p["education"][0]["degree"]


def test_projects_are_real_okhadi_projects():
    p = profile.load()
    names = {pr["name"] for pr in p["projects"]}
    assert "QALMS" in names
    assert "Dhoondlai" in names
    assert "DockerServicesStatus" in names
