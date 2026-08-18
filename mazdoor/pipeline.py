"""One-shot pipeline: collect -> curate -> research -> score -> resume ->
outreach -> persist (docs/OPERATIONS.md).

Explicitly NOT scheduled: run manually, exactly as many times as you want,
with `python -m mazdoor.cli collect` (no cron anywhere in this project).
"""

from datetime import date

from . import db, outreach, profile, resume
from .collect import curate
from .scoring import research_geo

OKHADI_PATH = "/home/motabilla/workspace/okHadi"


def capture_okhadi_sha():
    """Safely synchronize and return the canonical source commit."""
    return profile.sync_repository(OKHADI_PATH)


def run(db_path, artifacts_dir, sources, target=10, research_fn=None,
        okhadi_sha=None):
    """Run the full local pipeline once. Returns a state dict with counts and
    honest source errors."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    store = db.Store(db_path)
    try:
        source_errors = []
        collected = 0
        for source in sources:
            result = source.fetch()
            if not result["ok"]:
                source_errors.append(f"{result['source']}: {result['error']}")
                store.set_source_error(result["source"], result["error"])
                continue
            for job in result.get("jobs", []):
                store.upsert_job(job)
                collected += 1

        # record exact okHadi source SHA
        sha = okhadi_sha or capture_okhadi_sha()
        if sha:
            store.set_meta("okhadi_git_sha", sha)

        # curate from what was actually collected (never pads)
        all_jobs = store.get_jobs()
        curated = curate([j for j in all_jobs if not j.get("source_error")],
                         target=target)
        curated_ids = []
        for job in curated:
            job_id = store.upsert_job(job)  # ensure scored fields keyed by same id
            if sha:
                store.set_job_source_commit(job_id, sha)
            # re-fetch the row id for the curated job (score/geo stored below)
            row = store.get_job(job_id)
            store.update_curation(
                job_id=job_id, role_family=job["role_family"],
                geo_tag=job["geo_tag"], geo_confidence=job["geo_confidence"],
                geo_notes=job["geo_notes"], score=job["score"],
                score_breakdown=job.get("score_breakdown"),
                rationale=job.get("rationale"),
            )
            curated_ids.append(job_id)

        # research + geo + resume + outreach per curated job
        research_ok = 0
        resumes = 0
        drafts = 0
        for job_id in curated_ids:
            job = store.get_job(job_id)
            research = {}
            if research_fn:
                research = research_fn(job) or {}
            if research:
                store.upsert_company_research(
                    job_id=job_id,
                    company_summary=research.get("company_summary"),
                    evidence_urls=research.get("evidence_urls"),
                    evidence_notes=research.get("evidence_notes"),
                    funding=research.get("funding"),
                    headcount=research.get("headcount"),
                    remote_policy=research.get("remote_policy"),
                )
                for c in research.get("contacts", [])[:3]:
                    store.upsert_contact(
                        job_id=job_id, name=c.get("name"), role=c.get("role"),
                        source=c.get("source"), email=c.get("email"),
                        email_label=c.get("email_label"),
                        email_confidence=c.get("email_confidence"),
                        evidence_url=c.get("evidence_url"), note=c.get("note"),
                        confidence_label=c.get("confidence_label"),
                        hiring_influence=c.get("hiring_influence"),
                        role_is_current=1 if c.get("role_is_current") else 0,
                    )
                research_ok += 1
            n_res, n_drafts = _process_job(store, job_id, artifacts_dir)
            resumes += n_res
            drafts += n_drafts

        return {
            "jobs_collected": collected,
            "jobs_curated": len(curated_ids),
            "jobs_researched": research_ok,
            "resumes_generated": resumes,
            "drafts_generated": drafts,
            "source_errors": source_errors,
            "okhadi_sha": sha,
            "run_date": date.today().isoformat(),
        }
    finally:
        store.close()


def finalize(store, artifacts_dir=None, okhadi_sha=None):
    """Regenerate geo, resumes, tailoring plans, and drafts for already-curated
    jobs (e.g. after manual research ingestion). Returns counts."""
    resumes = drafts = 0
    if okhadi_sha:
        store.set_meta("okhadi_git_sha", okhadi_sha)
    for job in store.get_jobs(order_by="score", desc=True):
        if job.get("score") is None or job.get("source_error"):
            continue
        if okhadi_sha:
            store.set_job_source_commit(job["id"], okhadi_sha)
        n_res, n_drafts = _process_job(store, job["id"], artifacts_dir)
        resumes += n_res
        drafts += n_drafts
    return {"resumes_generated": resumes, "drafts_generated": drafts}


def _process_job(store, job_id, artifacts_dir=None):
    """Geo (with evidence), resume PDF + tailoring plan, outreach drafts."""
    job = store.get_job(job_id)

    # geo with independent evidence
    research_row = store.get_company_research(job_id)
    geo_notes = []
    if research_row and research_row.get("evidence_notes"):
        geo_notes = [{"url": None, "note": research_row["evidence_notes"]}]
    geo = research_geo(job, company_notes=geo_notes)
    cites = "; ".join(
        c if isinstance(c, str) else c.get("note", str(c))
        for c in geo["citations"][:3]
    )
    store.update_curation(
        job_id=job_id, role_family=job["role_family"],
        geo_tag=geo["tag"], geo_confidence=geo["confidence"],
        geo_notes=f"{job.get('geo_notes') or ''} | research: {cites}",
        score=job["score"], score_breakdown=None, rationale=job["rationale"],
    )

    resumes = 0
    drafts = 0
    if artifacts_dir is not None:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        family = job["role_family"]
        pdf_path = resume.default_filename(
            family, job["company"], artifacts_dir, title=job["title"],
        )
        resume.generate(pdf_path, family=family, job=job)
        plan = resume.build_plan(family=family, job=job)
        store.set_tailoring_plan(job_id, plan)
        resumes = 1

        # outreach drafts: only for real contacts (never invented)
        contacts = store.get_contacts(job_id)
        draft_path = None
        for c in contacts:
            draft = outreach.build_draft({
                "job_title": job["title"], "company": job["company"],
                "company_hook": _hook_from_research(job, research_row),
                "role_family": family,
                "evidence": None,
                "contact_name": c.get("name"), "contact_role": c.get("role"),
                "contact_email": c.get("email"),
                "email_label": c.get("email_label"),
                "contact_profile": c.get("linkedin_url") or c.get("evidence_url"),
            })
            store.upsert_outreach(job_id=job_id, contact_id=c["id"],
                                  subject=draft["subject"], body=draft["body"])
            safe = "".join(ch for ch in job["company"] if ch.isalnum() or ch in " -_") \
                .strip().replace(" ", "_")
            draft_path = artifacts_dir / f"outreach_{job_id}_{safe}.md"
            _write_draft_file(draft_path, c, draft)
            drafts += 1

        store.update_application(
            job_id=job_id, status="prepared",
            resume_path=str(pdf_path),
            outreach_path=str(draft_path) if draft_path else None,
        )
    return resumes, drafts


def _hook_from_research(job, research_row):
    """Build a specific, truthful hook from research evidence. Returns None if
    nothing specific is available (builder falls back to job-specific line)."""
    if not research_row:
        return None
    summary = research_row.get("company_summary") or ""
    notes = research_row.get("evidence_notes") or ""
    researched_hook = notes.splitlines()[0].strip() if notes else ""
    if len(researched_hook) > 40:
        return researched_hook
    if len(summary) > 40:
        return f"I found the {job.get('title')} role while looking into what {job.get('company')} ships: {summary[:220]}"
    return None


def _write_draft_file(path, contact, draft):
    header = (
        f"# Outreach draft for job contact\n\n"
        f"Recipient: {contact.get('name') or 'unknown'} ({contact.get('role') or 'unknown'})\n"
        f"Email: {contact.get('email') or 'none found'}\n"
        f"Email label: {contact.get('email_label') or 'unlabelled'} "
        f"(confidence {contact.get('email_confidence')})\n"
        f"Channel: {draft.get('channel', 'profile_lookup_required')}\n"
        f"Source: {contact.get('evidence_url') or contact.get('source') or 'unknown'}\n\n"
        f"---\n\n"
    )
    body = f"Subject: {draft['subject']}\n\n{draft['body']}\n"
    lint = outreach.lint_draft(draft)
    footer = "\n\n---\nVoice lint: " + ("clean" if not lint else "; ".join(lint))
    path.write_text(header + body + footer)
    return path
