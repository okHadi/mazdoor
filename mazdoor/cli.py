"""Mazdoor CLI: manual, one-shot commands only. No scheduling code exists here.

Commands:
  collect   one-shot job collection + curation + research + resumes + drafts
  serve     local dashboard (tracking/copy only; nothing is sent)
  verify    checks on PDFs/drafts/DB (run after collect)
  export    dump curated jobs to data/jobs.json (deliverable shape)
"""

import argparse
import json
import re
import sys
from pathlib import Path

from . import profile

from . import __version__
from .collect import Collector
from .db import Store
from .research import ResearchEngine, ingest_research


def _paths(args):
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    artifacts = Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    return db_path, artifacts


def cmd_collect(args):
    """One-shot: fetch public keyless sources, curate, research, generate."""
    db_path, artifacts = _paths(args)
    collector = Collector(timeout=args.timeout)

    sources = []
    if args.sources == "all" or "remotive" in args.sources:
        sources.append(_SourceWrapper("remotive", collector))
    if args.sources == "all" or "greenhouse" in args.sources:
        sources.append(_SourceWrapper("greenhouse", collector))
    if args.sources == "all" or "lever" in args.sources:
        sources.append(_SourceWrapper("lever", collector))
    if args.sources == "all" or "ashby" in args.sources:
        sources.append(_SourceWrapper("ashby", collector))

    from . import pipeline
    research = ResearchEngine(timeout=args.timeout)

    def research_fn(job):
        r = research.research_company(job)
        contacts = research.find_contacts(job, max_contacts=3)
        r["contacts"] = contacts
        return r

    state = pipeline.run(
        db_path=db_path, artifacts_dir=artifacts, sources=sources,
        target=args.target, research_fn=research_fn,
    )
    print(json.dumps(state, indent=2))
    print(f"DB: {db_path}  artifacts: {artifacts}")
    if state["source_errors"]:
        print("Source errors recorded (honest, not fabricated):")
        for e in state["source_errors"]:
            print(f"  - {e}")
    return 0


class _SourceWrapper:
    def __init__(self, name, collector):
        self.name = name
        self.collector = collector

    def fetch(self):
        return self.collector.fetch_source(self.name)


def cmd_serve(args):
    from . import dashboard
    db_path, artifacts = _paths(args)
    store = Store(db_path)
    handle = dashboard.make_server(store, host=args.host, port=args.port,
                                   artifacts_dir=artifacts)
    print(f"Mazdoor dashboard: http://{args.host}:{handle.port}")
    print("Local tracking only. Nothing is sent, applied, or scheduled.")
    try:
        handle.join()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        handle.stop()
        store.close()
    return 0


def cmd_verify(args):
    """Verify generated artifacts against hard rules (docs/OPERATIONS.md)."""
    from pypdf import PdfReader  # dev dependency, verified in docs

    db_path, artifacts = _paths(args)
    store = Store(db_path)
    issues = []
    pdfs = sorted(artifacts.glob("*.pdf"))
    for pdf in pdfs:
        try:
            reader = PdfReader(str(pdf))
            text = "\n".join(pg.extract_text() or "" for pg in reader.pages)
            if len(reader.pages) != 1:
                issues.append(f"{pdf.name}: {len(reader.pages)} pages (must be 1)")
            if "—" in text or "–" in text:
                issues.append(f"{pdf.name}: em/en dash present")
            if re.search(r"\+92\s?\d{3}", text):
                issues.append(f"{pdf.name}: unmasked phone")
            if re.search(r"\barr\b", text, re.I):
                issues.append(f"{pdf.name}: ARR token")
            if "booked revenue" not in text.lower():
                issues.append(f"{pdf.name}: missing booked-revenue phrasing")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"{pdf.name}: unreadable ({exc})")

    # draft voice lint
    drafts = sorted(artifacts.glob("outreach_*.md"))
    from . import outreach
    for d in drafts:
        content = d.read_text()
        draft = {"subject": "", "body": content, "words": len(content.split())}
        for issue in outreach.lint_draft(draft):
            issues.append(f"{d.name}: {issue}")

    jobs = store.get_jobs()
    curated_count = len([j for j in jobs if j["score"] is not None])
    if curated_count != args.expect:
        issues.append(f"expected {args.expect} curated jobs, found {curated_count}")
    if len(pdfs) != args.expect:
        issues.append(f"expected {args.expect} PDFs, found {len(pdfs)}")

    if not issues and args.render:
        from . import verify as v
        rendered, failed = v.verify_renders(artifacts, out_dir=args.render)
        if failed:
            issues.append(f"PNG render failed: {failed}")
        print(f"rendered {len(rendered)} PDFs to {args.render} for visual inspection")

    if issues:
        print("VERIFY FAILED:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print(f"VERIFY OK: {len(pdfs)} PDFs, {len(drafts)} drafts, "
          f"{len([j for j in jobs if j['score'] is not None])} curated jobs")
    return 0


def cmd_export(args):
    db_path, artifacts = _paths(args)
    store = Store(db_path)
    out = {"run": "mazdoor first batch", "jobs": store.jobs_with_details()}
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, default=str))
    print(f"exported {len(out['jobs'])} jobs -> {target}")
    return 0


def cmd_candidates(args):
    """Load parent-verified candidate jobs from a JSON file, curate them."""
    db_path, artifacts = _paths(args)
    payload = json.loads(Path(args.file).read_text())
    jobs = payload if isinstance(payload, list) else payload.get("jobs", [])
    store = Store(db_path)
    try:
        from . import pipeline
        from .collect import curate
        sha = profile.sync_repository()
        store.set_meta("okhadi_git_sha", sha)
        for j in jobs:
            store.upsert_job(j)
        raw = store.get_jobs()
        raw = [j for j in raw if j["source"] == "verified"]
        curated = curate(raw, target=len(raw))
        for j in curated:
            jid = store.upsert_job(j)
            store.set_job_source_commit(jid, sha)
            store.update_curation(
                job_id=jid, role_family=j["role_family"], geo_tag=j["geo_tag"],
                geo_confidence=j["geo_confidence"], geo_notes=j["geo_notes"],
                score=j["score"], score_breakdown=None, rationale=j["rationale"],
            )
        print(f"loaded {len(jobs)} verified candidates; curated {len(curated)}")
    finally:
        store.close()
    return 0


def cmd_research(args):
    """Ingest a manual research JSON file (company/geo/contacts) for curated jobs."""
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    records = json.loads(Path(args.file).read_text())
    store = Store(db_path)
    try:
        applied = ingest_research(store, records, geo=True, gen_drafts=False)
        print(f"applied research to {applied} jobs")
    finally:
        store.close()
    return 0


def cmd_finalize(args):
    """Regenerate geo + resumes + drafts for curated jobs (after research)."""
    db_path, artifacts = _paths(args)
    store = Store(db_path)
    try:
        from . import pipeline
        sha = profile.sync_repository()
        state = pipeline.finalize(
            store, artifacts_dir=artifacts, okhadi_sha=sha,
        )
        print(json.dumps(state))
    finally:
        store.close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mazdoor", description=__doc__)
    parser.add_argument("--version", action="version", version=f"mazdoor {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_collect = sub.add_parser("collect", help="one-shot collection run (no scheduling)")
    p_collect.add_argument("--db", default="data/mazdoor.db")
    p_collect.add_argument("--artifacts", default="artifacts")
    p_collect.add_argument("--target", type=int, default=10,
                           help="curated job target for this batch")
    p_collect.add_argument("--sources", default="all",
                           help="comma list or 'all' (remotive,greenhouse,lever,ashby)")
    p_collect.add_argument("--timeout", type=int, default=25)
    p_collect.set_defaults(fn=cmd_collect)

    p_serve = sub.add_parser("serve", help="local dashboard (copy/track only)")
    p_serve.add_argument("--db", default="data/mazdoor.db")
    p_serve.add_argument("--artifacts", default="artifacts")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8787)
    p_serve.set_defaults(fn=cmd_serve)

    p_verify = sub.add_parser("verify", help="verify PDFs/drafts/DB against hard rules")
    p_verify.add_argument("--db", default="data/mazdoor.db")
    p_verify.add_argument("--artifacts", default="artifacts")
    p_verify.add_argument("--expect", type=int, default=10)
    p_verify.add_argument("--render", default="", nargs="?", const="artifacts/preview",
                          help="render PDFs to PNG for visual inspection (AGENTS.md)")
    p_verify.set_defaults(fn=cmd_verify)

    p_export = sub.add_parser("export", help="export curated jobs JSON")
    p_export.add_argument("--db", default="data/mazdoor.db")
    p_export.add_argument("--artifacts", default="artifacts")
    p_export.add_argument("--out", default="data/jobs.json")
    p_export.set_defaults(fn=cmd_export)

    p_cand = sub.add_parser("candidates", help="load verified candidate jobs JSON")
    p_cand.add_argument("--db", default="data/mazdoor.db")
    p_cand.add_argument("--artifacts", default="artifacts")
    p_cand.add_argument("--file", required=True, help="candidates JSON file")
    p_cand.set_defaults(fn=cmd_candidates)

    p_research = sub.add_parser("research", help="ingest manual research JSON")
    p_research.add_argument("--db", default="data/mazdoor.db")
    p_research.add_argument("--file", required=True, help="research JSON file")
    p_research.set_defaults(fn=cmd_research)

    p_finalize = sub.add_parser("finalize", help="regenerate geo/resumes/drafts")
    p_finalize.add_argument("--db", default="data/mazdoor.db")
    p_finalize.add_argument("--artifacts", default="artifacts")
    p_finalize.set_defaults(fn=cmd_finalize)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
