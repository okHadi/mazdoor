# OUTREACH.md

## Mandatory skill process

`cold-email-writer` -> `VOICE.md` -> `humanizer`:

1. **cold-email-writer**: research before writing (company angle, recipient name, relevant projects, stack overlap); hook must be specific.
2. **VOICE.md**: the user's supplied sample is the voice authority: "Hey Name, / I'm Hadi. Product Engineer." Short direct fragments, quantified hook, no em dashes, no filler, no chat typos.
3. **humanizer**: final pass strips AI tells (rule-of-three, -ing fake depth, reassurance kickers, "it's not just X, it's Y", generic positive conclusions).

## Draft anatomy

```
Subject: Quick intro - Hadi Khan

Hey {Name},

I'm Hadi. Product Engineer.

[Specific hook: company research line or the role reference]

I also run Parhlai. 8,281 users. PKR 500,079 booked revenue. Built its AWS and Cloudflare stack, with infra near 1% of total spend.

{Family evidence line in short fragments.}

The {job title} role at {company} looks close to that work.

More about me: https://mhadi.dev

Hope to talk to you :)

Hadi
hello@mhadi.dev
```

Per-family evidence lines are fixed canonical facts (see `mazdoor/outreach.py`), e.g.:
- DevOps: "At Syslify, I manage Terraform across 100+ AWS accounts, Control Tower, OpenShift, and disaster recovery. Also built CI that cut runner costs ~90%."
- AI-first: "I build with Claude Code and Codex every day. Shipped Chatly's AI extension in 2 weeks to 2,000+ users. Led OmniAgent to 5,000 DAUs."
- Technical PM: "I led a 10-engineer cross-functional team, ran the roadmap with PostHog, and shipped production PRs alongside engineering."

## Rules (hard)

- Quantified proof uses verified wording; revenue is **booked revenue**, never ARR (the token `ARR` is banned everywhere, even defensively).
- Revenue is not claimed to be organic; acquisition was organic (SEO, Reddit, referrals).
- No private data: no phone, no personal email; sign `Hadi` + `hello@mhadi.dev`.
- Recipient-specific greeting when a public contact exists; no invented recipients, no invented hooks. Generic hooks are flagged (`hook_warning`).
- Length 60-400 words; short wins.

## Automation

- `mazdoor finalize` generates one draft per **real** contact (DB `contacts`), writes `artifacts/outreach_<jobid>_<company>.md` with the recipient's source URL, channel, and email label, and stores subject/body in the DB.
- `mazdoor verify` lints every draft file: zero em dashes, zero banned filler, zero chat typos, no ARR token, canonical email present, no private data.

Nothing is sent from Mazdoor. Drafts are copy-paste only.
