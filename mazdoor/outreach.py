"""Recipient-specific outreach drafts (docs/OUTREACH.md, VOICE.md).

Voice rules (authoritative: user's supplied outreach sample):
  - Short, direct fragments. "Hey Name," then "I'm Hadi. Product Engineer."
  - A quantified, verified hook. No invented numbers.
  - No em dashes (use plain hyphens), no filler, no corporate language.
  - No deliberate misspellings or chat-style abbreviations.
  - Only canonical public contact info (hello@mhadi.dev), never the phone
    number, never any private email.
  - Parhlai revenue is "PKR 500,079 in booked revenue" / "500k+ PKR booked
    revenue". Never ARR, never USD.
"""

import re

from .profile import load

BANNED_FILLER = [
    "i am writing to express", "i hope this finds you well", "i look forward to hearing",
    "i would love the opportunity", "please find attached", "in today's fast-paced",
    "leverage", "passionate about", "excited to potentially", "additionally",
    "moreover", "furthermore", "i believe that", "it would be a privilege",
    "i am confident that", "as you can see", "in conclusion",
]

GENERIC_HOOK_MARKERS = [
    "love what you're building", "mission resonates", "generic compliment",
    "great company", "amazing work", "i admire your", "your innovative",
    "cutting-edge", "world-class team", "i was impressed by your website",
]

CHAT_TYPO_RE = [
    r"\bgonna\b", r"\bwanna\b", r"\bplz\b", r"\bthx\b", r"\bbtw\b",
    r"\brn\b", r"\bu\b", r"\bya\b", r"\bnvm\b", r"\bidk\b", r"\btbh\b",
    r"\blmk\b", r"\bur\b", r"\bpls\b", r"\bcuz\b",
]

# Per-family evidence lines: canonical facts only
_FAMILY_EVIDENCE = {
    "devops_sre_platform": (
        "At Syslify, I manage Terraform across 100+ AWS accounts, Control Tower, "
        "OpenShift, and disaster recovery. Also built CI that cut runner costs ~90%."
    ),
    "backend_api": (
        "Python and TypeScript. Event-driven AWS systems, 40+ production scrapers, "
        "and backend work that supported 50+ developers."
    ),
    "product_engineering": (
        "I shipped AI features end to end and scaled a platform from 200K "
        "to 1.2M+ MAUs."
    ),
    "ai_first_product": (
        "I build with Claude Code and Codex every day. Shipped Chatly's AI extension "
        "in 2 weeks to 2,000+ users. Led OmniAgent to 5,000 DAUs."
    ),
    "technical_pm": (
        "I led a 10-engineer cross-functional team, ran the roadmap with "
        "PostHog, and shipped production PRs alongside engineering."
    ),
    "ai_training": (
        "I review production code daily: Python, TypeScript, and Terraform "
        "across AWS and Cloudflare."
    ),
}

_PARHLAI_LINE = (
    "I also run Parhlai. 8,281 users. PKR 500,079 booked revenue. "
    "Built its AWS and Cloudflare stack, with infra near 1% of total spend."
)


def build_draft(ctx):
    """Build one outreach draft for a job/contact context dict.

    ctx keys: job_title, company, company_hook, role_family, evidence,
    contact_name, contact_role, contact_email, email_label.
    Returns dict: subject, body, email_warning, hook_warning, words.
    """
    p = load()
    name = ctx.get("contact_name")
    role = ctx.get("contact_role")
    company = ctx.get("company", "")
    job_title = ctx.get("job_title", "")
    family = ctx.get("role_family", "devops_sre_platform")
    hook = (ctx.get("company_hook") or "").strip()
    evidence = (ctx.get("evidence") or _FAMILY_EVIDENCE.get(family, "")).strip()

    # --- hook quality check ------------------------------------------------
    hook_low = hook.lower()
    hook_warning = any(m in hook_low for m in GENERIC_HOOK_MARKERS) or len(hook) < 40

    # --- subject -------------------------------------------------------------
    subject = "Quick intro - Hadi Khan"

    # --- body ----------------------------------------------------------------
    first_name = name.split()[0] if name else None
    greeting = f"Hey {first_name}," if first_name else "Hey,"
    parts = [greeting, "", "I'm Hadi. Product Engineer.", ""]

    if hook and not hook_warning:
        parts.append(hook)
        parts.append("")
    else:
        parts.append(f"I found the {job_title} role at {company} and the work your team ships is the reason I'm reaching out.")
        parts.append("")

    parts.append(_PARHLAI_LINE)
    parts.append("")
    parts.append(evidence)
    parts.append("")
    parts.append(f"The {job_title} role at {company} looks close to that work.")
    parts.append("")
    parts.append("More about me: https://mhadi.dev")
    parts.append("")
    parts.append("Hope to talk to you :)")
    parts.append("")
    parts.append("Hadi")
    parts.append(p["email"])

    body = "\n".join(parts)

    email = ctx.get("contact_email")
    profile_url = ctx.get("contact_profile") or ""
    if email:
        channel = "email"
    elif "linkedin.com" in profile_url:
        channel = "linkedin_dm"
    else:
        channel = "profile_lookup_required"

    return {
        "subject": subject,
        "body": body,
        "channel": channel,
        "email_warning": ctx.get("email_label") == "guessed",
        "hook_warning": hook_warning,
        "words": len(body.split()),
    }


def lint_draft(draft):
    """Voice lint: returns list of rule violations (empty = clean)."""
    body = draft["body"]
    text = f"{draft['subject']}\n{body}"
    low = text.lower()
    issues = []
    if "—" in text or "–" in text:
        issues.append("em/en dash found")
    for phrase in BANNED_FILLER:
        if phrase in low:
            issues.append(f"filler: '{phrase}'")
    for pat in CHAT_TYPO_RE:
        if re.search(pat, text, re.I):
            issues.append(f"chat typo/abbrev: '{pat}'")
    if re.search(r"\barr\b", text, re.I):
        issues.append("ARR token present (forbidden everywhere)")
    if "hello@mhadi.dev" not in body:
        issues.append("missing canonical email hello@mhadi.dev")
    if "+92" in body or "khan.hadi2951@gmail.com" in low:
        issues.append("private contact data leaked")
    if not (60 <= draft["words"] <= 400):
        issues.append(f"length {draft['words']} outside 60..400")
    return issues
