"""Local dashboard for Mazdoor (stdlib http.server, no secrets, no keys).

Endpoints:
  GET  /                       job board table (score, family, geo, apply, status)
  GET  /job/<id>               full detail: evidence, apply link, PDF, drafts, notes
  GET  /api/jobs               JSON of all curated jobs
  GET  /api/job/<id>           JSON detail
  POST /api/job/<id>/status    update status/outcome/notes (local only)
  GET  /artifacts/<file>       resume PDFs and draft files

There is deliberately NO send/apply endpoint. The dashboard is a tracking and
copy-paste surface only (docs/OPERATIONS.md).
"""

import json
import re
import mimetypes
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import markdown

from .db import STATUSES

GEO_BADGE = {
    "confirmed_eligible": "green",
    "strong_signal": "teal",
    "possible_exception": "amber",
    "restricted": "red",
    "unknown": "gray",
}


class DashboardHandler(BaseHTTPRequestHandler):
    store = None
    artifacts_dir = None

    # -- helpers ---------------------------------------------------------------
    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, status=200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # keep server quiet
        pass

    # -- routing ---------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._html(_page_index(self.store, urllib.parse.parse_qs(parsed.query)))
        elif path.startswith("/job/"):
            job_id = _int_or(path.rsplit("/", 1)[-1], None)
            detail = self.store.job_with_details(job_id) if job_id else None
            if detail:
                self._html(_page_job(self.store, detail))
            else:
                self._html("<h1>404</h1>", 404)
        elif path == "/api/jobs":
            self._json({"jobs": _api_jobs(self.store)})
        elif path.startswith("/api/job/"):
            job_id = _int_or(path.rsplit("/", 1)[-1], None)
            detail = self.store.job_with_details(job_id) if job_id else None
            self._json(detail or {"error": "not found"}, 200 if detail else 404)
        elif path.startswith("/artifacts/"):
            self._serve_artifact(path[len("/artifacts/"):])
        else:
            self._html("<h1>404</h1>", 404)

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/job/") and parsed.path.endswith("/status"):
            job_id = _int_or(parsed.path.split("/")[3], None)
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"ok": False, "error": "bad json"}, 400)
                return
            status = payload.get("status")
            if status not in STATUSES:
                self._json({"ok": False, "error": f"invalid status: {status}"}, 400)
                return
            self.store.update_application(
                job_id=job_id, status=status,
                applied_at=payload.get("applied_at"),
                notes=payload.get("notes"), outcome=payload.get("outcome"),
            )
            self._json({"ok": True})
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def _serve_artifact(self, name):
        name = urllib.parse.unquote(name)
        if ".." in name or "/" in name:
            self._html("<h1>403</h1>", 403)
            return
        path = (self.artifacts_dir / name).resolve()
        if not str(path).startswith(str(self.artifacts_dir.resolve())) or not path.exists():
            self._html("<h1>404</h1>", 404)
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(store, host="127.0.0.1", port=8080, artifacts_dir=None):
    """Start the dashboard in a background thread.

    Returns a handle with .port, .stop() and .join(). Call stop() to shut the
    server down cleanly (tests and CLI exit paths).
    """
    handler = type("BoundHandler", (DashboardHandler,), {})
    handler.store = store
    handler.artifacts_dir = artifacts_dir
    httpd = ThreadingHTTPServer((host, port), handler)
    actual_port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    class Handle:
        port = actual_port

        def stop(self):
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

        def join(self, timeout=None):
            thread.join(timeout=timeout)

    return Handle()


def _int_or(s, default):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


def _api_jobs(store):
    out = []
    for job in store.get_jobs(order_by="score", desc=True):
        app = store.get_application(job["id"]) or {}
        out.append({
            "id": job["id"], "title": job["title"], "company": job["company"],
            "location": job["location"], "external_url": job["external_url"],
            "role_family": job["role_family"], "geo_tag": job["geo_tag"],
            "geo_confidence": job["geo_confidence"], "score": job["score"],
            "rationale": job["rationale"], "status": app.get("status", "not_applied"),
            "source": job["source"],
        })
    return out


# ---------------------------------------------------------------------------
# HTML pages
# ---------------------------------------------------------------------------

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Mazdoor - local job tracker</title>
<style>
  :root {{ --ink:#172033; --muted:#637083; --line:#dfe4ea; --paper:#fff; --canvas:#f2f4f7; --navy:#101a2e; --blue:#1769e0; --blue-dark:#0f52b7; --green:#177245; --soft-blue:#eaf2ff; }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: var(--canvas); color: var(--ink); line-height: 1.5; }}
  ::selection {{ background:#cfe0ff; color:#0b2f68; }}
  a {{ color: var(--blue); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
  a:hover {{ color: var(--blue-dark); }}
  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {{ outline:3px solid #93b9f7; outline-offset:2px; }}
  header {{ background: var(--navy); color: #fff; padding: 14px max(20px, env(safe-area-inset-right)) 14px max(20px, env(safe-area-inset-left)); }}
  .header-inner {{ max-width:1180px; margin:0 auto; display:flex; align-items:center; justify-content:space-between; gap:18px; }}
  .brand {{ margin: 0; font-size: 18px; font-weight:780; letter-spacing:-.01em; }}
  header p {{ margin: 2px 0 0; color: #aab6ca; font-size: 12px; }}
  .nav a {{ color:#cfe0ff; font-size:13px; font-weight:650; text-decoration:none; }}
  main {{ padding: 24px 24px 64px; max-width: 1180px; margin: 0 auto; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 14px; overflow: hidden; box-shadow: 0 8px 24px rgba(16,26,46,.06); }}
  th, td {{ text-align: left; padding: 12px 14px; font-size: 13.5px; border-bottom: 1px solid #edf0f4; }}
  th {{ background: #f7f8fa; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: #596579; }}
  tr:hover td {{ background: #f9fbff; }}
  .card {{ background: var(--paper); border-radius: 14px; padding: 22px; box-shadow: 0 8px 24px rgba(16,26,46,.06); }}
  .section {{ margin-top:20px; }}
  .section-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin:0 0 12px; }}
  .section-head h2, .card h2 {{ margin:0; font-size:19px; letter-spacing:-.015em; }}
  .section-head p {{ margin:2px 0 0; color:var(--muted); font-size:13px; }}
  .badge {{ display:inline-flex; align-items:center; padding:4px 9px; border-radius:999px; font-size:11.5px; font-weight:750; white-space:nowrap; }}
  .green {{ background:#e0f5e9; color:#13663e; }} .teal {{ background:#dff5f2; color:#12635c; }}
  .amber {{ background:#fff0c7; color:#805a00; }} .red {{ background:#ffe2e2; color:#912f2f; }} .gray {{ background:#e9edf2; color:#526071; }}
  .score {{ font-weight:780; font-variant-numeric:tabular-nums; }}
  .muted {{ color:var(--muted); font-size:13px; }}
  .eyeline {{ color:var(--muted); font-size:13px; margin:0 0 8px; }}
  .job-hero {{ padding:26px; }}
  .job-hero h1 {{ font-size:clamp(25px,4vw,38px); line-height:1.15; letter-spacing:-.035em; margin:0; max-width:850px; }}
  .company {{ color:var(--muted); font-weight:550; }}
  .hero-meta, .metrics {{ display:flex; flex-wrap:wrap; gap:8px 16px; align-items:center; }}
  .hero-meta {{ margin-top:12px; color:var(--muted); font-size:13px; }}
  .metrics {{ margin-top:20px; padding-top:18px; border-top:1px solid var(--line); }}
  .metric {{ min-width:120px; }} .metric strong {{ display:block; font-size:18px; }} .metric span {{ color:var(--muted); font-size:12px; }}
  .actions {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }}
  .button, button {{ display:inline-flex; min-height:42px; align-items:center; justify-content:center; gap:7px; padding:9px 14px; border:0; border-radius:9px; background:var(--blue); color:#fff; font:inherit; font-size:13px; font-weight:720; cursor:pointer; text-decoration:none; }}
  .button:hover, button:hover {{ background:var(--blue-dark); color:#fff; text-decoration:none; }}
  .button.secondary, button.secondary {{ background:#eef2f7; color:#1e2a3d; }}
  .button.ghost {{ background:transparent; color:var(--blue); border:1px solid #bed2ef; }}
  .layout {{ display:grid; grid-template-columns:minmax(0,1.5fr) minmax(280px,.75fr); gap:20px; align-items:start; }}
  .stack {{ display:grid; gap:14px; }}
  .kit-list {{ display:grid; gap:12px; }}
  .kit-row {{ display:flex; align-items:center; justify-content:space-between; gap:16px; padding:14px 0; border-bottom:1px solid var(--line); }}
  .kit-row:last-child {{ border-bottom:0; padding-bottom:0; }}
  .kit-row:first-child {{ padding-top:0; }}
  .kit-row strong {{ display:block; }}
  .lead-card {{ border:1px solid var(--line); border-radius:12px; overflow:hidden; margin-top:12px; }}
  .lead-head {{ display:flex; justify-content:space-between; gap:14px; padding:15px 16px; background:#f7f9fc; }}
  .lead-head h3 {{ margin:0; font-size:16px; }}
  .lead-head p {{ margin:2px 0 0; }}
  .lead-body {{ padding:16px; }}
  .channel {{ color:var(--muted); font-size:12px; margin-bottom:10px; }}
  .message {{ white-space:pre-wrap; border:1px solid #cdd8e6; background:#fbfcfe; border-radius:10px; padding:14px; font-size:14px; line-height:1.58; max-height:360px; overflow:auto; }}
  .copy-state {{ margin-left:8px; color:var(--green); font-size:12px; font-weight:650; }}
  .empty {{ border:1px dashed #b9c4d2; border-radius:12px; padding:20px; background:#fafbfc; }}
  .empty h3 {{ margin:0 0 5px; font-size:16px; }} .empty p {{ margin:0; color:var(--muted); }}
  .source-list {{ list-style:none; padding:0; margin:12px 0 0; display:flex; flex-wrap:wrap; gap:8px; }}
  .source-list a {{ display:inline-block; padding:6px 9px; background:#eef3fa; border-radius:7px; font-size:12px; text-decoration:none; }}
  details.card {{ padding:0; overflow:hidden; }}
  details > summary {{ cursor:pointer; padding:18px 22px; font-weight:750; list-style:none; display:flex; justify-content:space-between; align-items:center; }}
  details > summary::-webkit-details-marker {{ display:none; }} details > summary::after {{ content:"Show"; font-size:12px; color:var(--blue); }}
  details[open] > summary {{ border-bottom:1px solid var(--line); }} details[open] > summary::after {{ content:"Hide"; }}
  .details-body {{ padding:20px 22px; }}
  .prose {{ max-width:76ch; font-size:15px; line-height:1.7; }}
  .prose h1 {{ font-size:23px; }} .prose h2 {{ font-size:20px; }} .prose h3 {{ font-size:17px; }}
  .prose h1,.prose h2,.prose h3,.prose h4 {{ margin:1.5em 0 .55em; line-height:1.25; }} .prose > :first-child {{ margin-top:0; }}
  .prose p {{ margin:.65em 0; }} .prose li {{ margin:.32em 0; }} .prose ul {{ padding-left:1.25em; }}
  .status-form {{ display:grid; gap:10px; }}
  input, select, textarea {{ font:inherit; min-height:42px; padding:8px 10px; border:1px solid #c8d1dc; border-radius:8px; background:#fff; color:var(--ink); }}
  .save-status {{ min-height:18px; color:var(--green); font-size:12px; }}
  .back {{ display:inline-block; margin:0 0 14px; font-size:13px; font-weight:650; text-decoration:none; }}
  .mobile-actions {{ display:none; }}
  @media (max-width:760px) {{
    header {{ padding-top:11px; padding-bottom:11px; }} header p {{ display:none; }}
    main {{ padding:14px 12px 96px; }} .layout {{ grid-template-columns:1fr; }}
    .card {{ border-radius:12px; padding:17px; }} .job-hero {{ padding:19px 17px; }}
    .job-hero h1 {{ font-size:25px; }} .metrics {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
    .metric {{ min-width:0; }} .actions {{ display:none; }}
    .section-head {{ align-items:flex-start; }} .section-head h2,.card h2 {{ font-size:18px; }}
    .kit-row {{ align-items:flex-start; flex-direction:column; gap:8px; }}
    .kit-row .button {{ width:100%; }} .lead-head {{ flex-direction:column; }}
    .message {{ font-size:13px; max-height:320px; }}
    table, thead, tbody, th, td, tr {{ display:block; }} th {{ display:none; }} tr {{ padding:12px; border-bottom:1px solid var(--line); }} td {{ border:0; padding:4px 2px; }}
    .mobile-actions {{ position:fixed; z-index:20; display:grid; grid-template-columns:1fr 1fr 1fr; left:0; right:0; bottom:0; padding:9px 10px max(9px, env(safe-area-inset-bottom)); gap:8px; background:rgba(255,255,255,.97); border-top:1px solid var(--line); box-shadow:0 -8px 24px rgba(16,26,46,.08); }}
    .mobile-actions .button {{ min-height:44px; padding:8px; font-size:12px; }}
  }}
</style>
</head>
<body>
<header>
  <div class="header-inner"><div><div class="brand">Mazdoor</div><p>Your private application workspace. Nothing is sent automatically.</p></div><nav class="nav"><a href="/">All jobs</a></nav></div>
</header>
<main>
{BODY}
</main>
</body>
</html>"""


def _page_index(store, params=None):
    params = params or {}
    selected_family = (params.get("family") or [""])[0]
    selected_geo = (params.get("geo") or [""])[0]
    selected_status = (params.get("status") or [""])[0]
    jobs = store.get_jobs(order_by="score", desc=True)
    families = sorted({job["role_family"] for job in jobs if job["role_family"]})
    geos = sorted({job["geo_tag"] for job in jobs if job["geo_tag"]})
    rows = []
    for job in jobs:
        app = store.get_application(job["id"]) or {}
        if selected_family and job["role_family"] != selected_family:
            continue
        if selected_geo and job["geo_tag"] != selected_geo:
            continue
        if selected_status and app.get("status", "not_applied") != selected_status:
            continue
        badge = GEO_BADGE.get(job["geo_tag"] or "unknown", "gray")
        score = f"{job['score']:.0f}" if job["score"] is not None else "-"
        rows.append(f"""<tr>
<td><a href="/job/{job['id']}"><strong>{_esc(job['title'])}</strong></a><br>
<span class="muted">{_esc(job['company'])} &middot; {_esc(job['location'] or '')}</span></td>
<td><span class="score">{score}</span></td>
<td>{_esc(job['role_family'] or '')}</td>
<td><span class="badge {badge}">{_esc(job['geo_tag'] or 'unknown')}</span></td>
<td><a href="{_esc(job['external_url'])}" target="_blank" rel="noopener">apply</a></td>
<td>{_esc(app.get('status', 'not_applied'))}</td>
</tr>""")
    family_options = ''.join(
        f'<option value="{_esc(value)}" {"selected" if value == selected_family else ""}>{_esc(value)}</option>'
        for value in families
    )
    geo_options = ''.join(
        f'<option value="{_esc(value)}" {"selected" if value == selected_geo else ""}>{_esc(value)}</option>'
        for value in geos
    )
    status_options = ''.join(
        f'<option value="{_esc(value)}" {"selected" if value == selected_status else ""}>{_esc(value)}</option>'
        for value in STATUSES
    )
    body = f"""
<div class="card"><form method="get" action="/">
  <label>Family <select name="family"><option value="">all</option>{family_options}</select></label>
  <label>Geo <select name="geo"><option value="">all</option>{geo_options}</select></label>
  <label>Status <select name="status"><option value="">all</option>{status_options}</select></label>
  <button type="submit">Filter</button> <a href="/">Reset</a>
</form></div>
<p class="muted">{len(rows)} matching jobs &middot; first batch is manual and one-shot (docs/OPERATIONS.md)</p>
<table>
<tr><th>Job</th><th>Score</th><th>Family</th><th>Geo</th><th>Apply</th><th>Status</th></tr>
{''.join(rows)}
</table>"""
    return _PAGE.format(BODY=body)


def _page_job(store, job):
    research = job.get("research") or {}
    contacts = job.get("contacts") or []
    drafts = job.get("outreach") or []
    app = job.get("application") or {}
    badge = GEO_BADGE.get(job.get("geo_tag") or "unknown", "gray")
    geo_label = {
        "confirmed_eligible": "Confirmed eligible", "strong_signal": "Strong signal",
        "possible_exception": "Possible exception", "restricted": "Restricted",
        "unknown": "Eligibility unknown",
    }.get(job.get("geo_tag"), "Eligibility unknown")
    family_label = {
        "devops_sre_platform": "DevOps / Platform", "backend_api": "Backend / API",
        "product_engineering": "Product engineering", "ai_first_product": "AI product engineering",
        "technical_pm": "Technical product", "ai_training": "AI evaluation contract",
    }.get(job.get("role_family"), job.get("role_family") or "Unclassified")

    resume_path = app.get("resume_path")
    resume_url = (f'/artifacts/{urllib.parse.quote(Path(resume_path).name)}'
                  if resume_path else None)
    outreach_path = app.get("outreach_path")
    outreach_url = (f'/artifacts/{urllib.parse.quote(Path(outreach_path).name)}'
                    if outreach_path else None)

    resume_action = (f'<a class="button" href="{resume_url}">Download tailored CV</a>'
                     if resume_url else '<span class="badge gray">CV not generated</span>')
    mobile_resume_action = (f'<a class="button" href="{resume_url}">CV</a>'
                            if resume_url else '<span class="button secondary">No CV</span>')
    message_action = (f'<a class="button ghost" href="#leads">View cold message</a>'
                      if drafts else '<span class="muted">No message prepared yet</span>')
    kit_html = f"""
<section class="section" id="application-kit">
  <div class="section-head"><div><h2>Application kit</h2><p>Everything you need to apply manually.</p></div></div>
  <div class="card kit-list">
    <div class="kit-row"><div><strong>Tailored CV</strong><span class="muted">One-page PDF matched to this role.</span></div>{resume_action}</div>
    <div class="kit-row"><div><strong>Cold outreach</strong><span class="muted">{len(contacts)} researched lead{'s' if len(contacts) != 1 else ''} &middot; {len(drafts)} prepared message{'s' if len(drafts) != 1 else ''}</span></div>{message_action}</div>
    <div class="kit-row"><div><strong>Application</strong><span class="muted">Opens the original job listing. Nothing is submitted automatically.</span></div><a class="button secondary" href="{_esc(job['external_url'])}" target="_blank" rel="noopener">Open job &amp; apply</a></div>
  </div>
</section>"""

    contacts_by_id = {c.get("id"): c for c in contacts}
    lead_blocks = []
    for draft in drafts:
        contact = contacts_by_id.get(draft.get("contact_id"), {})
        contact_name = contact.get("name") or "Researched contact"
        role = contact.get("role") or "Role not confirmed"
        source_url = contact.get("evidence_url")
        email = contact.get("email")
        if email:
            channel = f"Email: {_esc(email)}"
        elif source_url:
            channel = "Recommended channel: public profile / LinkedIn DM"
        else:
            channel = "Recommended channel: profile lookup required"
        profile_link = (f'<a class="button ghost" href="{_esc(source_url)}" target="_blank" rel="noopener">Open lead profile</a>'
                        if source_url else '')
        influence = contact.get("hiring_influence") or contact.get("note") or "Relevant company contact"
        lead_blocks.append(f"""
<article class="lead-card">
  <div class="lead-head"><div><h3>{_esc(contact_name)}</h3><p class="muted">{_esc(role)} &middot; {_esc(influence)}</p></div>{profile_link}</div>
  <div class="lead-body">
    <div class="channel">{channel} &middot; Contact confidence: {_esc(contact.get('confidence_label') or 'unverified')}</div>
    <strong>{_esc(draft.get('subject') or 'Cold introduction')}</strong>
    <div class="message" id="draft-{draft['id']}">{_esc(draft.get('body') or '')}</div>
    <div style="margin-top:10px"><button class="secondary" onclick="copyDraft({draft['id']})">Copy message</button><span class="copy-state" id="copied-{draft['id']}" aria-live="polite"></span></div>
  </div>
</article>""")
    if lead_blocks:
        leads_content = "".join(lead_blocks)
    elif contacts:
        lead_rows = []
        for contact in contacts:
            link = (f'<a class="button ghost" href="{_esc(contact.get("evidence_url"))}" target="_blank" rel="noopener">Open profile</a>'
                    if contact.get("evidence_url") else '')
            lead_rows.append(f'<div class="kit-row"><div><strong>{_esc(contact.get("name") or "Researched contact")}</strong><span class="muted">{_esc(contact.get("role") or "Role unconfirmed")} &middot; Message not generated</span></div>{link}</div>')
        leads_content = f'<div class="card kit-list">{"".join(lead_rows)}</div>'
    else:
        query = urllib.parse.quote_plus(f'{job["company"]} hiring manager recruiter engineering LinkedIn')
        leads_content = f"""<div class="empty"><h3>No verified lead found yet</h3>
<p>Mazdoor did not invent a name or email. This job has no cold message because there is no sourced recipient yet.</p>
<p style="margin-top:12px"><a class="button ghost" href="https://www.google.com/search?q={query}" target="_blank" rel="noopener">Search for a public lead</a></p></div>"""
    leads_html = f"""
<section class="section" id="leads">
  <div class="section-head"><div><h2>Leads &amp; cold messages</h2><p>Publicly researched contacts. Copy only. Mazdoor never sends anything.</p></div><span class="badge {'green' if drafts else 'gray'}">{len(drafts)} ready</span></div>
  {leads_content}
</section>"""

    urls = []
    if research:
        try:
            urls = json.loads(research.get("evidence_urls") or "[]")
        except (TypeError, json.JSONDecodeError):
            urls = []
    source_links = "".join(
        f'<li><a href="{_esc(url)}" target="_blank" rel="noopener">Research source {index}</a></li>'
        for index, url in enumerate(urls, 1))
    research_html = f"""
<details class="card section">
  <summary>Company &amp; eligibility research</summary>
  <div class="details-body">
    <p>{_esc(research.get('company_summary') or 'No company summary available.')}</p>
    <p><strong>Remote eligibility:</strong> {_esc(research.get('remote_policy') or job.get('geo_notes') or 'Unknown')}</p>
    <p class="muted">{_esc(research.get('evidence_notes') or '')}</p>
    <ul class="source-list">{source_links}</ul>
  </div>
</details>"""

    status_html = f"""
<div class="card"><h2>Track this application</h2><p class="muted">Update this after you apply or hear back.</p>
<form id="status-form" class="status-form">
  <label class="muted" for="status">Status</label>
  <select id="status">{''.join(f'<option {"selected" if app.get("status")==s else ""}>{s.replace("_", " ").title()}</option>' for s in STATUSES)}</select>
  <label class="muted" for="outcome">Notes or outcome</label>
  <input id="outcome" placeholder="Interview date, response, rejection reason..." value="{_esc(app.get('outcome') or '')}">
  <button type="submit">Save status</button><span class="save-status" id="save-status" aria-live="polite"></span>
</form></div>"""

    description = _render_description(job.get("description") or "")
    description_html = f"""
<details class="card section" id="job-description">
  <summary>Read the full job description</summary>
  <div class="details-body prose">{description}</div>
</details>"""
    advanced_html = f"""
<details class="card section"><summary>Why Mazdoor selected this job</summary><div class="details-body">
<p><strong>Fit rationale:</strong> {_esc(job.get('rationale') or 'Not available')}</p>
<p><strong>Eligibility reasoning:</strong> {_esc(job.get('geo_notes') or 'Not available')}</p>
<p class="muted">Evidence snapshot: {_esc(job.get('source_commit') or 'unknown')}</p>
</div></details>"""

    body = f"""
<a class="back" href="/">&larr; All jobs</a>
<section class="card job-hero">
  <p class="eyeline">{_esc(job['company'])}</p>
  <h1>{_esc(job['title'])}</h1>
  <div class="hero-meta"><span>{_esc(job['location'] or 'Location unknown')}</span><span>Posted {_esc(job['posted_at'] or 'date unknown')}</span><span>Status: <strong>{_esc((app.get('status') or 'not_applied').replace('_',' ').title())}</strong></span></div>
  <div class="metrics">
    <div class="metric"><strong>{job['score']:.0f}/100</strong><span>Fit score</span></div>
    <div class="metric"><strong>{_esc(family_label)}</strong><span>Best role match</span></div>
    <div class="metric"><strong><span class="badge {badge}">{_esc(geo_label)}</span></strong><span>{round((job.get('geo_confidence') or 0) * 100)}% confidence</span></div>
    <div class="metric"><strong>{len(contacts)} lead{'s' if len(contacts) != 1 else ''}</strong><span>{len(drafts)} message{'s' if len(drafts) != 1 else ''} ready</span></div>
  </div>
  <div class="actions">{resume_action}<a class="button ghost" href="#leads">Leads &amp; messages</a><a class="button secondary" href="{_esc(job['external_url'])}" target="_blank" rel="noopener">Open job &amp; apply</a></div>
</section>
<div class="layout">
  <div>{kit_html}</div>
  <aside class="section">{status_html}</aside>
</div>
{leads_html}
{research_html}
{description_html}
{advanced_html}
<nav class="mobile-actions">{mobile_resume_action}<a class="button ghost" href="#leads">Leads</a><a class="button secondary" href="{_esc(job['external_url'])}" target="_blank" rel="noopener">Apply</a></nav>
<script>
async function copyDraft(id) {{
  const text = document.getElementById('draft-' + id).innerText;
  const state = document.getElementById('copied-' + id);
  try {{
    if (navigator.clipboard && window.isSecureContext) {{
      await navigator.clipboard.writeText(text);
    }} else {{
      const area = document.createElement('textarea');
      area.value = text;
      area.style.position = 'fixed'; area.style.opacity = '0';
      document.body.appendChild(area); area.select();
      if (!document.execCommand('copy')) throw new Error('copy failed');
      area.remove();
    }}
    state.textContent = 'Copied';
  }} catch (error) {{
    state.textContent = 'Select the message and copy it manually';
  }}
  window.setTimeout(() => state.textContent = '', 1800);
}}
document.getElementById('status-form').addEventListener('submit', async (event) => {{
  event.preventDefault();
  const select = document.getElementById('status');
  const status = select.options[select.selectedIndex].text.toLowerCase().replaceAll(' ', '_');
  const response = await fetch('/api/job/{job["id"]}/status', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{status, outcome:document.getElementById('outcome').value}})}});
  document.getElementById('save-status').textContent = response.ok ? 'Saved' : 'Could not save. Try again.';
}});
</script>"""
    return _PAGE.format(BODY=body)


def _render_description(text):
    """Render source Markdown safely after dropping job-board chrome."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "tailor my resume" in line.lower():
            lines = lines[index + 1:]
            break
    drop_prefixes = (
        "seniority level", "employment type", "job function", "industries",
        "referrals increase", "get notified about new", "similar jobs",
    )
    cleaned = []
    for line in lines:
        plain = re.sub(r"[*#_`]+", "", line).strip().lower()
        if any(plain.startswith(prefix) for prefix in drop_prefixes):
            break
        if "report this job" in plain or "see who " in plain and "hired" in plain:
            continue
        cleaned.append(line.replace("\\[", "[").replace("\\]", "]"))
    source = "\n".join(cleaned).strip() or text.strip()
    source = source.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return markdown.markdown(source, extensions=["sane_lists"], output_format="html")


def _esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))
