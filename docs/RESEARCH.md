# RESEARCH.md

## Principles

- Public, keyless sources only: company sites, public job boards, public GitHub/LinkedIn profiles, news. No login walls, no paid lead databases, no scraping of recruiter PII.
- Every claim carries a citation (URL + access date) and a confidence score.
- If nothing is found, that is recorded honestly (geo `unknown`, empty evidence, no invented contacts).

## Geo eligibility research

Per job, research whether the company hires remote from Pakistan/APAC:

1. JD/location text is a **starting signal only**. Only explicit `worldwide`, `anywhere`, `pakistan`, `south asia`, `apac` confirm from the JD. `fully remote`/`remote-first` alone do not.
2. Independent evidence upgrades/downgrades: company careers pages, help-center hiring policy, engineering blog, news.
3. Record the evidence as citations (URL + access date) and a confidence score.

Classes: `confirmed_eligible` | `strong_signal` | `possible_exception` | `restricted` | `unknown`.

Example citation entry stored in `geo_notes`:
```
careers page (https://acme.com/careers, accessed 2026-08-18): "hiring worldwide across APAC, EMEA, Americas"
```

## Company research fields

- `company_summary` - what the company does (from public about page, with URL).
- `evidence_urls` - JSON list of URLs used.
- `evidence_notes` - dated notes per evidence item.
- `funding` / `headcount` / `remote_policy` - only if found; `null` otherwise.

## Contacts (max 3 per job)

- Sources: company careers/team pages, public LinkedIn profiles, GitHub org pages. Never behind login walls.
- **Email labels**:
  - `public` - email found verbatim in a public page.
  - `unverified` - no public email was found. Keep the field empty and use the sourced public profile when available.
- Fields: name, role, source URL, email, email label, confidence (0-1), `confidence_label` (high/medium/low), `hiring_influence` (e.g. "hiring manager for this role", "general inbox"), `role_is_current`.
- Never synthesize a company domain or inbox pattern. If no public contact exists, the job ships with zero contacts and no invented draft recipient.

## Honest failure modes

- Live page blocked (Cloudflare, login wall): note it in `evidence_notes`/`source_error`; use the best public alternative (e.g. digest snapshot) and say so.
- Search backend flaky: skip gracefully, mark geo `unknown` rather than guessing.
- Never fabricate a company summary, funding round, headcount, or remote policy.
