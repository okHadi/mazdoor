# RETENTION.md

Follow-up and tracking so applications don't go dark. Mazdoor only records; it never sends.

## Statuses

| Status | Meaning |
|---|---|
| `not_applied` | In the pipeline, nothing sent yet |
| `prepared` | Resume + outreach draft generated, ready to send manually |
| `applied` | Application submitted (manually) |
| `replied` | Got a human reply |
| `interview` | Interview process active |
| `offer` | Offer received |
| `rejected` | Rejected |
| `ghosted` | No response past the follow-up window |
| `withdrawn` | You pulled out |

Update via the dashboard (`/job/<id>` form) or `POST /api/job/<id>/status` (local only).

## Cadence (manual, tracked in `applications.outcome`/`notes`)

- Day 0: prepare resume + draft; apply if geo tag is `confirmed_eligible` or `strong_signal`; skip or hold `possible_exception` until evidence lands.
- Day 7: follow up once if no reply (use the drafted outreach, recipient-specific).
- Day 14: second follow-up or mark `ghosted` after one more week of silence.
- Ongoing: log every reply/outcome in the dashboard notes; keep the reasoning for `rejected`/`ghosted` so the next batch improves.

## Batch hygiene

- Exactly 10 curated jobs per first batch; new batches are new manual runs (no cron).
- Drop jobs whose apply link 404s or whose geo evidence degrades; record why in `notes`.
- Keep `data/jobs.json` export as the batch snapshot; `meta.okhadi_git_sha` pins the profile snapshot.
