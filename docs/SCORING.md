# SCORING.md

## Role families

Jobs are classified into one of six families (required behavior):

1. `devops_sre_platform` - DevOps / SRE / Platform / Cloud
2. `backend_api` - Backend / API / Automation
3. `product_engineering` - Product Engineering
4. `ai_first_product` - AI-First Product Engineering (Claude Code / Codex / AI agents)
5. `technical_pm` - Technical PM / Product Owner / Sprint Lead
6. `ai_training` - AI Training / Coding Evaluator contracts

### Classification rules

1. **Title patterns first** (strong role signals): "product manager/owner", "sprint lead" -> technical_pm; "ai trainer/evaluator/annotator/rater" -> ai_training; "devops/sre/platform/cloud/infrastructure engineer" -> devops; "backend/api/automation/integration/full-stack" -> backend.
2. **Description patterns**: explicit "Claude Code", "Codex", "AI agents", "agentic", "prompt engineering" -> ai_first_product; explicit "Terraform/Kubernetes/Control Tower/GitHub Actions/CI/CD" -> devops.
3. **Keyword scoring fallback** for adjacent titles ("Software Engineer" + infra description classifies devops; title hits weighted x3).

**Never exclude based on title alone.** Adjacent titles are classified by description evidence.

## Match score (0-100)

```
coverage = min(1.0, family_keyword_hits / min(len(family_keywords), 12))
base     = 40 + coverage * 55
score    = clamp(base - frontend_penalty + seniority_adjustment, 0, 100)
```

- Keyword coverage dominates; the capped denominator (12) stops large keyword lists from diluting strong hits.
- **Frontend penalty** (0-40): each distinct frontend signal (`react`, `css`, `figma`, `design system`, `ux`, `tailwind`, ...) word-bounded adds weight; never a hard exclusion. Explicit frontend-only roles (no API/backend/database/infra terms) are capped at 35.
- **Seniority**: mid preferred (+0), senior accepted (+1), junior (-3), ambiguous (-1).

Interpretation: 75-89 excellent fit; 60-74 good fit (apply with strong outreach); 50-59 stretch; <50 weak (frontend-heavy or thin keyword coverage).

## Curation

- `curate(jobs, target)` drops empty descriptions (<25 chars), source errors, and unscored rows; ranks by score; keeps exactly `target` (or fewer with honest reasons, never padded).
- Rationale recorded per job: family label, keyword hit count, frontend penalty, score.

## Geo eligibility (separate research step, docs/RESEARCH.md)

- `confirmed_eligible` - explicit worldwide/anywhere/Pakistan/APAC from JD **or** independent evidence.
- `strong_signal` - positive but not a written policy.
- `possible_exception` - remote but region unspecified; needs evidence.
- `restricted` - explicit regional limits or sponsorship requirements.
- `unknown` - no public evidence.

"Fully remote" / "remote-first" / "100% remote" alone do **not** confirm eligibility. Every tag carries citations and a confidence score.
