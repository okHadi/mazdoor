# SOURCE_SYNC.md

## Canonical source of truth

- `/home/motabilla/workspace/okHadi/site/content/jobs/<Role>/index.md` - canonical role history, technical scope, exact metric definitions.
- `/home/motabilla/workspace/okHadi/CV/ENG.tex` and `CV/PM.tex` - one-page application views.
- `/home/motabilla/workspace/okHadi/AGENTS.md` - content rules: exact values live on the website; CVs use rounded figures; never invent metrics; never convert booked revenue into ARR; keep titles/dates consistent.

Mazdoor mirrors these in `mazdoor/profile.py`. Serious processing runs refuse a dirty source tree, fetch `origin`, pull with `--ff-only`, and record the resulting commit.

## Sync workflow (when facts change)

1. Update the okHadi website job page first (per okHadi AGENTS.md).
2. Update `mazdoor/profile.py` to match.
3. Update `PROFILE.md` and this doc if the wording changed.
4. Run a real candidate/finalize operation, inspect the generated PDF text, and confirm the recorded source commit matches `git rev-parse HEAD`.

**Exact -> rounded mapping (risk register)**

| Topic | Exact | Rounded (allowed) | Banned |
|---|---|---|---|
| Parhlai users | 8,281 registered / 5,276 MAU | 8k+ / 5k+ | any other number |
| Parhlai revenue | PKR 500,079 booked | 500k+ PKR booked revenue | ARR, $, annualized |
| Parhlai funding | ~1M PKR | ~1M PKR | USD |
| SEO | 4.57M impressions, 162,233 clicks, last 90 days | 4.5M+ / 162k+ | dropping the 90-day window |
| Infra cost | near 1% of total spend | under 1% of total spend | "1% of revenue" |
| Syslify CI cost | ~90% reduction | ~90% | - |
| Syslify incidents | +50% detection | +50% | - |
| Syslify EC2 | ~70% cost reduction | ~70% | - |
| Vfairs | 40+ scrapers, +50% data, 10k users, 50+ devs | same | - |
| Chatly | 5k DAU, 15k+ generations, 2k+ extension users, 10k+ AI Slides users, 200K->1.2M+ MAU, 10M+ sign-ups, $6.5M revenue support | same | - |

## Collection sources (public, keyless)

| Source | Endpoint | Notes |
|---|---|---|
| Remotive | `https://remotive.com/api/remote-jobs?search=...` | public JSON, polite rate limit |
| Greenhouse boards | `https://boards-api.greenhouse.io/v1/boards/<board>/jobs` | public JSON |
| Lever | `https://api.lever.co/v0/postings/<co>?mode=json` | public JSON |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/<co>` | public JSON |
| Verified list | `data/candidates.json` | parent-verified live candidates, ingested via `mazdoor candidates` |

No keys, no login walls, no paid databases. Normalizers never invent fields the source did not provide. A failing source records `source_error` honestly and is excluded from curation.

## Provenance

- Every curated job keeps `source` + `source_id` + `external_url` + raw payload (`raw_json`).
- The exact okHadi git SHA is stored in DB `meta` and on every evaluated job/resume so the profile snapshot is reproducible.
- Research citations carry URL + access date (docs/RESEARCH.md).
