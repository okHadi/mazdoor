"""Evidence-backed company and contact research (docs/RESEARCH.md).

Rules:
  - Public, keyless sources only: company sites, public job boards, public
    GitHub/LinkedIn profiles. No login walls, no paid databases.
  - Every claim carries a URL + access date (evidence_urls / citations).
  - Contacts: up to 3 per job; each email labelled 'public' (found verbatim
    in a public page) or 'guessed' (pattern-derived, e.g. first@domain),
    with a confidence score and the source URL.
  - If a source fails or nothing is found, that is recorded honestly:
    geo tag 'unknown', empty evidence. Never fabricate companies, contacts,
    funding, or remote policies.
"""

import json
import re
from datetime import date
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
MAILTO_RE = re.compile(r"mailto:([\w.+-]+@[\w-]+\.[\w.-]+)", re.I)


class ResearchEngine:
    def __init__(self, timeout=20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mazdoor/0.1 (local research)"})

    # -- page fetching -------------------------------------------------------
    def fetch_page(self, url):
        """Return (status, html) or raise; caller records the failure honestly."""
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.status_code, resp.text

    # -- company research ------------------------------------------------------
    def research_company(self, job):
        """Best-effort keyless company research. Returns a dict matching the
        DB company_research fields plus geo_evidence. Never invents facts."""
        company = job.get("company", "")
        domain = _domain_of(job)
        evidence_urls, notes = [], []

        # 1) company homepage / about page
        for url in _candidate_urls(job):
            try:
                status, html = self.fetch_page(url)
                if status == 200:
                    title, summary = _page_summary(html)
                    evidence_urls.append(url)
                    notes.append(f"{url} ({date.today().isoformat()}): {summary}")
                    break
            except Exception:  # noqa: BLE001 - record, try next
                continue

        # 2) keyless search for funding / headcount / remote policy
        snippets = self._search_snippets(f"{company} funding headcount remote")
        for s in snippets[:6]:
            notes.append(f"search ({date.today().isoformat()}): {s}")

        return {
            "company_summary": _summarize(notes, company),
            "evidence_urls": json.dumps(evidence_urls),
            "evidence_notes": "\n".join(notes) if notes else "No public evidence found (recorded honestly).",
            "funding": _extract_funding(notes),
            "headcount": _extract_headcount(notes),
            "remote_policy": _extract_remote_policy(notes),
            "geo_evidence": [{"url": u, "accessed": date.today().isoformat(),
                              "note": n} for u, n in zip(evidence_urls, notes)][:5],
        }

    def _search_snippets(self, query, limit=8):
        """DuckDuckGo lite HTML search, keyless. Returns snippet strings."""
        try:
            resp = self.session.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query}, timeout=self.timeout,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for link in soup.select("a[href*='//duckduckgo.com/l/?uddg=']")[:limit]:
                url = _uddg_target(link.get("href", ""))
                results.append(f"{link.get_text(strip=True)} -> {url}")
            return results
        except Exception:  # noqa: BLE001
            return []

    # -- contacts --------------------------------------------------------------
    def find_contacts(self, job, max_contacts=3):
        """Find up to 3 public contacts. Emails labelled public vs guessed."""
        contacts = []
        domain = _domain_of(job)
        pages = [job.get("external_url"), job.get("description_url"),
                 f"https://{domain}" if domain else None]
        seen_emails = set()
        for page in pages:
            if not page or len(contacts) >= max_contacts:
                break
            try:
                status, html = self.fetch_page(page)
                if status != 200:
                    continue
            except Exception:  # noqa: BLE001
                continue
            for email in MAILTO_RE.findall(html):
                if email not in seen_emails and len(contacts) < max_contacts:
                    seen_emails.add(email)
                    contacts.append({
                        "name": None, "role": "contact on public page",
                        "source": page,
                        "email": email, "email_label": "public",
                        "email_confidence": 0.95,
                        "evidence_url": page,
                        "note": f"Public email on {page}",
                        "confidence_label": "high",
                        "hiring_influence": "unknown; verify role before outreach",
                        "role_is_current": 0,
                    })
        return contacts[:max_contacts]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _domain_of(job):
    # Job-board URLs are not official company domains. Only an explicit,
    # independently verified company URL may drive company-page requests.
    for key in ("company_url", "official_url"):
        url = job.get(key)
        if url:
            try:
                netloc = urlparse(url).netloc.lower()
                if netloc:
                    return netloc
            except Exception:  # noqa: BLE001
                continue
    return None


def _candidate_urls(job):
    domain = _domain_of(job)
    if not domain:
        return []
    urls = [f"https://{domain}", f"https://{domain}/about", f"https://{domain}/careers",
            f"https://www.{domain}"]
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _page_summary(html):
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "")[:120]
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return title, text[:400]


def _uddg_target(href):
    m = re.search(r"uddg=([^&]+)", href)
    return m.group(1) if m else href


def _summarize(notes, company):
    if not notes:
        return f"No public evidence found for {company}."
    return " ".join(notes)[:600]


def _extract_funding(notes):
    for n in notes:
        m = re.search(r"(Series [A-Z]\b|Seed\b|Pre-seed\b|funded|funding|raised)", n, re.I)
        if m:
            return n[:200]
    return None


def _extract_headcount(notes):
    for n in notes:
        m = re.search(r"(\d[\d,]*)\s*(employees|people|team members|staff)", n, re.I)
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return None


def _extract_remote_policy(notes):
    for n in notes:
        low = n.lower()
        if "remote" in low and any(w in low for w in ("first", "fully", "worldwide", "global", "anywhere")):
            return n[:200]
    return None


def ingest_research(store, records, geo=True, gen_drafts=False):
    """Apply researched fields to stored jobs. `records` is a list of dicts
    keyed by job_id with the research payload.

    When `geo` is True, the job's geo tag/confidence/notes are updated from
    the record's `geo` dict (tag, confidence, citations) or derived from
    evidence_notes via geo_eligibility (citations include URL+access date).
    """
    applied = 0
    for rec in records:
        job = store.get_job(rec["job_id"])
        if not job:
            continue
        company = rec.get("company") or {}
        geo_payload = rec.get("geo") or {}
        company_summary = rec.get("company_summary") or company.get("summary")
        evidence_urls = rec.get("evidence_urls") or geo_payload.get("evidence_urls") or []
        notes = rec.get("evidence_notes") or "\n".join(
            part for part in (
                company.get("hook"), geo_payload.get("summary"),
            ) if part
        )
        store.upsert_company_research(
            job_id=job["id"],
            company_summary=company_summary,
            evidence_urls=evidence_urls,
            evidence_notes=notes or None,
            funding=rec.get("funding"),
            headcount=rec.get("headcount"),
            remote_policy=rec.get("remote_policy") or geo_payload.get("summary"),
        )
        if geo:
            _apply_geo(store, job, rec)
        for contact in rec.get("contacts", [])[:3]:
            source_url = contact.get("source_url") or contact.get("evidence_url")
            email_label = contact.get("email_label") or contact.get("email_status")
            store.upsert_contact(
                job_id=job["id"],
                name=contact.get("name"), role=contact.get("role"),
                source=contact.get("source") or source_url,
                email=contact.get("email"), email_label=email_label,
                email_confidence=contact.get("email_confidence", 0.0),
                evidence_url=source_url,
                note=contact.get("note") or contact.get("linkedin_url"),
                confidence_label=contact.get("confidence_label") or "medium",
                hiring_influence=contact.get("hiring_influence") or contact.get("role"),
                role_is_current=1 if contact.get("role_is_current", True) else 0,
            )
        applied += 1
    if gen_drafts:
        from . import pipeline
        pipeline.finalize(store, artifacts_dir=None)
    return applied


def _apply_geo(store, job, rec):
    from .scoring import geo_eligibility

    geo = rec.get("geo")
    if geo:
        tag = geo.get("tag", "unknown")
        confidence = geo.get("confidence", 0.5)
        citations = geo.get("citations", [])
        if not citations:
            summary = geo.get("summary", "")
            citations = [
                {"url": url, "accessed": date.today().isoformat(), "note": summary}
                for url in geo.get("evidence_urls", [])
            ]
        notes = "; ".join(
            f"{c.get('note', '')} ({c.get('url', 'no-url')}, accessed {c.get('accessed', 'unknown')})"
            if isinstance(c, dict) else str(c)
            for c in citations
        )
    else:
        # derive from independent evidence notes (URL + access date present)
        evidence = [{"url": None, "note": rec.get("evidence_notes") or ""}]
        res = geo_eligibility(job.get("location"), "", research_evidence=evidence)
        tag, confidence = res["tag"], res["confidence"]
        notes = "; ".join(
            c if isinstance(c, str) else c.get("note", str(c))
            for c in res["citations"]
        )
    store.update_curation(
        job_id=job["id"], role_family=job["role_family"], geo_tag=tag,
        geo_confidence=confidence, geo_notes=notes, score=job["score"],
        score_breakdown=None, rationale=job["rationale"],
    )
