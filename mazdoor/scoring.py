"""Role-family classification, match scoring, and geo eligibility research.

Scoring rules (docs/SCORING.md):
- Never exclude a job based on title alone; adjacent titles are classified by
  description evidence.
- Frontend-heavy roles are penalized, never hard-excluded.
- Mid seniority preferred; junior/senior accepted.
- Geo eligibility is a separate research step with citations, not JD guessing.
"""

import re
from datetime import date

from .profile import load

_FAMILY_ORDER = [
    "devops_sre_platform",
    "backend_api",
    "ai_first_product",
    "product_engineering",
    "technical_pm",
    "ai_training",
]


def _text(title, description):
    return f"{title} {description}".lower()


def _score_family(title_desc, family_spec):
    """Fraction of family keywords present in the job text."""
    hits = [kw for kw in family_spec["keywords"] if kw in title_desc]
    return hits, len(hits) / max(len(family_spec["keywords"]), 1)


# Title patterns: strong role signals that beat generic keyword scoring.
# Order matters: the first match wins.
_TITLE_PATTERNS = [
    (re.compile(r"product manager|product owner|technical pm|sprint lead|scrum master"),
     "technical_pm"),
    (re.compile(r"ai trainer|evaluator|annotator|rater|labeling|ai training|ground truth|benchmark"),
     "ai_training"),
    (re.compile(r"devops|site reliability|\bsre\b|platform engineer|cloud infra|cloud operations|"
                r"cloud ops|infrastructure eng|cloud engineer|openshift|kubernetes engineer|"
                r"terraform engineer|platform eng"),
     "devops_sre_platform"),
    (re.compile(r"backend|api engineer|full stack|fullstack|automation engineer|integration engineer|"
                r"data engineer|serverless engineer"),
     "backend_api"),
]


# Description patterns: strong technical signals that define the family even
# for adjacent titles (e.g. "Product Engineer" building with Claude Code).
_DESC_PATTERNS = [
    (re.compile(r"claude code|codex|ai agents|ai coding|agentic|prompt engineering"),
     "ai_first_product"),
    (re.compile(r"terraform|kubernetes|\bk8s\b|aws accounts|control tower|openshift|"
                r"infrastructure as code|ci/cd|github actions"),
     "devops_sre_platform"),
]


def classify_role(title, description=""):
    """Pick the best role family for a job. Title alone never excludes."""
    tl = (title or "").lower()
    for pat, fam in _TITLE_PATTERNS:
        if pat.search(tl):
            return fam
    desc = (description or "").lower()
    for pat, fam in _DESC_PATTERNS:
        if pat.search(desc):
            return fam
    # fallback: keyword scoring with title hits weighted (adjacent titles)
    text = _text(title, description)
    best, best_score = None, 0
    for fam in _FAMILY_ORDER:
        spec = load()["role_families"][fam]
        hits, _frac = _score_family(text, spec)
        title_hits = sum(1 for kw in spec["keywords"] if kw in tl)
        score = title_hits * 3 + len(hits)
        if score > best_score:
            best, best_score = fam, score
    return best or "backend_api"


def frontend_penalty(title, description):
    """Return a penalty 0..40 and the offending signals, never exclusion."""
    text = _text(title, description)
    hits = []
    for w in load()["frontend_penalty_words"]:
        # word boundaries so "ux" doesn't match inside "Linux"
        if re.search(rf"\b{re.escape(w)}\b", text):
            hits.append(w)
    if not hits:
        return 0.0, []
    # heavy frontend weighting: more distinct signals -> larger penalty
    penalty = min(40.0, 10.0 + 8.0 * len(hits))
    return penalty, hits


def seniority_bonus(title, description):
    """Mid preferred, junior/senior accepted: 0 for mid, -3 junior, +1 senior."""
    text = _text(title, description)
    sk = load()["seniority_keywords"]
    has_junior = any(w in text for w in sk["junior"])
    has_mid = any(w in text for w in sk["mid"])
    has_senior = any(w in text for w in sk["senior"])
    if has_junior and not has_senior:
        return -3.0
    if has_senior and not has_junior:
        return 1.0
    if has_mid:
        return 0.0
    return -1.0  # ambiguous seniority


def score_job(title, description, company, profile=None):
    """Score a job 0..100 for the chosen family.

    Returns dict with family, score, keyword hits, penalties and breakdown.

    Keyword coverage uses a capped denominator (min(len(keywords), 12)) so a
    handful of strong hits is rewarded properly instead of being diluted by
    the full keyword list.
    """
    p = profile or load()
    text = _text(title, description)
    family = classify_role(title, description)
    spec = p["role_families"][family]
    hits, _frac = _score_family(text, spec)

    denom = max(8, min(len(spec["keywords"]), 12))
    coverage = min(1.0, len(hits) / denom)
    base = 40 + coverage * 55  # keyword coverage dominates

    pen, pen_hits = frontend_penalty(title, description)
    sen = seniority_bonus(title, description)
    score = max(0.0, min(100.0, base - pen + sen))

    # backend-heavy fullstack counts as backend; explicit "frontend-only" tanks
    is_frontend_only = bool(
        re.search(r"\bfrontend\b|\bfront-end\b|\bui engineer\b", text)
        and not re.search(r"\bapi\b|\bbackend\b|serverless|database|infrastructure", text)
    )
    if is_frontend_only:
        score = min(score, 35.0)

    return {
        "family": family,
        "family_label": spec["label"],
        "score": round(score, 1),
        "keyword_hits": hits,
        "frontend_penalty": round(pen, 1),
        "frontend_signals": pen_hits,
        "seniority_adjustment": sen,
        "breakdown": {
            "base_coverage": round(base, 1),
            "coverage_denominator": denom,
            "hits": len(hits),
            "frontend_penalty": round(pen, 1),
            "seniority_adjustment": sen,
        },
    }


# ---------------------------------------------------------------------------
# Geo eligibility
# ---------------------------------------------------------------------------

# Strong positive signals: only EXPLICIT terms may confirm eligibility from
# the JD. "Fully remote", "100% remote", "remote-first" alone are NOT enough
# (docs/RESEARCH.md, parent review). External evidence is handled separately.
_STRONG_ELIGIBLE_TERMS = [
    "worldwide", "anywhere", "pakistan", "south asia", "apac",
]
_RESTRICTED_TERMS = [
    "us only", "united states only", "must be based in the us", "us citizens only",
    "authorized to work in the us", "work authorization required",
    "europe only", "eu only", "within the eu", "uk only", "canada only",
    "australia only", "latin america only", "latam only", "must be located in",
]


def geo_eligibility(location, description, research_evidence=None):
    """Classify remote eligibility for a job.

    `research_evidence` is a list of dicts {url, accessed, note} produced by a
    separate research step (docs/RESEARCH.md). JD text is a starting signal
    only; the final tag should be informed by research_evidence when present.
    """
    text = _text(location or "", description or "")
    evidence = research_evidence or []

    # 1. Explicit restriction wins over everything
    for term in _RESTRICTED_TERMS:
        if term in text:
            return _geo("restricted", 0.9,
                        [f"JD/location text: '{term}'", *evidence])

    # 2. Explicit worldwide/anywhere/Pakistan/APAC inclusion confirms
    for term in _STRONG_ELIGIBLE_TERMS:
        if term in text:
            return _geo("confirmed_eligible", 0.85,
                        [f"JD/location text: '{term}'", *evidence])

    # 3. Research evidence can upgrade or downgrade
    if evidence:
        joined = " ".join(e.get("note", "") for e in evidence).lower()
        for term in _STRONG_ELIGIBLE_TERMS:
            if term in joined:
                return _geo("confirmed_eligible", 0.7,
                            [f"research: '{term}'", *evidence])
        for term in _RESTRICTED_TERMS:
            if term in joined:
                return _geo("restricted", 0.7, [f"research: '{term}'", *evidence])

    # 4. Remote with unknown region: possible exception until researched
    if "remote" in text:
        return _geo("possible_exception", 0.45,
                    ["JD says remote but region unspecified; needs separate research", *evidence])

    # 5. Nothing useful: unknown, researched honestly
    return _geo("unknown", 0.2,
                ["No geo signal in JD; needs separate research", *evidence])


def _geo(tag, confidence, citations):
    return {
        "tag": tag,
        "confidence": round(confidence, 2),
        "citations": citations,
        "accessed": date.today().isoformat(),
    }


def research_geo(job, company_notes):
    """Combine JD signal with independent research notes (company careers pages,
    hiring policy pages). Returns the same shape as geo_eligibility."""
    evidence = [{"url": n.get("url"), "accessed": date.today().isoformat(),
                 "note": n.get("note")} for n in (company_notes or [])]
    return geo_eligibility(job.get("location"), job.get("description"), evidence)
