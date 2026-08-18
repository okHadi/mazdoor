"""Tests for outreach draft generation: VOICE.md rules, recipient-specific, no AI slop."""

import re

from mazdoor import outreach
from mazdoor.profile import load


def _ctx(**kw):
    base = dict(
        job_title="Senior DevOps Engineer",
        company="Acme",
        company_hook="Your Terraform-account-tagging series on the engineering blog is the reason I found the role.",
        role_family="devops_sre_platform",
        evidence="tagging across 100+ AWS accounts",
        contact_name="Mira",
        contact_role="Head of Engineering",
        contact_email="mira@acme.com",
        email_label="public",
    )
    base.update(kw)
    return base


def test_draft_starts_with_hey_and_blunt_intro():
    d = outreach.build_draft(_ctx())
    assert d["subject"]
    assert d["body"].startswith("Hey Mira,")
    assert "I'm Hadi. Product Engineer." in d["body"]


def test_no_em_dashes():
    d = outreach.build_draft(_ctx())
    for part in (d["subject"], d["body"]):
        assert "—" not in part
        assert "–" not in part


def test_no_filler_corporate_language():
    d = outreach.build_draft(_ctx())
    banned = [
        "I am writing to express", "I hope this finds you well",
        "I look forward to hearing from you", "I would love the opportunity",
        "Please find attached", "in today's fast-paced", "leverage",
        "passionate about", "excited to potentially",
    ]
    low = d["body"].lower()
    for phrase in banned:
        assert phrase not in low, phrase


def test_quantified_proof_uses_verified_metrics():
    d = outreach.build_draft(_ctx())
    assert "8,281" in d["body"] or "8281" in d["body"] or "8k" in d["body"]
    assert "500,079" in d["body"] or "500k" in d["body"] or "PKR 500" in d["body"]


def test_arr_token_never_appears():
    """The token ARR must not appear anywhere in outreach (not even a
    defensive 'not ARR' sentence)."""
    import re
    d = outreach.build_draft(_ctx())
    assert not re.search(r"\barr\b", d["body"], re.I)


def test_revenue_not_claimed_organic():
    """Do not claim the revenue itself was organic; only acquisition was."""
    d = outreach.build_draft(_ctx())
    assert "all organic" not in d["body"]


def test_recipient_specific_name_and_role():
    d = outreach.build_draft(_ctx(contact_name="Zain", contact_role="CTO"))
    assert d["body"].startswith("Hey Zain,")
    assert "CTO" in d["body"] or "you" in d["body"]


def test_guessed_email_gets_warning():
    d = outreach.build_draft(_ctx(email_label="guessed"))
    assert d["email_warning"] is True


def test_public_email_no_warning():
    d = outreach.build_draft(_ctx(email_label="public"))
    assert d["email_warning"] is False


def test_fallback_when_no_contact_name():
    d = outreach.build_draft(_ctx(contact_name=None, contact_role=None, contact_email=None))
    assert d["body"].startswith("Hey,")


def test_draft_length_bounds():
    d = outreach.build_draft(_ctx())
    words = len(d["body"].split())
    assert 60 <= words <= 400, words


def test_hook_must_be_company_specific():
    d = outreach.build_draft(_ctx(company_hook="Generic compliment about your mission"))
    # generic hooks should be flagged or replaced; the builder validates hooks
    assert d["hook_warning"] is True


def test_humanizer_pass_applied_to_drafts():
    """Drafts must pass the humanizer's core tells: no rule-of-three forced lists,
    no em dash, no -ing fake depth, no reassurance kickers."""
    d = outreach.build_draft(_ctx())
    body = d["body"]
    for tell in ["And that's okay", "It's not just about", "no guessing"]:
        assert tell not in body


def test_no_chat_misspellings_or_lowercase_abbrevs():
    """Voice authority is the supplied outreach sample, not casual chat typos.
    No deliberate misspellings or lowercase abbreviations."""
    d = outreach.build_draft(_ctx())
    low = d["body"].lower()
    for typo in ["gonna", "wanna", "plz", "thx", "btw", "rn ", "u want", "ya "]:
        assert typo not in low, typo


def test_no_private_data_in_outreach():
    d = outreach.build_draft(_ctx())
    body = d["body"].lower()
    assert "khan.hadi2951@gmail.com" not in body
    assert "+92" not in body
    assert "hello@mhadi.dev" in d["body"]  # only canonical public email


def test_job_specific_reference_present():
    d = outreach.build_draft(_ctx(job_title="Senior DevOps Engineer", company="Acme"))
    assert "Acme" in d["body"]
    assert "DevOps" in d["body"]


def test_full_name_no_email_uses_hadi_voice_and_profile_channel():
    d = outreach.build_draft(_ctx(
        contact_name="Brad Jayakody",
        contact_role="Engineering leader at Paymentology",
        contact_email=None,
        email_label="unverified",
        company="Paymentology",
    ))
    body = d["body"]
    assert body.startswith("Hey Brad,")
    assert "at Paymentology at Paymentology" not in body
    assert "Proof over claims" not in body
    assert "maps to work I already do" not in body
    assert "100+ AWS accounts" in body
    assert "Hope to talk to you :)" in body
    assert d["channel"] == "profile_lookup_required"
