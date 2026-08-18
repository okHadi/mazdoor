# MAZDOOR

Local-first job search MVP: collect, curate, research, score, generate resumes and outreach drafts. Nothing is sent, applied, or scheduled from this tool. All data stays in a local SQLite database (WAL mode) on your machine.


## What it does

- **One-shot collection** from public, keyless job sources (Remotive API, Greenhouse board API, Lever API, Ashby API). A failing source is recorded honestly; jobs are never fabricated.
- **Curation** of exactly `--target` jobs (default 10) scored against a canonical profile across six role families: DevOps/SRE/Platform/Cloud, Backend/API/Automation, Product Engineering, AI-First Product Engineering, Technical PM/Product Owner/Sprint Lead, AI Training/Coding Evaluator. Frontend-heavy roles are penalized, never excluded by title alone.
- **Evidence-backed research** of companies, geo eligibility (confirmed / strong signal / possible exception / restricted / unknown, with citations and confidence), and up to 3 public contacts per job. Emails are stored only when found verbatim in a public source.
- **ATS-friendly one-page PDF resumes** per job, generated from canonical evidence only, with job-specific tailoring (JD keywords surfaced only if they exist in the canonical skill list) and a persisted tailoring plan.
- **Recipient-specific outreach drafts** in the user's voice (see VOICE.md), with automated voice lint. Copy-paste only.
- **Local dashboard** (stdlib `http.server`) for tracking status, outcomes, evidence, apply links, PDFs, and copyable drafts. No send/apply endpoints exist.

## Quick start

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"

# 1. one-shot run (first batch: exactly 10 curated jobs)
.venv/bin/python -m mazdoor.cli collect --target 10

# 2. ingest parent-verified candidate jobs (exact 10) instead of collector rows
.venv/bin/python -m mazdoor.cli candidates --file data/candidates.json

# 3. ingest manual research (company/geo/contacts with citations)
.venv/bin/python -m mazdoor.cli research --file data/research.json

# 4. regenerate geo + resumes + drafts from the curated set
.venv/bin/python -m mazdoor.cli finalize

# 5. verify real artifacts and render PNGs for visual inspection
.venv/bin/python -m mazdoor.cli verify --expect 10 --render artifacts/rendered

# 6. export the deliverable shape and run the dashboard
.venv/bin/python -m mazdoor.cli export --out data/jobs.json
.venv/bin/python -m mazdoor.cli serve --host <tailscale-ip> --port 8765
# open http://<tailscale-ip>:8765
```

## Commands

| Command | Purpose |
|---|---|
| `collect` | One-shot fetch + curate + research + generate (no scheduling) |
| `candidates` | Load a verified candidate list from JSON and curate it |
| `research` | Ingest manual research JSON (company/geo/contacts) |
| `finalize` | Regenerate geo/resumes/drafts for curated jobs |
| `verify` | Check PDFs/drafts/DB against hard rules; `--render` renders PNGs for visual inspection |
| `export` | Write `data/jobs.json` (10 curated jobs with evidence) |
| `serve` | Local dashboard (tracking/copy only) |

## Data model

SQLite (WAL) at `data/mazdoor.db`:

- `jobs` - raw + curated job, score, role family, geo tag/confidence/notes, rationale, tailoring plan
- `company_research` - summary, evidence URLs, funding, headcount, remote policy
- `contacts` - up to 3 public contacts per job, source evidence + confidence + hiring influence
- `applications` - status (`not_applied`, `prepared`, `applied`, `replied`, `interview`, `offer`, `rejected`, `ghosted`, `withdrawn`), dates, notes, outcomes, artifact paths
- `outreach_drafts` - subject + body per job/contact
- `meta` - e.g. exact okHadi git SHA captured at collection time

## Documentation

- [docs/SOURCE_SYNC.md](docs/SOURCE_SYNC.md) - canonical source of truth and sync workflow
- [docs/SCORING.md](docs/SCORING.md) - role families, scoring, frontend penalty, seniority
- [docs/RESEARCH.md](docs/RESEARCH.md) - geo eligibility classes, citations, contact rules
- [docs/RESUMES.md](docs/RESUMES.md) - ATS rules, tailoring, verification steps
- [docs/OUTREACH.md](docs/OUTREACH.md) - voice rules and draft structure
- [docs/RETENTION.md](docs/RETENTION.md) - follow-up cadence, statuses, notes
- [docs/OPERATIONS.md](docs/OPERATIONS.md) - runbook, verification checklist, ingest contract
- [docs/OPEN_SOURCE.md](docs/OPEN_SOURCE.md) - license-compatible usage and attribution
- [PROFILE.md](PROFILE.md), [VOICE.md](VOICE.md), [AGENTS.md](AGENTS.md)

## Hard rules

- Parhlai revenue is **PKR 500,079 in booked revenue** (rounded: 500k+ PKR). Never ARR, never USD, never annualized.
- No auto-send, no auto-apply, no cron. Every run is manual and one-shot.
- No fabricated jobs, companies, contacts, citations, or PDFs. Failures are recorded honestly.
- Only canonical facts from the okHadi source (exact git SHA recorded globally and on every evaluated job/resume).
- No secrets, no keys, and no private contact data. Generated resumes and drafts omit the phone number.
