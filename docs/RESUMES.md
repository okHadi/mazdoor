# RESUMES.md

## ATS rules (every generated PDF)

- **One page** (A4). The builder uses focused role blocks and a 9pt font floor, then reduces bullet budgets before it would overflow.
- **Text-based PDF** (reportlab embeds real text), no images, no tables, single column.
- **Standard section names**: Summary, Skills, Experience, Education (in that order).
- **Contact block in the body** (never header/footer): `hello@mhadi.dev`, LinkedIn, website, GitHub. No phone or full address.
- **No em dashes** (ATS encoding + voice rule); dates use `Mar 2024 - Present` (hyphen).
- **Searchable technology names** spelled out: Terraform, AWS, Cloudflare, Kubernetes, OpenShift, GitHub Actions, Docker, Python, etc.
- Consistent date format across entries; filename `Hadi_Khan_<Family>_<Company>_<JobTitle>.pdf` (no spaces/special chars).

## Job-specific tailoring

`resume.generate(path, family=..., job={title, company, description})`:

1. **Summary** is family-based, then names the target title/company and up to five JD-matched canonical skills.
2. **JD keywords are surfaced ONLY if they exist in the canonical skill list** (`jd_keywords_matched`). A JD mentioning "kafka3" (not canonical) never appears; "postgresql" (canonical) does.
3. **Bullets are selected** from four role-family-specific experience blocks, then re-ranked by JD relevance and verified impact.
4. **Skills are focused** to the three most relevant canonical groups rather than dumping the full skill library.
5. **Tailoring plan persisted**: a title-specific sidecar next to each PDF and JSON in `jobs.tailoring_plan` records family, matched keywords, summary, bullet budget, and generation date.

## Verification (per AGENTS.md)

1. `python -m mazdoor.cli verify --expect 10 --render artifacts/rendered`:
   - page count == 1 per PDF
   - text extraction contains key terms and correct Parhlai phrasing ("booked revenue")
   - no `ARR` token, no em/en dash, no phone
   - drafts pass voice lint
   - curated count matches
2. **Render each final PDF to PNG** and inspect `artifacts/rendered/*.png` for clipping, overlap, unreadable text, or accidental page overflow.
3. Confirm the PDF is text-based (pypdf extraction succeeds) and the download copy matches the repo build.

## Canonical-only content

Every bullet comes from `mazdoor/profile.py` (okHadi canonical). No invented metrics, no reworded claims beyond the exact->rounded mapping in docs/SOURCE_SYNC.md.
