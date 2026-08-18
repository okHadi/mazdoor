"""SQLite storage for Mazdoor (WAL mode, foreign keys enforced)."""

import json
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    external_url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT NOT NULL DEFAULT '',
    description_url TEXT,
    posted_at TEXT,
    salary TEXT,
    raw_json TEXT,
    collected_at TEXT NOT NULL,
    source_error TEXT,
    role_family TEXT,
    geo_tag TEXT,
    geo_confidence REAL,
    geo_notes TEXT,
    score REAL,
    score_breakdown TEXT,
    rationale TEXT,
    tailoring_plan TEXT,
    source_commit TEXT,
    UNIQUE(source, source_id)
);

CREATE TABLE IF NOT EXISTS company_research (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    company_summary TEXT,
    evidence_urls TEXT,
    evidence_notes TEXT,
    funding TEXT,
    headcount TEXT,
    remote_policy TEXT,
    researched_at TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT,
    role TEXT,
    source TEXT,
    email TEXT,
    email_label TEXT,
    email_confidence REAL,
    evidence_url TEXT,
    note TEXT,
    confidence_label TEXT,
    hiring_influence TEXT,
    role_is_current INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS applications (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'not_applied',
    applied_at TEXT,
    resume_path TEXT,
    outreach_path TEXT,
    notes TEXT,
    outcome TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS outreach_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    subject TEXT,
    body TEXT,
    created_at TEXT,
    UNIQUE(job_id, contact_id)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);
"""

STATUSES = (
    "not_applied", "prepared", "applied", "replied", "interview",
    "offer", "rejected", "ghosted", "withdrawn",
)


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.path = str(path)
        self._lock = threading.RLock()
        # check_same_thread=False: the dashboard serves requests from a worker
        # thread while the CLI writes from the main thread. sqlite3 serializes
        # statement execution internally; the RLock guards multi-statement ops.
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        columns = {
            row[1] for row in self.conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "source_commit" not in columns:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN source_commit TEXT")
        self.conn.commit()

    def close(self):
        with self._lock:
            self.conn.close()

    # -- introspection ------------------------------------------------------
    def journal_mode(self):
        with self._lock:
            return self.conn.execute("PRAGMA journal_mode").fetchone()[0]

    # -- meta ---------------------------------------------------------------
    def set_meta(self, key, value):
        with self._lock:
            self.conn.execute(
                "INSERT INTO meta (key, value, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (key, value, utcnow()),
            )
            self.conn.commit()

    def get_meta(self, key):
        with self._lock:
            row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None

    def set_job_source_commit(self, job_id, source_commit):
        with self._lock:
            self.conn.execute(
                "UPDATE jobs SET source_commit=? WHERE id=?",
                (source_commit, job_id),
            )
            self.conn.commit()

    # -- jobs ----------------------------------------------------------------
    def upsert_job(self, job):
        now = utcnow()
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO jobs (
                    source, source_id, external_url, title, company, location,
                    description, description_url, posted_at, salary, raw_json,
                    collected_at, source_error
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    external_url=excluded.external_url,
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    description=excluded.description,
                    description_url=excluded.description_url,
                    posted_at=excluded.posted_at,
                    salary=excluded.salary,
                    raw_json=excluded.raw_json,
                    source_error=excluded.source_error
                """,
                (
                    job["source"], job["source_id"], job["external_url"],
                    job["title"], job["company"], job.get("location"),
                    job.get("description") or "", job.get("description_url"),
                    job.get("posted_at"), job.get("salary"), job.get("raw_json"),
                    now, job.get("source_error"),
                ),
            )
            row = self.conn.execute(
                "SELECT id FROM jobs WHERE source=? AND source_id=?",
                (job["source"], job["source_id"]),
            ).fetchone()
            self.conn.commit()
        return row["id"]

    def update_curation(self, job_id, role_family, geo_tag, geo_confidence,
                        geo_notes, score, score_breakdown, rationale=None):
        with self._lock:
            self.conn.execute(
                """
                UPDATE jobs SET role_family=?, geo_tag=?, geo_confidence=?,
                    geo_notes=?, score=?, score_breakdown=?, rationale=?
                WHERE id=?
                """,
                (role_family, geo_tag, geo_confidence, geo_notes, score,
                 json.dumps(score_breakdown) if score_breakdown else None,
                 rationale, job_id),
            )
            self.conn.commit()

    def set_tailoring_plan(self, job_id, plan):
        """Persist the per-job tailoring plan (summary, JD keyword match,
        bullet selection) as JSON on the job row."""
        with self._lock:
            self.conn.execute(
                "UPDATE jobs SET tailoring_plan=? WHERE id=?",
                (json.dumps(plan, default=str), job_id),
            )
            self.conn.commit()

    def get_job(self, job_id):
        with self._lock:
            row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    def get_jobs(self, role_family=None, geo_tag=None, order_by="id", desc=False):
        sql = "SELECT * FROM jobs"
        clauses, params = [], []
        if role_family:
            clauses.append("role_family=?")
            params.append(role_family)
        if geo_tag:
            clauses.append("geo_tag=?")
            params.append(geo_tag)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        order_col = order_by if order_by in ("id", "score", "posted_at", "company") else "id"
        sql += f" ORDER BY {order_col} " + ("DESC" if desc else "ASC")
        with self._lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def set_source_error(self, source, message):
        """Record a source-level failure without fabricating any jobs."""
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO jobs (source, source_id, external_url, title, company,
                    description, collected_at, source_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, source_id) DO UPDATE SET
                    source_error=excluded.source_error
                """,
                (source, f"__error__", f"https://error.local/{source}", "(source error)",
                 "(source error)", "", utcnow(), message),
            )
            self.conn.commit()

    def get_source_errors(self):
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM jobs WHERE source_error IS NOT NULL"
            ).fetchall()
        return [dict(r) for r in rows]

    # -- company research ------------------------------------------------------
    def upsert_company_research(self, job_id, company_summary, evidence_urls,
                                evidence_notes, funding, headcount, remote_policy):
        if isinstance(evidence_urls, (list, tuple)):
            evidence_urls = json.dumps(list(evidence_urls))
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO company_research (
                    job_id, company_summary, evidence_urls, evidence_notes,
                    funding, headcount, remote_policy, researched_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                    company_summary=excluded.company_summary,
                    evidence_urls=excluded.evidence_urls,
                    evidence_notes=excluded.evidence_notes,
                    funding=excluded.funding,
                    headcount=excluded.headcount,
                    remote_policy=excluded.remote_policy,
                    researched_at=excluded.researched_at
                """,
                (job_id, company_summary, evidence_urls, evidence_notes,
                 funding, headcount, remote_policy, utcnow()),
            )
            self.conn.commit()

    def get_company_research(self, job_id):
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM company_research WHERE job_id=?", (job_id,)
            ).fetchone()
            return dict(row) if row else None

    # -- contacts ---------------------------------------------------------------
    def upsert_contact(self, job_id, name, role, source, email, email_label,
                       email_confidence, evidence_url, note,
                       confidence_label=None, hiring_influence=None,
                       role_is_current=0):
        with self._lock:
            existing = self.conn.execute(
                """
                SELECT id FROM contacts
                WHERE job_id=? AND COALESCE(name, '')=?
                  AND COALESCE(email, '')=? AND COALESCE(evidence_url, '')=?
                """,
                (job_id, name or "", email or "", evidence_url or ""),
            ).fetchone()
            values = (
                name, role, source, email, email_label, email_confidence,
                evidence_url, note,
                confidence_label or _label_from_confidence(email_confidence),
                hiring_influence, role_is_current,
            )
            if existing:
                self.conn.execute(
                    """
                    UPDATE contacts SET name=?, role=?, source=?, email=?,
                        email_label=?, email_confidence=?, evidence_url=?, note=?,
                        confidence_label=?, hiring_influence=?, role_is_current=?
                    WHERE id=?
                    """,
                    (*values, existing["id"]),
                )
                contact_id = existing["id"]
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO contacts (
                        job_id, name, role, source, email, email_label,
                        email_confidence, evidence_url, note,
                        confidence_label, hiring_influence, role_is_current
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (job_id, *values),
                )
                contact_id = cur.lastrowid
            self.conn.commit()
        return contact_id

    def get_contacts(self, job_id):
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM contacts WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -- applications ---------------------------------------------------------
    def update_application(self, job_id, status, applied_at=None, resume_path=None,
                           outreach_path=None, notes=None, outcome=None):
        """Update status; NULL fields preserve previously stored values."""
        assert status in STATUSES, f"invalid status: {status}"
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO applications (
                    job_id, status, applied_at, resume_path, outreach_path,
                    notes, outcome, updated_at
                ) VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status,
                    applied_at=COALESCE(excluded.applied_at, applications.applied_at),
                    resume_path=COALESCE(excluded.resume_path, applications.resume_path),
                    outreach_path=COALESCE(excluded.outreach_path, applications.outreach_path),
                    notes=COALESCE(excluded.notes, applications.notes),
                    outcome=COALESCE(excluded.outcome, applications.outcome),
                    updated_at=excluded.updated_at
                """,
                (job_id, status, applied_at, resume_path, outreach_path,
                 notes, outcome, utcnow()),
            )
            self.conn.commit()

    def get_application(self, job_id):
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM applications WHERE job_id=?", (job_id,)
            ).fetchone()
            return dict(row) if row else None

    # -- outreach drafts --------------------------------------------------------
    def upsert_outreach(self, job_id, contact_id, subject, body):
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO outreach_drafts (job_id, contact_id, subject, body, created_at)
                VALUES (?,?,?,?,?)
                ON CONFLICT(job_id, contact_id) DO UPDATE SET
                    subject=excluded.subject, body=excluded.body,
                    created_at=excluded.created_at
                """,
                (job_id, contact_id, subject, body, utcnow()),
            )
            self.conn.commit()

    def get_outreach(self, job_id):
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM outreach_drafts WHERE job_id=? ORDER BY id", (job_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -- combined view ----------------------------------------------------------
    def job_with_details(self, job_id):
        job = self.get_job(job_id)
        if not job:
            return None
        job["research"] = self.get_company_research(job_id)
        job["contacts"] = self.get_contacts(job_id)
        job["application"] = self.get_application(job_id)
        job["outreach"] = self.get_outreach(job_id)
        return job

    def jobs_with_details(self, **filters):
        jobs = self.get_jobs(**filters)
        return [self.job_with_details(j["id"]) for j in jobs]


def _label_from_confidence(conf):
    if conf is None:
        return "low"
    if conf >= 0.9:
        return "high"
    if conf >= 0.5:
        return "medium"
    return "low"
