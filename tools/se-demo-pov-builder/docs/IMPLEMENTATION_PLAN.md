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

## Phase 7 — Reuse public LogicMonitor tooling ✅

- Replaced the invented mock adapters with a read-only adapter for the public
  `logicmonitor-api-mcp` server (mock and live modes, protocol-faithful tests).
- POV readiness checks with attach-as-evidence (simulated flag preserved).
- Generated Logic.Monitor PowerShell setup scripts (dry run by default, pinned sources,
  never overwrite existing modules, no credentials).
- `knowledge/lm_ecosystem.yaml`: pinned public projects, POV toolkit, reference links.
- Versioned handoff export for downstream SE platforms (LMDA).
- Private repositories used as reference only.

## Next milestones (proposed, not started)

1. **Migrations**: Alembic, so upgrades keep existing local data.
2. **Exports**: DOCX/PDF for POV plans and success summaries.
3. **Validate against a sandbox portal**: run the MCP readiness checks and a generated
   setup script (dry run, then `-Apply`) against a sandbox with synthetic resources; add
   PSScriptAnalyzer and Pester to CI for generated scripts.
4. **LMDA import**: an importer on the LMDA side for `se-demo-pov-builder/handoff` v1
   (lives in LMDA's repository, not here).
5. **Second tool** (e.g. inventory exporter) that reuses the adapter contracts; at that
   point move `adapters/base.py` into `shared/python/`.
6. **Multi-user**: authentication, per-user ownership, audit log of state changes.
7. **Content packs**: load additional persona/scenario directories (team-specific) via
   `SEPB_EXTRA_CONTENT_DIRS`.
8. **Optional AI assists**: talking-point refinement and objection-handling drafts, always
   labelled and never auto-saved.
