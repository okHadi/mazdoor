"""Canonical candidate profile.

Single source of truth for Mazdoor. Every fact here traces to
/home/motabilla/workspace/okHadi/site/content/jobs/*/index.md and CV/ENG.md
(see docs/SOURCE_SYNC.md). Metrics use the exact canonical wording:

  - Parhlai: 8,281 registered users, 5,276 MAU, ~1M PKR funding,
    PKR 500,079 combined consumer and B2B BOOKED revenue (never ARR),
    4.57M Google Search impressions + 162,233 clicks in the last 90 days.
  - Syslify: 100+ AWS accounts, AWS Control Tower, Terraform, OpenShift.

Do not add, remove, or reword metrics here without updating the okHadi
canonical source first (per okHadi/AGENTS.md sync workflow).
"""

import subprocess
from pathlib import Path


class SourceSyncError(RuntimeError):
    """The canonical evidence repository cannot be synchronized safely."""


def sync_repository(path="/home/motabilla/workspace/okHadi"):
    """Fetch and fast-forward a clean canonical evidence repository.

    Never stashes, resets, discards, or overwrites local changes.
    """
    repo = Path(path)

    def run(*args):
        result = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True,
            text=True, timeout=120,
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise SourceSyncError(f"git {' '.join(args)} failed: {detail}")
        return result.stdout.strip()

    if run("status", "--porcelain"):
        raise SourceSyncError(f"canonical source worktree is dirty: {repo}")
    run("fetch", "--prune", "origin")
    run("pull", "--ff-only")
    return run("rev-parse", "HEAD")

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
NAME = "Hadi Khan"
EMAIL = "hello@mhadi.dev"
PHONE_MASKED = "+923****3633"  # must stay masked everywhere
LINKS = {
    "linkedin": "https://linkedin.com/in/okHadi",
    "github": "https://github.com/okHadi",
    "website": "https://mhadi.dev",
}

EDUCATION = [
    {
        "school": "National University of Sciences and Technology (NUST)",
        "degree": "Bachelor of Science in Computer Science",
        "location": "Islamabad, Pakistan",
        "dates": None,
    }
]

# ---------------------------------------------------------------------------
# Experience (canonical bullets, exact numbers)
# ---------------------------------------------------------------------------
EXPERIENCE = [
    {
        "company": "Syslify",
        "titles": [
            {
                "title": "Senior DevOps Engineer",
                "dates": "Jun 2026 - Present",
                "location": "UK, Remote",
                "bullets": [
                    "Built GitHub disaster recovery and AWS account backup workflows using AWS Control Tower Landing Zone",
                    "Enforced account-level tagging across 100+ AWS accounts through Terraform IaC",
                    "Led production Terraform module migrations and Red Hat OpenShift machine-pool upgrades",
                ],
            },
            {
                "title": "Junior DevOps Engineer",
                "dates": "2022 - 2025",
                "location": "UK, Remote",
                "bullets": [
                    "Migrated CodeCommit, CodePipeline, and manual infrastructure to GitHub and Terraform-based IaC, standardizing multi-cloud production environments across AWS, GCP, Cloudflare, and GitHub",
                    "Managed GitHub infrastructure with Terraform, including granular permissions and reproducible operations across environments",
                    "Designed GitHub Actions and GitLab CI pipelines with Docker layer caching and build optimizations",
                    "Provisioned self-hosted GitHub Actions runners on AWS Fargate, reducing CI costs by ~90%; automated database, WAF, and state-lock operations with GitHub Actions workflows",
                    "Implemented blue/green deployments on ECS Fargate with CloudFormation, CodePipeline, and CodeDeploy, including a rapid hotfix path",
                    "Configured GitHub Environments, OIDC temporary credentials, Microsoft Entra ID SSO, RBAC, and Firebase Authentication custom roles",
                    "Built Bash/Python monitoring, Slack/PagerDuty alerting, and Datadog observability across EC2 and ECS Fargate, improving issue detection and response times by 50%",
                    "Secured development endpoints with CloudFront Functions and AWS WAF; managed DNS and WAF configuration through Terraform",
                    "Built disaster recovery plans with multi-region RDS snapshot replication and Cognito user pool backups",
                    "Improved AWS Security Hub from ~60% to ~80% by remediating IAM, networking, and compute findings",
                    "Rightsized EC2 and non-production environments, reducing infrastructure costs by ~70% while maintaining performance",
                    "Managed and tuned OpenSearch clusters for production search workloads",
                ],
            },
            {
                "title": "Trainee DevOps Engineer",
                "dates": "2021 - 2022",
                "location": "UK, Remote",
                "bullets": [
                    "Developed and deployed Dockerized Flask and TypeScript/Express applications across AWS Lambda, ECS Fargate, and EC2, including MongoDB-backed backends for two e-commerce platforms",
                ],
            },
        ],
    },
    {
        "company": "Parhlai",
        "metrics": {
            "users": 8281,
            "mau": 5276,
            "funding_pkr": 1000000,  # ~1M PKR (approximate per canonical source)
            "booked_revenue_pkr": 500079,  # PKR 500,079 combined consumer and B2B booked revenue. NEVER call it ARR.
            "impressions": 4570000,  # 4.57M in the last 90 days
            "clicks": 162233,
            "quizzes": 15623,
            "mcqs_presented": 1827125,
            "mcq_bank": 127295,
        },
        "titles": [
            {
                "title": "Co-Founder & CTO",
                "dates": "Mar 2024 - Present",
                "location": "Islamabad / Remote",
                "bullets": [
                    "Grew Parhlai to 8,281 registered users and 5,276 MAU while leading a lean team of 4 engineers",
                    "Secured ~1M PKR in funding and generated PKR 500,079 in combined consumer and B2B booked revenue",
                    "Owned product strategy, roadmap execution, and an AI-first engineering culture; used PostHog to guide prioritization and retention work",
                    "Drove all-organic acquisition through SEO, Reddit, and referrals, reaching 4.57M Google Search impressions and 162,233 clicks in the last 90 days",
                    "Ranked key features #1 in search within 2 weeks using Ahrefs and SEO optimization",
                    "Supported 15,623 quizzes, 1,827,125 MCQs presented, and a 127,295-question MCQ bank",
                    "Architected a multi-cloud serverless backend across AWS and Cloudflare with Terraform, keeping infrastructure cost near 1% of total spend",
                    "Built asynchronous, event-driven ML pipelines for MCQ generation and content moderation",
                    "Built the MCQ generation pipeline with OCR, YOLOv12, Pinecone embeddings, Groq/Gemini generation, and multi-agent validation",
                ],
            }
        ],
    },
    {
        "company": "Imagine.art / Vyro.ai",
        "titles": [
            {
                "title": "Product Manager (AI First)",
                "dates": "Dec 2025 - Jun 2026",
                "location": "Islamabad, PK",
                "bullets": [
                    "Led OmniAgent end-to-end as the new AI core of ChatlyAI, scaling from 0 to 5,000 DAUs and 15,000+ organic generations from architecture through growth",
                    "Contributed production PRs alongside the engineering team while translating product requirements into shipped AI features",
                    "Independently built and launched Chatly's AI Chrome extension in 2 weeks using Claude, acquiring 2,000+ organic users with zero paid acquisition",
                    "Owned AI Slides from research and proof of concept through pipeline architecture and launch, reaching 10,000+ users within 1 month",
                    "Contributed to scaling the broader product from 200K to 1.2M+ MAUs (6x) and 10M+ sign-ups through feature prioritization, growth experiments, and cross-functional execution",
                    "Supported revenue growth into the $6.5M range through pricing experiments, funnel optimization, and Stripe billing improvements",
                    "Helped scale the product organization from 5 to 35+ members while leading a cross-functional team of 10 engineers",
                    "Improved AI image-generation quality ratings by 50% through structured prompt engineering, model parameter tuning, and iterative testing",
                    "Automated vendor invoicing, template updates, and review tracking with serverless functions, reducing hours-long workflows to minutes",
                ],
            }
        ],
    },
    {
        "company": "Vfairs",
        "titles": [
            {
                "title": "Associate Software Engineer",
                "dates": "Nov 2023 - Sept 2024",
                "location": "Lahore, Remote (Part-time)",
                "bullets": [
                    "Developed and improved 40+ job scrapers using Selenium and Scrapy, increasing data fetched by 50%",
                    "Configured and developed load tests for multiple applications using Artillery.io, K6, and Flood, simulating up to 10,000 users",
                    "Designed and provisioned ephemeral QA environments on AWS ECS, triggered by pull requests, to support parallel testing across a team of 50+ developers",
                ],
            }
        ],
    },
]

# ---------------------------------------------------------------------------
# Skills (searchable names, ATS-friendly)
# ---------------------------------------------------------------------------
SKILLS = {
    "languages": ["Python", "TypeScript", "JavaScript", "Bash", "SQL"],
    "infra": [
        "AWS", "Terraform", "Kubernetes", "OpenShift", "Docker", "GitHub Actions",
        "GitLab CI", "Cloudflare", "GCP", "Control Tower", "ECS Fargate", "Lambda",
        "EC2", "RDS", "CloudFormation", "OpenSearch", "Datadog", "Ansible", "WAF",
        "CI/CD", "OIDC", "SSO", "RBAC", "Microsoft Entra ID",
    ],
    "backend": [
        "FastAPI", "Flask", "ExpressJS", "Node.js", "MongoDB", "PostgreSQL",
        "REST APIs", "Serverless", "Event-driven architecture",
    ],
    "ai_ml": [
        "Claude Code", "Codex", "AI agents", "LLM APIs", "RAG", "Pinecone",
        "OCR", "YOLOv12", "Groq", "Gemini", "PostHog", "Prompt engineering",
    ],
    "product": [
        "Product strategy", "Roadmap", "AI-first product management", "Sprint planning",
        "Stakeholder management", "A/B testing", "Growth experiments", "SEO",
        "Stripe billing", "Funnel optimization", "Cross-functional leadership",
    ],
    "qa_perf": ["Selenium", "Scrapy", "K6", "Artillery", "Load testing"],
}

# ---------------------------------------------------------------------------
# Projects (real okHadi projects)
# ---------------------------------------------------------------------------
PROJECTS = [
    {
        "name": "QALMS",
        "description": "Core scraper for individual NUST entry-test data; powers question pipelines at scale",
        "link": "https://github.com/okHadi/QALMS",
    },
    {
        "name": "Dhoondlai",
        "description": "Scraper for PC parts pricing in the Pakistani market",
        "link": "https://github.com/okHadi/Dhoondlai",
    },
    {
        "name": "DockerServicesStatus",
        "description": "Simple Docker monitoring tool for multiple servers",
        "link": "https://github.com/okHadi/docker-services-status",
    },
    {
        "name": "Repak",
        "description": "Android app to track crime on a map",
        "link": "https://github.com/okHadi/Repak",
    },
]

# ---------------------------------------------------------------------------
# Role families (required behavior) and per-family resume weighting
# ---------------------------------------------------------------------------
ROLE_FAMILIES = {
    "devops_sre_platform": {
        "label": "DevOps / SRE / Platform / Cloud",
        "weight": 1.0,
        "keywords": [
            "devops", "platform", "terraform", "aws", "kubernetes", "k8s", "docker",
            "ci/cd", "github actions", "openshift", "linux", "sre", "reliability",
            "incident", "observability", "monitoring", "datadog", "cloud", "gcp",
            "cloudflare", "infrastructure", "control tower", "ecs", "fargate",
            "lambda", "jenkins", "gitlab ci", "ansible", "prometheus", "grafana",
            "on-call", "autoscaling", "argo",
        ],
        "summary": "DevOps / platform engineer with 4+ years across AWS (100+ accounts), Terraform, Kubernetes and OpenShift, with a startup CTO track record running multi-cloud serverless infra at near 1% cost.",
    },
    "backend_api": {
        "label": "Backend / API / Automation",
        "weight": 1.0,
        "keywords": [
            "python", "fastapi", "flask", "node", "typescript", "express", "rest",
            "api", "postgresql", "mongodb", "serverless", "lambda", "event-driven",
            "microservices", "automation", "scraping", "selenium", "scrapy", "sql",
            "webhooks", "integration", "databases", "queue", "kafka", "redis",
        ],
        "summary": "Backend engineer shipping production Python and TypeScript services, event-driven pipelines, and scraper automation at scale.",
    },
    "product_engineering": {
        "label": "Product Engineering",
        "weight": 0.9,
        "keywords": [
            "product engineer", "full stack", "fullstack", "feature development",
            "product development", "ship", "build", "customer", "user feedback",
            "metrics", "experimentation", "startup", "mvp", "prototype", "growth",
        ],
        "summary": "Product engineer with a CTO and AI-PM track record: shipped AI products from zero to 5,000 DAUs and scaled a platform from 200K to 1.2M+ MAUs.",
    },
    "ai_first_product": {
        "label": "AI-First Product Engineering",
        "weight": 1.0,
        "keywords": [
            "claude", "codex", "ai agent", "ai agents", "agentic", "llm", "gpt",
            "ai coding", "cursor", "copilot", "rag", "prompt engineering", "fine-tuning",
            "model", "ai-powered", "ai features", "ai product", "genai", "generative ai",
        ],
        "summary": "AI-first engineer who builds with Claude Code and Codex: shipped an AI extension in 2 weeks (2,000+ organic users) and an LLM pipeline with multi-agent validation.",
    },
    "technical_pm": {
        "label": "Technical PM / Product Owner / Sprint Lead",
        "weight": 0.9,
        "keywords": [
            "product manager", "product owner", "sprint", "scrum", "agile", "roadmap",
            "stakeholder", "prioritization", "backlog", "technical pm", "pm",
            "gtm", "launch", "requirements", "cross-functional", "jira", "analytics",
            "kpi", "user research",
        ],
        "summary": "Technical PM who has owned product and roadmap end-to-end while shipping production PRs: led a 10-engineer team, scaled a product org from 5 to 35+.",
    },
    "ai_training": {
        "label": "AI Training / Coding Evaluator Contracts",
        "weight": 0.8,
        "keywords": [
            "ai trainer", "data annotator", "evaluator", "code review", "feedback",
            "contract", "prompt", "benchmark", "red team", "model evaluation",
            "ground truth", "label", "coding assessment", "rater",
        ],
        "summary": "AI trainer and coding evaluator: production engineer experience across Python, TypeScript, and infra, with strong judgment on code quality and LLM output.",
    },
}

# Frontend-heavy signal words -> score penalty (never hard exclusion)
FRONTEND_PENALTY_WORDS = [
    "react", "frontend", "front-end", "ui engineer", "css", "tailwind", "figma",
    "webflow", "wordpress", "html", "design system", "landing pages", "vite",
    "next.js frontend", "front end", "ux", "design engineer",
]

# Seniority preference: mid preferred, junior/senior accepted
SENIORITY_KEYWORDS = {
    "junior": ["junior", "associate", "entry-level", "entry level", "trainee"],
    "mid": ["mid", "intermediate", "2+ years", "3+ years", "4+ years", "5+ years"],
    "senior": ["senior", "staff", "lead", "principal", "sr."],
}

# ---------------------------------------------------------------------------
# Geo eligibility classes
# ---------------------------------------------------------------------------
GEO_TAGS = {
    "confirmed_eligible": "Company hires remote from Pakistan/APAC with evidence",
    "strong_signal": "Strong positive signal, not yet a written policy",
    "possible_exception": "Maybe eligible via exception or timezone overlap",
    "restricted": "Explicitly limited to other regions or sponsorship required",
    "unknown": "No public evidence found",
}

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load():
    """Return the canonical profile dict used by scoring, resume, outreach."""
    text_parts = []
    for exp in EXPERIENCE:
        for t in exp["titles"]:
            text_parts.append(f"{t['title']} at {exp['company']}")
            text_parts.extend(t["bullets"])
    return {
        "name": NAME,
        "email": EMAIL,
        "phone_masked": PHONE_MASKED,
        "links": LINKS,
        "education": EDUCATION,
        "experience": EXPERIENCE,
        "skills": SKILLS,
        "projects": PROJECTS,
        "role_families": ROLE_FAMILIES,
        "frontend_penalty_words": FRONTEND_PENALTY_WORDS,
        "seniority_keywords": SENIORITY_KEYWORDS,
        "geo_tags": GEO_TAGS,
        "experience_evidence_text": "\n".join(text_parts),
        # Parhlai verified metrics, exact canonical wording
        "parhlai_metrics": {
            "users": 8281,
            "mau": 5276,
            "funding_pkr": 1000000,  # ~1M PKR (approximate per canonical source)
            "booked_revenue_pkr": 500079,  # PKR 500,079 combined consumer and B2B booked revenue. NEVER call it ARR.
            "impressions": 4570000,  # 4.57M in the last 90 days
            "clicks": 162233,
            "quizzes": 15623,
            "mcqs_presented": 1827125,
            "mcq_bank": 127295,
        },
    }
