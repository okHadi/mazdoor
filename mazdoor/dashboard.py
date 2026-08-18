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
import mimetypes
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
<title>Mazdoor - local job tracker</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f6f7f9; color: #1a1a1a; }}
  header {{ background: #0f172a; color: #fff; padding: 18px 28px; }}
  header h1 {{ margin: 0; font-size: 20px; }}
  header p {{ margin: 4px 0 0; color: #94a3b8; font-size: 13px; }}
  main {{ padding: 22px 28px; max-width: 1100px; margin: 0 auto; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  th, td {{ text-align: left; padding: 10px 12px; font-size: 13.5px; border-bottom: 1px solid #eef0f3; }}
  th {{ background: #f1f5f9; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #475569; }}
  tr:hover td {{ background: #fafbfc; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }}
  .green {{ background: #dcfce7; color: #166534; }}
  .teal {{ background: #ccfbf1; color: #115e59; }}
  .amber {{ background: #fef3c7; color: #92400e; }}
  .red {{ background: #fee2e2; color: #991b1b; }}
  .gray {{ background: #e2e8f0; color: #475569; }}
  .score {{ font-weight: 700; font-size: 15px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card h2 {{ margin: 0 0 10px; font-size: 16px; }}
  .muted {{ color: #64748b; font-size: 12.5px; }}
  .draft {{ white-space: pre-wrap; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; font-family: ui-monospace, monospace; font-size: 12.5px; line-height: 1.55; }}
  button {{ background: #2563eb; color: #fff; border: 0; border-radius: 6px; padding: 6px 12px; font-size: 12.5px; cursor: pointer; }}
  button.secondary {{ background: #e2e8f0; color: #0f172a; }}
  input, select, textarea {{ font: inherit; padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 6px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 800px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .nav a {{ margin-right: 14px; font-size: 13px; }}
  .ok {{ color: #166534; }}
</style>
</head>
<body>
<header>
  <h1>Mazdoor</h1>
  <p>Local job tracker. Nothing is sent, applied, or scheduled from here.</p>
  <div class="nav" style="margin-top:8px">
    <a href="/" style="color:#93c5fd">Board</a>
    <a href="/api/jobs" style="color:#93c5fd">JSON</a>
  </div>
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
    evidence = ""
    if research:
        urls = json.loads(research.get("evidence_urls") or "[]")
        links = "".join(f'<li><a href="{_esc(u)}" target="_blank" rel="noopener">{_esc(u)}</a></li>'
                        for u in urls)
        evidence = f"""
<div class="card"><h2>Company research</h2>
<p>{_esc(research.get('company_summary') or '')}</p>
<p class="muted">Funding: {_esc(research.get('funding') or 'unknown')} &middot;
Headcount: {_esc(research.get('headcount') or 'unknown')} &middot;
Remote policy: {_esc(research.get('remote_policy') or 'unknown')}</p>
<ul>{links}</ul>
<p class="muted">{_esc((research.get('evidence_notes') or '')[:400])}</p>
</div>"""

    contacts_html = ""
    if contacts:
        rows = "".join(
            f"<li>{_esc(c.get('name') or 'unknown name')} ({_esc(c.get('role') or '')}) "
            f"- {_esc(c.get('email') or '')} "
            f"<span class='badge {'green' if c.get('email_label')=='public' else 'amber'}'>"
            f"{_esc(c.get('email_label') or 'unlabelled')}</span> "
            f"<span class='muted'>conf {c.get('email_confidence')} &middot; "
            f"<a href='{_esc(c.get('evidence_url') or '#')}' target='_blank' rel='noopener'>source</a></span></li>"
            for c in contacts)
        contacts_html = f'<div class="card"><h2>Contacts (public research only)</h2><ul>{rows}</ul></div>'

    drafts_html = ""
    if drafts:
        blocks = []
        for d in drafts:
            blocks.append(
                f'<h3>{_esc(d.get("subject") or "")}</h3>'
                f'<div class="draft" id="draft-{d["id"]}">{_esc(d.get("body") or "")}</div>'
                f'<p><button class="secondary" onclick="copyDraft({d["id"]})">Copy</button></p>')
        drafts_html = f'<div class="card"><h2>Outreach drafts (copy only, nothing is sent)</h2>{"".join(blocks)}</div>'

    artifact_links = []
    for label, stored_path in (
            ("Download tailored resume PDF", app.get("resume_path")),
            ("Download outreach draft", app.get("outreach_path"))):
        if stored_path:
            name = Path(stored_path).name
            artifact_links.append(
                f'<li><a href="/artifacts/{urllib.parse.quote(name)}">{_esc(label)}</a></li>'
            )
    artifacts_html = (
        f'<div class="card"><h2>Prepared artifacts</h2><ul>{"".join(artifact_links)}</ul></div>'
        if artifact_links else '<div class="card"><h2>Prepared artifacts</h2><p class="muted">None yet.</p></div>'
    )
    description_html = (
        f'<div class="card"><h2>Job description</h2><div class="draft">{_esc(job.get("description") or "")}</div></div>'
    )

    status_html = f"""
<div class="card"><h2>Status &amp; outcome</h2>
<form id="status-form">
  <select id="status">{''.join(f'<option {"selected" if app.get("status")==s else ""}>{s}</option>' for s in STATUSES)}</select>
  <input id="outcome" placeholder="outcome / notes" value="{_esc(app.get('outcome') or '')}" size="40">
  <button type="submit">Save</button>
</form>
<p class="muted">Applied at: {_esc(app.get('applied_at') or '-')} &middot; Last update: {_esc(app.get('updated_at') or '-')}</p>
</div>
<script>
function copyDraft(id) {{
  const el = document.getElementById('draft-' + id);
  navigator.clipboard.writeText(el.innerText);
  alert('Copied');
}}
document.getElementById('status-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const resp = await fetch('/api/job/{job["id"]}/status', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{status: document.getElementById('status').value,
                          outcome: document.getElementById('outcome').value}})
  }});
  if (resp.ok) alert('Saved');
}});
</script>"""

    body = f"""
<p><a href="/">&larr; back</a></p>
<div class="card"><h2>{_esc(job['title'])} <span class="muted">at {_esc(job['company'])}</span></h2>
<p class="muted">Location: {_esc(job['location'] or 'unknown')} &middot;
Source: {_esc(job['source'])} &middot; Posted: {_esc(job['posted_at'] or 'unknown')}</p>
<p>Score: <span class="score">{job['score']:.1f}</span> &middot;
Family: <strong>{_esc(job['role_family'] or '')}</strong> &middot;
Geo: <span class="badge {badge}">{_esc(job['geo_tag'] or 'unknown')}</span> (conf {job['geo_confidence']})</p>
<p class="muted">Rationale: {_esc(job.get('rationale') or '')}</p>
<p class="muted">Geo notes: {_esc(job.get('geo_notes') or '')}</p>
<p class="muted">Source commit: {_esc(job.get('source_commit') or 'unknown')}</p>
<p><a class="ok" href="{_esc(job['external_url'])}" target="_blank" rel="noopener"><strong>Open apply link</strong></a></p>
</div>
<div class="grid2">{evidence}{contacts_html}</div>
{artifacts_html}
{status_html}
{drafts_html}
{description_html}
"""
    return _PAGE.format(BODY=body)


def _esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))
