# OPERATIONS.md

## Runbook (first batch, manual and one-shot)

```bash
# environment
cd /home/motabilla/workspace/mazdoor
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# 1. OPTIONAL live-source probe (proves collectors work; raw rows only)
.venv/bin/python -m mazdoor.cli collect --db data/live_probe.db --target 0 --sources all

# 2. ingest the parent-verified 10 candidates (exact JSON, no guessing)
.venv/bin/python -m mazdoor.cli candidates --file data/candidates.json

# 3. ingest manual research (company/geo/contacts with citations)
.venv/bin/python -m mazdoor.cli research --file data/research.json

# 4. regenerate geo + resumes + drafts for the curated set
.venv/bin/python -m mazdoor.cli finalize

# 5. verify hard rules + render PNGs for visual inspection
.venv/bin/python -m mazdoor.cli verify --expect 10 --render artifacts/rendered

# 6. export batch snapshot + dashboard
.venv/bin/python -m mazdoor.cli export --out data/jobs.json
.venv/bin/python -m mazdoor.cli serve --host <tailscale-ip> --port 8765
```

No cron. No scheduling code exists anywhere in this project.

## Ingest contract (for the parent / future batches)

### data/candidates.json

A JSON array of job dicts (or `{"jobs": [...]}`):

```json
[
  {
    "source": "verified",
    "source_id": "sw-4454471966",
    "external_url": "https://pk.linkedin.com/jobs/view/...",
    "title": "Senior DevSecOps Engineer",
    "company": "Smart Working",
    "location": "Hyderabad, Sindh, Pakistan (Remote)",
    "description": "full JD text (>= 25 chars)",
    "description_url": "https://pk.linkedin.com/jobs/view/...",
    "posted_at": "2026-08-18",
    "salary": null,
    "raw_json": null,
    "source_error": null
  }
]
```

`mazdoor candidates` upserts each, then curates them (scores, role family, geo signal, rationale) to exactly the list length.

### data/research.json

A JSON array keyed by `job_id` (the DB id printed by `mazdoor candidates` / visible in the dashboard):

```json
[
  {
    "job_id": 1,
    "company_summary": "...",
    "evidence_urls": "[\"https://...\"]",
    "evidence_notes": "careers page (2026-08-18): hiring worldwide including Pakistan",
    "funding": "Series B",
    "headcount": "150 employees",
    "remote_policy": "Remote-first, hires worldwide",
    "geo": {
      "tag": "confirmed_eligible",
      "confidence": 0.8,
      "citations": [
        {"url": "https://acme.com/careers", "accessed": "2026-08-18",
         "note": "hiring worldwide including APAC"}
      ]
    },
    "contacts": [
      {
        "name": "Mira Chen", "role": "Head of Platform",
        "source": "team page", "email": "mira@acme.com",
        "email_label": "public", "email_confidence": 0.95,
        "evidence_url": "https://acme.com/team",
        "note": "listed on public team page",
        "confidence_label": "high",
        "hiring_influence": "hiring manager for this role",
        "role_is_current": 1
      }
    ]
  }
]
```

If `geo` is omitted, the tag is derived from `evidence_notes` via the same strict rules (only explicit worldwide/anywhere/Pakistan/APAC confirm). Contacts are capped at 3; absent contacts stay absent (no invention).

## Verification checklist (per batch)

- [ ] exactly 10 curated jobs (or fewer with honest reasons; never padded)
- [ ] every apply URL live (or recorded failure)
- [ ] geo tag + citations (URL + access date) per job
- [ ] contacts: source URL + confidence label; none from login walls
- [ ] PDFs: 1 page, text-based, no em dash, no ARR, no phone, booked-revenue phrasing
- [ ] PNG renders inspected for clipping/overlap/overflow
- [ ] drafts: voice lint clean; recipient-specific only where a real contact exists
- [ ] dashboard exercised through its real Tailscale URL; filters, details, PDF download, and status update work
- [ ] `curl` confirms the HTML, JSON, artifact, and POST routes against the running server
- [ ] SQLite inspection confirms WAL mode, source commits, evidence, contacts, and preserved artifact paths
- [ ] no cron entries; nothing scheduled
- [ ] `.gitignore` excludes `.venv/`, `data/`, `artifacts/`, `*.db*`; secret scan clean
- [ ] `data/jobs.json` exported

## Troubleshooting

- **SQLite "database is locked"**: WAL mode + a single Store per process; the dashboard and CLI should not write the same DB concurrently.
- **Source flaky (429/Cloudflare)**: failures land in `source_error` and in the state dict; curation continues with what actually arrived.
- **PDF overflow**: the builder uses four relevant role blocks and a 9pt floor, then reduces bullet budgets. If a PDF still overflows, remove lower-value evidence rather than shrinking below the floor.
- **Search backend empty**: record `unknown`/no-evidence honestly rather than guessing (docs/RESEARCH.md).
