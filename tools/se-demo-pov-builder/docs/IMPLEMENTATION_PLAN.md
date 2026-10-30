# SE Demo & POV Builder — Implementation Plan

Strategy: build one complete vertical slice of the journey first
(Create Deal → Stakeholders → Discovery → Success Criteria → Demo Plan → POV Plan →
Next Actions), then widen.

## Phase 0 — Foundations ✅

- Repository standards, root docs, CI workflow, `.gitignore`, license recommendation.
- Tool skeleton: backend package, frontend app, content directories, Makefile, Docker.

## Phase 1 — Content model ✅

- Pydantic models for personas, capabilities, discovery questions, demo scenarios,
  workflows and POV template.
- Loader that validates cross-references (persona ids, capability ids, task dependencies,
  dependency cycles) and reports every problem at once.
- `validate-content` CLI and tests.
- Initial content: 7 personas, capability catalogue (all `verified: false`), discovery
  question library with context tags and qualification checklist, demo scenarios,
  7 workflows, POV milestone template.

## Phase 2 — Core data and API ✅

- SQLAlchemy models, SQLite, Pydantic schemas.
- CRUD for accounts, deals, stakeholders, discovery answers, requirements, success
  criteria, evidence, tasks.

## Phase 3 — Engines ✅

- Discovery coach: question selection, gap analysis, suggested next actions, capability
  matching.
- Workflow engine: instantiate runs, dependency/evidence/blocker rules, stage progress.
- Demo builder: scenario scoring, agenda, talking points, prerequisites, assumptions,
  missing evidence; versioned plans; Markdown export.
- POV builder: plan creation, milestone tasks, draft criteria, checklist, evidence rules,
  Markdown export.

## Phase 4 — Integrations framework ✅ (mock only)

- Adapter contracts with read-only vs state-changing actions and `Authorization`.
- Mock adapters with JSON fixtures for REST API, PowerShell, LogicModule utilities, MCP.
- Optional LLM provider abstraction (none / Ollama / OpenAI-compatible), off by default.

## Phase 5 — Deal Workspace UI ✅

- Deals list, create account + deal, load sample engagement.
- Deal workspace tabs: Overview, Stakeholders, Discovery, Requirements, Demo Plan, POV,
  Workflows, Next Actions.
- Library (personas, capabilities, scenarios, workflows) and Integrations pages.

## Phase 6 — Quality ✅

- Backend unit tests per engine and an end-to-end API test of the full journey.
- Frontend component tests with mocked API.
- CI: ruff, pytest, tsc, vitest, vite build.

## Next milestones (proposed, not started)

1. **Migrations**: Alembic, so upgrades keep existing local data.
2. **Exports**: DOCX/PDF for POV plans and success summaries.
3. **Read-only REST adapter (live)**: implement 2–3 read operations after verifying
   endpoints, authentication and rate limits against official documentation; keep mock as
   default; record fixtures from a sandbox with synthetic data only.
4. **Second tool** (e.g. inventory exporter) that reuses the adapter contracts; at that
   point move `adapters/base.py` into `shared/python/`.
5. **Multi-user**: authentication, per-user ownership, audit log of state changes.
6. **Content packs**: load additional persona/scenario directories (team-specific) via
   `SEPB_EXTRA_CONTENT_DIRS`.
7. **Optional AI assists**: talking-point refinement and objection-handling drafts, always
   labelled and never auto-saved.
