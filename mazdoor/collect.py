"""One-shot job collection and curation from public, keyless sources.

Sources (docs/SOURCE_SYNC.md):
  - remotive   : https://remotive.com/api/remote-jobs (public JSON API)
  - greenhouse : https://boards-api.greenhouse.io/v1/boards/<board>/jobs (public)
  - lever      : https://api.lever.co/v0/postings/<company>?mode=json (public)
  - ashby      : https://api.ashbyhq.com/posting-api/job-board/<company> (public)

Rules:
  - A failing source is recorded honestly (source_error); never fabricated.
  - Normalizers never invent fields that the source did not provide.
  - Curation picks the target number of scored jobs, never pads.
"""

import json
import re
import time

import requests
from bs4 import BeautifulSoup

from .profile import load
from .scoring import score_job, research_geo

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
LEVER_API = "https://api.lever.co/v0/postings/{company}?mode=json"
ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{company}"

REMOTIVE_SEARCHES = [
    "devops", "sre", "platform", "cloud", "backend", "api", "automation",
    "product", "ai", "pm", "infrastructure", "data engineer",
]

GREENHOUSE_BOARDS = ["gitlab", "hashicorp", "supabase", "vercel", "reddit"]
LEVER_COMPANIES = ["automattic", "dropbox", "stripe"]
ASHBY_COMPANIES = ["supabase", "linear", "notion"]


class Collector:
    def __init__(self, timeout=25):
        self.timeout = timeout

    # -- fetch helpers -------------------------------------------------------
    def _get(self, url, params=None):
        resp = requests.get(url, params=params, timeout=self.timeout,
                            headers={"User-Agent": "Mazdoor/0.1 (local job curator)"})
        resp.raise_for_status()
        return resp.json()

    def fetch_source(self, source, params=None):
        """Fetch one source; returns {'ok', 'source', 'jobs', 'error'}."""
        try:
            if source == "remotive":
                jobs = self._fetch_remotive(params or {"search": "devops"})
            elif source == "greenhouse":
                jobs = self._fetch_greenhouse(params or {"board": "gitlab"})
            elif source == "lever":
                jobs = self._fetch_lever(params or {"company": "automattic"})
            elif source == "ashby":
                jobs = self._fetch_ashby(params or {"company": "supabase"})
            else:
                return {"ok": False, "source": source, "error": f"unknown source {source}", "jobs": []}
            return {"ok": True, "source": source, "jobs": jobs, "error": None}
        except Exception as exc:  # noqa: BLE001 - record honestly, never fabricate
            return {"ok": False, "source": source, "error": str(exc)[:500], "jobs": []}

    # -- remotive ------------------------------------------------------------
    def _fetch_remotive(self, params):
        jobs = []
        for search in REMOTIVE_SEARCHES:
            try:
                data = self._get(REMOTIVE_API, {"search": search, "limit": 30})
                jobs.extend(normalize_remotive(j) for j in data.get("jobs", []))
                time.sleep(0.4)  # polite rate limit
            except Exception as exc:  # noqa: BLE001
                # record per-search failure, keep collecting the rest
                jobs.append(_error_job("remotive", f"search={search}: {exc}"))
        if jobs and all(j.get("source_error") for j in jobs):
            raise RuntimeError(jobs[0]["source_error"])  # whole source failed
        return _dedupe(jobs)

    # -- greenhouse ------------------------------------------------------------
    def _fetch_greenhouse(self, params):
        jobs = []
        for board in params.get("boards") or GREENHOUSE_BOARDS:
            try:
                data = self._get(GREENHOUSE_API.format(board=board))
                jobs.extend(normalize_greenhouse(j, board) for j in data.get("jobs", []))
                time.sleep(0.4)
            except Exception as exc:  # noqa: BLE001
                jobs.append(_error_job("greenhouse", f"board={board}: {exc}"))
        return _dedupe(jobs)

    # -- lever ----------------------------------------------------------------
    def _fetch_lever(self, params):
        jobs = []
        for company in params.get("companies") or LEVER_COMPANIES:
            try:
                data = self._get(LEVER_API.format(company=company))
                jobs.extend(normalize_lever(j, company) for j in data)
                time.sleep(0.4)
            except Exception as exc:  # noqa: BLE001
                jobs.append(_error_job("lever", f"company={company}: {exc}"))
        return _dedupe(jobs)

    # -- ashby ---------------------------------------------------------------
    def _fetch_ashby(self, params):
        jobs = []
        for company in params.get("companies") or ASHBY_COMPANIES:
            try:
                data = self._get(ASHBY_API.format(company=company))
                jobs.extend(normalize_ashby(j, company) for j in data.get("jobs", []))
                time.sleep(0.4)
            except Exception as exc:  # noqa: BLE001
                jobs.append(_error_job("ashby", f"company={company}: {exc}"))
        return _dedupe(jobs)


# ---------------------------------------------------------------------------
# Normalizers (never fabricate: absent fields stay None/empty)
# ---------------------------------------------------------------------------


def _strip_html(text):
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def _clean(text, limit=12000):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[:limit]


def normalize_remotive(raw):
    return {
        "source": "remotive",
        "source_id": str(raw.get("id", "")),
        "external_url": raw.get("url") or f"https://remotive.com/remote-jobs/{raw.get('id', '')}",
        "title": _clean(raw.get("title", "")),
        "company": _clean(raw.get("company_name", "")),
        "location": raw.get("candidate_required_location"),
        "description": _clean(raw.get("description", ""), 12000),
        "description_url": raw.get("url"),
        "posted_at": (raw.get("publication_date") or "")[:10] or None,
        "salary": raw.get("salary"),
        "raw_json": json.dumps(raw, default=str)[:20000],
        "source_error": None,
    }


def normalize_greenhouse(raw, board):
    return {
        "source": "greenhouse",
        "source_id": str(raw.get("id", "")),
        "external_url": raw.get("absolute_url")
        or f"https://job-boards.greenhouse.io/{board}/jobs/{raw.get('id', '')}",
        "title": _clean(raw.get("title", "")),
        "company": _clean((raw.get("company_name") or "").title() or board),
        "location": (raw.get("location") or {}).get("name"),
        "description": _clean(_strip_html(raw.get("content", "")), 12000),
        "description_url": raw.get("absolute_url"),
        "posted_at": (raw.get("updated_at") or "")[:10] or None,
        "salary": None,
        "raw_json": json.dumps(raw, default=str)[:20000],
        "source_error": None,
    }


def normalize_lever(raw, company):
    cats = raw.get("categories") or {}
    return {
        "source": "lever",
        "source_id": str(raw.get("id", "")),
        "external_url": raw.get("hostedUrl") or raw.get("applyUrl") or "",
        "title": _clean(raw.get("text", "")),
        "company": _clean(company.title()),
        "location": cats.get("location") or raw.get("workplaceType"),
        "description": _clean(raw.get("descriptionPlain") or raw.get("description") or "", 12000),
        "description_url": raw.get("hostedUrl"),
        "posted_at": (raw.get("createdAt") or "")[:10] or None,
        "salary": None,
        "raw_json": json.dumps(raw, default=str)[:20000],
        "source_error": None,
    }


def normalize_ashby(raw, company):
    return {
        "source": "ashby",
        "source_id": str(raw.get("id", "")),
        "external_url": raw.get("jobUrl") or raw.get("applyUrl") or "",
        "title": _clean(raw.get("title", "")),
        "company": _clean(company.title()),
        "location": raw.get("location"),
        "description": _clean(raw.get("descriptionHtml") or raw.get("descriptionPlain") or "", 12000),
        "description_url": raw.get("jobUrl"),
        "posted_at": (raw.get("publishedAt") or "")[:10] or None,
        "salary": None,
        "raw_json": json.dumps(raw, default=str)[:20000],
        "source_error": None,
    }


def _error_job(source, message):
    return {
        "source": source,
        "source_id": "__error__",
        "external_url": f"https://error.local/{source}",
        "title": "(source error)",
        "company": "(source error)",
        "location": None,
        "description": "",
        "description_url": None,
        "posted_at": None,
        "salary": None,
        "raw_json": None,
        "source_error": message,
    }


def _dedupe(jobs, key=lambda j: (j["source"], j["source_id"])):
    seen, out = set(), []
    for j in jobs:
        k = key(j)
        if k not in seen and j.get("source_id"):
            seen.add(k)
            out.append(j)
    return out


# ---------------------------------------------------------------------------
# Curation
# ---------------------------------------------------------------------------


def curate(jobs, target=10, profile=None):
    """Score raw jobs, drop empty/error rows, rank, keep top `target`.

    Returns list of dicts: {job fields..., score, role_family, geo_tag,
    geo_confidence, geo_notes, rationale}. Never pads: if fewer than target
    jobs pass, fewer are returned (documented honestly).
    """
    p = profile or load()
    scored = []
    for job in jobs:
        if job.get("source_error"):
            continue  # recorded in DB, not curated
        title, desc = job.get("title") or "", job.get("description") or ""
        if not title.strip() or len(desc.strip()) < 25:
            continue  # too thin to curate honestly
        res = score_job(title, desc, job.get("company", ""), profile=p)
        geo = research_geo(job, company_notes=[])
        job = dict(job)
        job["score"] = res["score"]
        job["role_family"] = res["family"]
        job["geo_tag"] = geo["tag"]
        job["geo_confidence"] = geo["confidence"]
        job["geo_notes"] = "JD signal: " + "; ".join(geo["citations"][:2])
        job["rationale"] = (
            f"{res['family_label']} family; {len(res['keyword_hits'])} keyword hits; "
            f"frontend penalty {res['frontend_penalty']}; score {res['score']}"
        )
        scored.append(job)

    scored.sort(key=lambda j: j["score"], reverse=True)
    return scored[:target]
