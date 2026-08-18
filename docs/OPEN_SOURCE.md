# OPEN_SOURCE.md

Mazdoor is a local, personal tool. Its own code is MIT (see pyproject.toml). Anything borrowed or derived must come from license-compatible open source with attribution.

## Dependencies (all permissive)

| Dependency | License | Use |
|---|---|---|
| reportlab | BSD-3-Clause | PDF generation (embedded text, ATS-friendly) |
| pypdfium2 | Apache-2.0 / BSD-3-Clause | PDF -> PNG render for visual verification |
| pypdf | BSD-3-Clause | text extraction in tests/verify |
| requests | Apache-2.0 | HTTP fetching |
| beautifulsoup4 | MIT | HTML parsing for normalizers/research |
| pytest | MIT | tests |

## Concepts and code borrowed

- **job-description-analyzer, resume-tailor, resume-ats-optimizer, cold-email-writer, humanizer** (Hermes skills): process guidance only (requirement classification, tailoring honesty rules, ATS checks, outreach structure, anti-AI-slop patterns). No code copied; Mazdoor implements the behavior natively.
- **humanizer skill patterns**: ported by Hermes Agent from [blader/humanizer](https://github.com/blader/humanizer) (MIT), based on Wikipedia's "Signs of AI writing". The tell-list is encoded in `mazdoor/outreach.py` (BANNED_FILLER, GENERIC_HOOK_MARKERS, CHAT_TYPO_RE).
- **okHadi repository** (`/home/motabilla/workspace/okHadi`): source of canonical facts (facts, not code). Read-only; never modified. Exact commit SHA recorded in DB `meta.okhadi_git_sha`.

## Public data sources (not code)

- Remotive API, Greenhouse board API, Lever API, Ashby API: public JSON endpoints used per their terms (link back to source URLs; no republishing to third-party boards).
- Company websites, public LinkedIn job pages: fetched for research; citations retained.

## No copied proprietary content

- No code or text from closed-source or unknown-license repositories.
- Job descriptions are stored as fetched evidence (`raw_json`, `description`) for local curation only, per the source APIs' terms.
- If in doubt, don't copy: reimplement the behavior and attribute the inspiration.

## Attribution notes

- Resume PDF rendering follows okHadi/AGENTS.md verification rules (render to PNG, inspect for clipping).
- Outreach voice rules trace to the user's supplied sample (VOICE.md); the humanizer's tell-pattern taxonomy is attributed above.
