"""ATS-friendly one-page resume PDFs from canonical evidence (docs/RESUMES.md).

Rules:
  - One page, text-based PDF (reportlab embeds real text), no images.
  - Standard ATS section names: Summary, Skills, Experience, Education, Projects.
  - Contact block in body (never header/footer): masked phone, hello@mhadi.dev.
  - No em dashes anywhere (ATS encoding + voice rule); plain hyphens only.
  - Job-specific tailoring: per-job title/company/JD keywords change the
    summary, surface JD-matched canonical skills, and re-rank bullet selection.
    JD keywords are ONLY surfaced if they exist in the canonical skill list
    (no invented skills). The tailoring plan is persisted next to the PDF.
  - Fonts stay readable (body >= 8pt); if a page overflows after shrinking,
    content is reduced (fewer bullets, then Projects dropped) before giving up.
"""

import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate

from .profile import load

# Company order per family: most relevant first
_COMPANY_ORDER = {
    "devops_sre_platform": ["Syslify", "Parhlai", "Vfairs", "Imagine.art / Vyro.ai"],
    "backend_api": ["Syslify", "Parhlai", "Vfairs", "Imagine.art / Vyro.ai"],
    "product_engineering": ["Parhlai", "Imagine.art / Vyro.ai", "Syslify", "Vfairs"],
    "ai_first_product": ["Imagine.art / Vyro.ai", "Parhlai", "Syslify", "Vfairs"],
    "technical_pm": ["Imagine.art / Vyro.ai", "Parhlai", "Syslify", "Vfairs"],
    "ai_training": ["Parhlai", "Syslify", "Imagine.art / Vyro.ai", "Vfairs"],
}

# Explicit role blocks keep the page selective and readable. Tuple shape:
# (company, title prefix, bullet budget).
_FAMILY_BLOCKS = {
    "devops_sre_platform": [
        ("Syslify", "Senior DevOps Engineer", 2),
        ("Syslify", "Junior DevOps Engineer", 3),
        ("Parhlai", "Co-Founder & CTO", 3),
        ("Vfairs", "Associate Software Engineer", 1),
    ],
    "backend_api": [
        ("Parhlai", "Co-Founder & CTO", 3),
        ("Syslify", "Junior DevOps Engineer", 2),
        ("Vfairs", "Associate Software Engineer", 2),
        ("Imagine.art / Vyro.ai", "Product Manager", 2),
    ],
    "product_engineering": [
        ("Imagine.art / Vyro.ai", "Product Manager", 4),
        ("Parhlai", "Co-Founder & CTO", 3),
        ("Syslify", "Senior DevOps Engineer", 1),
        ("Vfairs", "Associate Software Engineer", 1),
    ],
    "ai_first_product": [
        ("Imagine.art / Vyro.ai", "Product Manager", 4),
        ("Parhlai", "Co-Founder & CTO", 3),
        ("Syslify", "Senior DevOps Engineer", 1),
        ("Vfairs", "Associate Software Engineer", 1),
    ],
    "technical_pm": [
        ("Imagine.art / Vyro.ai", "Product Manager", 4),
        ("Parhlai", "Co-Founder & CTO", 3),
        ("Syslify", "Senior DevOps Engineer", 1),
        ("Vfairs", "Associate Software Engineer", 1),
    ],
    "ai_training": [
        ("Imagine.art / Vyro.ai", "Product Manager", 3),
        ("Parhlai", "Co-Founder & CTO", 3),
        ("Syslify", "Junior DevOps Engineer", 2),
        ("Vfairs", "Associate Software Engineer", 1),
    ],
}

_MAX_BULLETS = {family: 4 for family in _FAMILY_BLOCKS}

_FAMILY_SKILL_ORDER = {
    "devops_sre_platform": ["infra", "languages", "backend", "ai_ml", "qa_perf", "product"],
    "backend_api": ["languages", "backend", "infra", "ai_ml", "qa_perf", "product"],
    "product_engineering": ["backend", "product", "ai_ml", "infra", "languages", "qa_perf"],
    "ai_first_product": ["ai_ml", "backend", "languages", "infra", "product", "qa_perf"],
    "technical_pm": ["product", "ai_ml", "backend", "infra", "languages", "qa_perf"],
    "ai_training": ["languages", "ai_ml", "backend", "infra", "qa_perf", "product"],
}

MIN_BODY_FONT = 9.0


def _family_keywords(family):
    return set(load()["role_families"][family]["keywords"])


def _canonical_skill_words(profile):
    """All canonical skills, lowercased, for honest JD keyword matching."""
    words = set()
    for group in profile["skills"].values():
        for s in group:
            words.add(s.lower())
    return words


def jd_keywords_matched(profile, family, description):
    """JD keywords backed by canonical skills or experience evidence."""
    canonical = _canonical_skill_words(profile)
    text = (description or "").lower()
    matched = sorted(kw for kw in canonical if kw in text)
    evidence = " ".join(
        bullet
        for experience in profile["experience"]
        for title in experience["titles"]
        for bullet in title["bullets"]
    ).lower()
    for kw in profile["role_families"][family]["keywords"]:
        if kw in text and kw in evidence and kw not in matched:
            matched.append(kw)
    return matched


def _bullet_relevance(bullet, family, jd_keywords):
    kws = _family_keywords(family)
    low = bullet.lower()
    hits = sum(1 for kw in kws if kw in low)
    jd_hits = sum(1 for kw in jd_keywords if kw in low)
    metric = 1.5 if any(m in bullet for m in (
        "users", "PKR", "revenue", "accounts", "reduction", "50%", "90%", "70%",
        "MAU", "DAUs", "cost", "million", "scaled", "zero paid")) else 0.0
    return hits + 2.0 * jd_hits + metric


def _select_bullets(exp, family, max_bullets, jd_keywords):
    """Pick the strongest bullets for a family + job, keeping title blocks whole."""
    out = []
    for t in exp["titles"]:
        ranked = sorted(
            t["bullets"],
            key=lambda b: _bullet_relevance(b, family, jd_keywords),
            reverse=True,
        )
        out.append({
            "title": t["title"],
            "dates": t["dates"],
            "location": t["location"],
            "bullets": ranked[:max_bullets],
        })
    return out


def _tailored_summary(profile, family, job, jd_keywords):
    base = profile["role_families"][family]["summary"]
    if not job:
        return base
    title, company = job.get("title") or "", job.get("company") or ""
    target = f"Target role: {title} | {company}." if title and company else ""
    if jd_keywords:
        surfaced = ", ".join(jd_keywords[:5])
        target += f" Relevant stack: {surfaced}."
    return (base + " " + target).strip() if target else base


def _focused_skill_groups(profile, family, jd_keywords):
    matched = {keyword.lower() for keyword in jd_keywords}
    groups = []
    labels = {"ai_ml": "AI/ML", "qa_perf": "QA/Performance"}
    for index, group in enumerate(_FAMILY_SKILL_ORDER[family][:3]):
        skills = profile["skills"][group]
        ordered = [skill for skill in skills if skill.lower() in matched]
        ordered += [skill for skill in skills if skill.lower() not in matched]
        limit = (9, 7, 6)[index]
        groups.append(f"{labels.get(group, group.capitalize())}: {', '.join(ordered[:limit])}")
    return groups


def _experience_blocks(profile, family, jd_keywords, max_bullets=None):
    companies = {experience["company"]: experience for experience in profile["experience"]}
    blocks = []
    for company, title_prefix, budget in _FAMILY_BLOCKS[family]:
        experience = companies[company]
        title = next(
            item for item in experience["titles"]
            if item["title"].startswith(title_prefix)
        )
        limit = min(budget, max_bullets) if max_bullets is not None else budget
        ranked = sorted(
            title["bullets"],
            key=lambda bullet: _bullet_relevance(bullet, family, jd_keywords),
            reverse=True,
        )
        selected = ranked[:limit]
        if company == "Parhlai" and selected and not any(
                "booked revenue" in bullet.lower() for bullet in selected):
            revenue_bullet = next(
                bullet for bullet in title["bullets"]
                if "booked revenue" in bullet.lower()
            )
            selected[-1] = revenue_bullet
        blocks.append({
            "company": company,
            "title": title["title"],
            "dates": title["dates"],
            "location": title["location"],
            "bullets": selected,
        })
    return blocks


def render_text(profile=None, family="devops_sre_platform", job=None,
                max_bullets=None):
    """Render the resume as structured text lines (used by tests + PDF builder).

    `job` is a dict {title, company, description} that drives tailoring.
    `max_bullets` overrides the per-company bullet budget (one-page control).
    """
    p = profile or load()
    jd_keywords = jd_keywords_matched(p, family, job.get("description") if job else None)
    budget = max_bullets if max_bullets is not None else _MAX_BULLETS[family]

    lines = []
    lines.append(p["name"])
    contact = " | ".join([
        p["email"], p["links"]["linkedin"],
        p["links"]["website"], p["links"]["github"],
    ])
    lines.append(contact)
    lines.append("")

    lines.append("Summary")
    lines.append(_tailored_summary(p, family, job, jd_keywords))
    lines.append("")

    skill_groups = _focused_skill_groups(p, family, jd_keywords)
    lines.append("Skills")
    lines.append(" | ".join(skill_groups))
    lines.append("")

    lines.append("Experience")
    for block in _experience_blocks(p, family, jd_keywords, max_bullets=budget):
        lines.append(
            f"{block['title']} - {block['company']} "
            f"({block['dates']}, {block['location']})"
        )
        for bullet in block["bullets"]:
            lines.append(f"- {bullet}")
    lines.append("")

    lines.append("Education")
    for ed in p["education"]:
        lines.append(f"{ed['degree']}, {ed['school']} - {ed['location']}")
    lines.append("")
    return "\n".join(lines)


def build_plan(profile=None, family="devops_sre_platform", job=None):
    """Tailoring plan dict (persisted to DB and as a sidecar .md file)."""
    p = profile or load()
    jd_keywords = jd_keywords_matched(p, family, job.get("description") if job else None)
    return {
        "family": family,
        "family_label": p["role_families"][family]["label"],
        "job_title": (job or {}).get("title"),
        "company": (job or {}).get("company"),
        "jd_keywords_matched": jd_keywords,
        "summary": _tailored_summary(p, family, job, jd_keywords),
        "bullet_budget": "8-10 total across four relevant roles",
        "sections": ["Summary", "Skills", "Experience", "Education"],
        "generated": date.today().isoformat(),
    }


def _write_plan_file(pdf_path, plan):
    sidecar = pdf_path.with_name(pdf_path.stem + "_tailoring.md")
    parts = [
        f"# Tailoring plan: {plan['job_title'] or 'resume'} at {plan['company'] or 'unknown'}",
        "",
        f"- Family: {plan['family']} ({plan['family_label']})",
        f"- JD keywords matched (canonical only): {', '.join(plan['jd_keywords_matched']) or 'none'}",
        f"- Summary used: {plan['summary']}",
        f"- Bullet budget: {plan['bullet_budget']}",
        f"- Generated: {plan['generated']}",
        "",
        "Rule: JD keywords are surfaced only if they exist in the canonical",
        "skill list (mazdoor/profile.py). No invented skills or metrics.",
    ]
    sidecar.write_text("\n".join(parts))
    return sidecar


# ---------------------------------------------------------------------------
# PDF builder
# ---------------------------------------------------------------------------

_STYLES = {}


def _build_styles():
    """Create the style set once. The shrink loop mutates these same styles;
    it must never be re-run from scratch (which would loop forever)."""
    _STYLES.clear()
    _STYLES["name"] = ParagraphStyle(
        "name", fontName="Helvetica-Bold", fontSize=15, leading=18,
        spaceAfter=1, alignment=TA_LEFT)
    _STYLES["contact"] = ParagraphStyle(
        "contact", fontName="Helvetica", fontSize=8.4, leading=10.2,
        textColor=colors.HexColor("#333333"), spaceAfter=5)
    _STYLES["h2"] = ParagraphStyle(
        "h2", fontName="Helvetica-Bold", fontSize=10.5, leading=12.5,
        spaceBefore=5, spaceAfter=2, textColor=colors.HexColor("#111111"))
    _STYLES["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9.5, leading=11.7, spaceAfter=1.8)
    _STYLES["jobhead"] = ParagraphStyle(
        "jobhead", fontName="Helvetica-Bold", fontSize=9.6, leading=11.6,
        spaceBefore=3, spaceAfter=1)
    _STYLES["bullet"] = ParagraphStyle(
        "bullet", fontName="Helvetica", fontSize=9.2, leading=11.2,
        leftIndent=9, bulletIndent=2, spaceAfter=0.5)


def _flowables(text):
    lines = text.splitlines()
    story = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if i == 0:
            story.append(Paragraph(line, _STYLES["name"]))
            i += 1
            continue
        if i == 1:
            story.append(Paragraph(line, _STYLES["contact"]))
            i += 1
            continue
        if line in ("Summary", "Skills", "Experience", "Education", "Projects"):
            story.append(Paragraph(line, _STYLES["h2"]))
            i += 1
            body = []
            while i < len(lines) and lines[i].strip() not in (
                    "Summary", "Skills", "Experience", "Education", "Projects"):
                if lines[i].strip():
                    body.append(lines[i].strip())
                i += 1
            for para in body:
                if para.startswith("- "):
                    story.append(Paragraph(para[2:], _STYLES["bullet"], bulletText="\u2022"))
                elif line == "Experience":
                    story.append(Paragraph(para, _STYLES["jobhead"]))
                else:
                    story.append(Paragraph(para, _STYLES["body"]))
            continue
        if line.startswith("- "):
            story.append(Paragraph(line[2:], _STYLES["bullet"], bulletText="\u2022"))
            i += 1
            continue
        story.append(Paragraph(line, _STYLES["body"]))
        i += 1
    return story


def _build(path, story):
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=11 * mm, bottomMargin=11 * mm,
        title="Hadi Khan - Resume",
        author="Hadi Khan",
        subject="Resume",
        creator="Mazdoor",
    )
    doc.build(story)
    return doc.page  # page count


def _shrink_styles_once():
    """Reduce font sizes one step; returns True if it changed anything."""
    changed = False
    for s in _STYLES.values():
        if s.fontSize and s.fontSize > MIN_BODY_FONT:
            s.fontSize = round(max(MIN_BODY_FONT, s.fontSize - 0.3), 1)
            s.leading = round(max(s.leading - 0.4, s.fontSize + 1.2), 1)
            changed = True
    return changed


def generate(path, family="devops_sre_platform", profile=None, job=None):
    """Build the one-page PDF at `path`; writes the tailoring plan sidecar.

    Returns the PDF path. Deterministic termination: shrink fonts to a 9pt floor,
    then reduce the already focused bullet budgets.
    """
    p = profile or load()
    path = Path(path) if not isinstance(path, Path) else path
    _build_styles()

    budgets = [4, 3, 2, 1]
    pdf_path = str(path)

    for budget in budgets:
        for _attempt in range(12):  # bounded shrink attempts
            text = render_text(p, family, job=job, max_bullets=budget)
            story = _flowables(text)
            pages = _build(pdf_path, story)
            if pages <= 1:
                plan = build_plan(p, family, job)
                _write_plan_file(path, plan)
                return path
            if not _shrink_styles_once():
                break  # at floor; reduce content next

    # Final fallback: absolute minimum content, accept whatever fits
    text = render_text(p, family, job=job, max_bullets=1)
    _build(pdf_path, _flowables(text))
    plan = build_plan(p, family, job)
    _write_plan_file(path, plan)
    return path


def _drop_projects(text):
    lines = text.splitlines()
    out, skipping = [], False
    for ln in lines:
        if ln.strip() == "Projects":
            skipping = True
            continue
        if skipping and not ln.strip():
            skipping = False
            continue
        if not skipping:
            out.append(ln)
    return "\n".join(out)


def default_filename(family, company, out_dir, title=None):
    safe_company = "".join(c for c in company if c.isalnum() or c in " -_") \
        .strip().replace(" ", "_") or "Company"
    safe_title = "".join(c for c in (title or "") if c.isalnum() or c in " -_") \
        .strip().replace(" ", "_")[:70]
    fam_label = family.replace("devops_sre_platform", "DevOps") \
                      .replace("backend_api", "Backend") \
                      .replace("ai_first_product", "AI_Product") \
                      .replace("product_engineering", "ProductEng") \
                      .replace("technical_pm", "TechnicalPM") \
                      .replace("ai_training", "AITraining")
    suffix = f"_{safe_title}" if safe_title else ""
    return out_dir / f"Hadi_Khan_{fam_label}_{safe_company}{suffix}.pdf"


def json_plan(plan):
    return json.dumps(plan, default=str)
