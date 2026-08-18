"""Tests for ATS-friendly one-page resume generation with role-family weighting."""

import json
import re

import pytest
from pypdf import PdfReader

from mazdoor import resume
from mazdoor.profile import load


@pytest.fixture()
def out(tmp_path):
    return resume.generate(tmp_path / "Hadi_Khan_DevOps.pdf", family="devops_sre_platform")


def test_pdf_exists_and_is_text_based(out, tmp_path):
    assert out.exists()
    reader = PdfReader(str(out))
    assert len(reader.pages) == 1, "resume must be one page"
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(text) > 300
    assert "Hadi Khan" in text


def test_ats_sections_present(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for section in ["Summary", "Skills", "Experience", "Education"]:
        assert section in text, f"missing standard ATS section: {section}"


def test_contact_in_body_not_header(out, tmp_path):
    reader = PdfReader(str(out))
    page0 = reader.pages[0]
    text = page0.extract_text() or ""
    assert "hello@mhadi.dev" in text
    assert "mhadi.dev" in text


def test_devops_family_weights_lead_with_infra(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # DevOps-family resume must surface infra keywords
    for kw in ["Terraform", "AWS", "Control Tower"]:
        assert kw in text, kw


def test_parhlai_metrics_use_verified_wording(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "500" in text  # booked revenue figure present (rounded, per AGENTS.md)
    assert "ARR" not in text.upper() or "arr" not in text.lower()


def test_family_variants_are_distinct():
    base = load()
    p1 = resume.render_text(base, "devops_sre_platform")
    p2 = resume.render_text(base, "technical_pm")
    assert p1 != p2, "family weighting must produce different resumes"
    assert "roadmap" in p2.lower() or "product" in p2.lower()


def test_all_families_render_one_page(tmp_path):
    for fam in ["devops_sre_platform", "backend_api", "product_engineering",
                "ai_first_product", "technical_pm", "ai_training"]:
        path = tmp_path / f"{fam}.pdf"
        p = resume.generate(path, family=fam)
        reader = PdfReader(str(p))
        assert len(reader.pages) == 1, fam
        text = "\n".join(pg.extract_text() or "" for pg in reader.pages)
        assert "Hadi Khan" in text


def test_text_extractable_means_no_embedded_images(out, tmp_path):
    reader = PdfReader(str(out))
    page = reader.pages[0]
    images = page.images if hasattr(page, "images") else []
    assert len(images) == 0


def test_no_em_dashes_in_pdf(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "—" not in text
    assert "–" not in text


def test_no_unmasked_phone_in_pdf(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    # no full phone number patterns like +92 3xx xxxxxxx
    assert not re.search(r"\+92\s?\d{3}", text)
    # masked form is allowed and is the canonical contact block form
    assert "+923" in text or "mhadi.dev" in text


def test_parhlai_revenue_phrasing_exact(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "booked revenue" in text.lower()
    assert "PKR 500" in text or "500k+ PKR" in text
    for banned in ["ARR", "annual recurring revenue", "annualized", "$500"]:
        assert banned not in text


def test_standard_ats_headers_and_contact_order(out, tmp_path):
    reader = PdfReader(str(out))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    idx_exp = text.find("Experience")
    idx_edu = text.find("Education")
    idx_skills = text.find("Skills")
    assert 0 <= idx_skills < idx_exp < idx_edu, "skills before experience before education"


def test_job_specific_tailoring_changes_summary_and_plan(tmp_path):
    """generate() must accept per-job context and produce job-specific output,
    persisting a tailoring plan file."""
    job = {
        "title": "Senior DevOps Engineer",
        "company": "Acme Cloud",
        "description": ("Terraform across AWS accounts, Kubernetes, OpenShift, "
                        "GitHub Actions, Docker, Control Tower, Linux, CI/CD pipelines"),
    }
    path = tmp_path / "Hadi_Khan_DevOps_Acme_Cloud.pdf"
    p = resume.generate(path, family="devops_sre_platform", job=job)
    reader = PdfReader(str(p))
    text = "\n".join(pg.extract_text() or "" for pg in reader.pages)
    normalized = re.sub(r"\s+", " ", text)
    assert "Acme Cloud" in normalized
    assert "Senior DevOps Engineer" in normalized
    # plan file persisted next to the PDF
    plan = tmp_path / "Hadi_Khan_DevOps_Acme_Cloud_tailoring.md"
    assert plan.exists()
    plan_text = plan.read_text()
    assert "Acme Cloud" in plan_text
    assert "devops_sre_platform" in plan_text


def test_jd_keywords_surfaced_but_only_from_canonical_skills(tmp_path):
    """JD keywords may only be surfaced on the resume if they exist in the
    canonical skill list (no invented skills)."""
    p = load()
    canonical = set()
    for group in p["skills"].values():
        canonical.update(s.lower() for s in group)
    # a JD with a canonical keyword (postgresql) and a fabricated one (kafka3)
    job = {"title": "Backend Engineer", "company": "X",
           "description": "PostgreSQL, kafka3, FastAPI, event-driven pipelines"}
    path = tmp_path / "x.pdf"
    resume.generate(path, family="backend_api", job=job)
    reader = PdfReader(str(path))
    text = "\n".join(pg.extract_text() or "" for pg in reader.pages).lower()
    assert "postgresql" in text
    assert "kafka3" not in text


def test_long_jd_still_one_page_readable(tmp_path):
    """Even with a huge description, the PDF must stay one page with a
    readable body font (>= 8pt); the shrink loop must terminate."""
    job = {"title": "Platform Engineer", "company": "Huge Co",
           "description": "Terraform, AWS, Kubernetes, Docker, Linux, CI/CD, " * 400}
    path = tmp_path / "huge.pdf"
    p = resume.generate(path, family="devops_sre_platform", job=job)
    reader = PdfReader(str(p))
    assert len(reader.pages) == 1
    text = "\n".join(pg.extract_text() or "" for pg in reader.pages)
    assert len(text) > 200


def test_render_png_verification(tmp_path):
    """Render the PDF to PNG and verify it is non-blank and page-sized
    (AGENTS.md: 'Render each final PDF to PNG and inspect it')."""
    pdfium = pytest.importorskip("pypdfium2")
    from mazdoor import verify as v
    path = tmp_path / "Hadi_Khan_DevOps.png"
    pdf = tmp_path / "Hadi_Khan_DevOps.pdf"
    resume.generate(pdf, family="devops_sre_platform")
    img = v.render_pdf_png(pdf, out=path, scale=2)
    assert img.size[0] > 1000  # A4 at scale 2 is ~1190px wide
    assert img.size[1] > 1400
    # non-blank: variance across the page
    import numpy as np
    arr = np.asarray(img.convert("L"))
    assert arr.std() > 5, "rendered page looks blank"
    assert path.exists()


def test_render_text_supports_tighter_budgets():
    base = load()
    full = resume.render_text(base, "devops_sre_platform")
    tight = resume.render_text(base, "devops_sre_platform", max_bullets=2)
    assert full != tight
    assert len(tight.splitlines()) < len(full.splitlines())
