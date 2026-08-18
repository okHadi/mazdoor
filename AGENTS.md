# Mazdoor AGENTS.md

Operational rules for AI agents working in this repository. Read before making changes.

## Source of truth

- `mazdoor/profile.py` is the **only** place candidate facts live. Every fact traces to `/home/motabilla/workspace/okHadi/site/content/jobs/*/index.md` and `CV/ENG.tex` (see docs/SOURCE_SYNC.md).
- Do not add, remove, or reword metrics in `profile.py` without updating the okHadi canonical source first (okHadi/AGENTS.md sync workflow).
- The exact okHadi git SHA at collection time is recorded in the DB `meta` table and on every evaluated job/resume record.

## Hard rules (non-negotiable)

1. **Parhlai = 500k+ PKR booked revenue, NEVER ARR.** Banned anywhere in output (PDFs, drafts, docs): `ARR`, `annual recurring revenue`, `annualized`, USD-denominated revenue. Exact: PKR 500,079 combined consumer and B2B booked revenue. Rounded: "500k+ PKR booked revenue".
2. **No em dashes** in PDFs, drafts, or docs. Use plain hyphens. Dates use `Mar 2024 - Present` style.
3. **Do not put a phone number on generated resumes or drafts.** Never expose the full number. Never use `khan.hadi2951@gmail.com` or any private account.
4. **No fabrication.** No invented jobs, companies, contacts, metrics, citations, or PDFs. Live source failures are recorded honestly (`source_error`); geo tags include `unknown`; missing contacts stay missing.
5. **No auto-send, no auto-apply, no cron.** The CLI has collect/serve/verify only; nothing schedules itself.
6. **JD keywords on resumes only if canonical.** `jd_keywords_matched` filters against the canonical skill list in `profile.py` before surfacing on a resume.
7. **Geo eligibility is researched, not guessed.** Only explicit worldwide/anywhere/Pakistan/APAC terms confirm from the JD; `fully remote`/`remote-first` alone do not. Independent evidence (URL + access date) is required for the final tag.
8. **Contacts: public/keyless only, up to 3 per job.** Store an email only when found verbatim in a public source. Missing emails stay missing. Never synthesize inboxes or company domains. No login walls, paid databases, or recruiter PII harvesting.
9. **Voice authority is the supplied outreach sample** (see VOICE.md): short direct fragments, quantified hook, no filler, no chat typos/lowercase abbreviations. Do not imitate misspellings.
10. **Do not add or modify automated tests unless Hadi explicitly asks.** Validate changes against the running system: launch the dashboard, exercise it in a real browser, call live endpoints with `curl`, inspect SQLite state, generate real PDFs, extract their text, and visually inspect rendered output. Existing tests may be run as a regression signal, but do not make test authoring the implementation workflow.

## Verification workflow (after any artifact generation)

1. Run `python -m mazdoor.cli verify --expect 10 --render artifacts/rendered` against real artifacts.
2. Launch the dashboard on the actual bind address. Exercise list, detail, artifact download, filters, and status updates in a real browser.
3. Use `curl` to verify HTTP status, response content, artifact delivery, and POST behavior independently of the browser.
4. Inspect SQLite directly to confirm writes, preserved artifact paths, WAL mode, source commits, research evidence, contacts, and application history.
5. Inspect every rendered PNG for clipping, overlap, unreadable text, or page overflow.
6. Check `python -m mazdoor.cli export` output (`data/jobs.json`) carries evidence URLs and citations.

## Conventions

- Python 3.11+, stdlib-first; extra deps only for PDF/render (reportlab, pypdfium2) and HTTP (requests, bs4).
- SQLite WAL mode; `check_same_thread=False` + RLock so the dashboard can serve from worker threads.
- Existing tests live in `tests/` and may be run as a regression signal. Do not add or modify them without explicit approval.
- Filenames: `Hadi_Khan_<Family>_<Company>_<JobTitle>.pdf` (ATS-safe, no spaces).
