# SE Demo & POV Builder — Architecture

## Overview

```
┌──────────────────────────┐      /api (JSON)      ┌───────────────────────────────────┐
│ React + TypeScript (Vite)│ ───────────────────▶ │ FastAPI app (se_pov_builder)       │
│ Deal Workspace UI        │                       │                                   │
└──────────────────────────┘                       │  api/        HTTP routers          │
                                                   │  services/   deterministic engines │
                                                   │    discovery, demo_builder,        │
                                                   │    pov_builder, workflow_engine,   │
                                                   │    export                          │
                                                   │  knowledge.py  YAML content loader │
                                                   │  adapters/   integration contracts │
                                                   │              + mock implementations│
                                                   │  llm/        optional, off default │
                                                   │  models.py   SQLAlchemy ORM        │
                                                   └──────┬───────────────┬────────────┘
                                                          │               │
                                                  SQLite (data/)   YAML content (personas/,
                                                                   knowledge/, workflows/)
```

### Design principles

1. **Content is data, not code.** Personas, discovery questions, capability descriptions,
   demo scenarios, POV milestone templates and workflows are YAML files validated at
   start-up. Adding a persona or a workflow does not require code changes.
2. **Deterministic first.** Every step of the core journey works with rule-based logic.
   An optional LLM can draft text, and its output is always labelled as an AI draft.
3. **Honest outputs.** Generated plans list their assumptions and missing evidence.
   Simulated evidence is stored with `is_simulated = true`, is labelled everywhere, and
   cannot be used to mark a success criterion as met.
4. **No live integrations in the MVP.** Adapters implement documented contracts with
   mock responses. State-changing actions require an explicit `Authorization`.
5. **Local and single-user.** Binds to `127.0.0.1`. Optional bearer token
   (`SEPB_API_TOKEN`) for basic protection; not a substitute for real authentication.

## Directory layout

```
tools/se-demo-pov-builder/
├── backend/
│   ├── pyproject.toml
│   ├── se_pov_builder/
│   │   ├── app.py              create_app(): routers, CORS, auth, static UI
│   │   ├── config.py           Settings from SEPB_* environment variables
│   │   ├── db.py / models.py   SQLAlchemy engine + ORM
│   │   ├── schemas.py          Pydantic request/response models
│   │   ├── knowledge.py        Content models, loader, cross-reference validation
│   │   ├── services/           Discovery coach, demo builder, POV builder,
│   │   │                       workflow engine, markdown export
│   │   ├── adapters/           base.py contracts, MCP client, lm_mcp adapter
│   │   ├── llm/                Provider abstraction (none / Ollama / OpenAI-compatible)
│   │   ├── api/                FastAPI routers
│   │   ├── seed.py             Synthetic sample engagement
│   │   └── validate_content.py CLI: validate YAML content
│   └── tests/
├── frontend/                   Vite + React + TypeScript, vitest
├── personas/                   One YAML file per persona
├── knowledge/                  capabilities, discovery questions, demo scenarios, POV template,
│                               lm_ecosystem.yaml (public LM tooling, POV toolkit)
├── workflows/                  One YAML file per workflow
├── adapters/mock_responses/    MCP-format fixtures for mock mode
├── docs/                       This file, implementation plan, acceptance criteria
├── Dockerfile, docker-compose.yml, Makefile, .env.example
└── data/                       SQLite database (git-ignored)
```

## Data model

| Entity | Key fields | Notes |
|--------|------------|-------|
| `Account` | name, industry, employee_band, region, is_synthetic | Fictional customer organisation |
| `Deal` | account_id, name, stage, summary, business_drivers, technical_context[] | `technical_context` holds context tag ids (e.g. `network`, `cloud_aws`) that drive question selection |
| `Stakeholder` | deal_id, name, title, persona_id, influence, stance | `persona_id` references a persona YAML file |
| `DiscoveryAnswer` | deal_id, question_id, stakeholder_id, answer, evidence_source, confidence, evidence_quote | One answer per question per deal; `confidence` is `confirmed` or `assumed`; `evidence_quote` holds the accepted transcript quote |
| `DealQuestion` | deal_id, text, category, purpose, qualification_key | A question added to one deal; exposed as question id `custom-<id>` |
| `Requirement` | deal_id, title, category, priority, pain_point, source_question_id, capability_ids[] | `capability_ids` reference `knowledge/capabilities.yaml` |
| `DemoPlan` | deal_id, version, title, duration_minutes, content (JSON) | Snapshot of a generated plan, including the inputs it used |
| `PovPlan` | deal_id, title, objectives, start_date, end_date, status | Milestones are `Task` rows with `kind = milestone` |
| `SuccessCriterion` | deal_id, pov_plan_id, requirement_id, measurable_outcome, target, validation_method, owner, status | `met` requires at least one non-simulated evidence item |
| `Evidence` | criterion_id, description, reference, evidence_type, is_simulated, recorded_by | |
| `WorkflowRun` | deal_id, workflow_id, workflow_version | Instantiated from a workflow YAML file |
| `Task` | deal_id, kind (`next_action`/`workflow`/`milestone`), workflow_run_id, pov_plan_id, stage_id, owner, due_date, status, blocker, depends_on[], evidence_required, evidence_note | One table for workflow tasks, POV milestones and ad-hoc next actions, so dependency and status rules live in one place |

### Task rules (workflow engine)

- Status values: `todo`, `in_progress`, `blocked`, `done`, `cancelled`.
- `blocked` requires a `blocker` description.
- `done` is rejected while any dependency is not `done`/`cancelled`.
- `done` is rejected when `evidence_required` is true and `evidence_note` is empty.
- A stage is complete when all its tasks are `done` or `cancelled`. The current stage is
  the first incomplete stage. Workflow progress = completed tasks / total tasks.

## Engines

### Discovery coach (`services/discovery.py`)

- **Question selection**: a question is *suggested* when its `personas` include `all` or
  any persona assigned to a deal stakeholder, **and** its `contexts` include `any` or any
  of the deal's `technical_context` tags. Every bank question is returned with a
  `suggested` flag, so any deal can browse and answer all of them.
- **Custom questions** (`services/questions.py`): `question_index` merges the bank with the
  deal's `DealQuestion` rows; the API, gap analysis, handoff and AI prompts all use it.
- **Start here** (`next_questions`): up to five questions, in this order: one question per
  qualification checklist item nobody has answered (pain, impact, success criteria and
  decision process first), key questions for the deal, assumed answers to confirm, the
  deal's custom questions, other suggested questions. Bank questions outside the deal's
  personas fill in when few are suggested.
- **Transcript import** (`services/transcript.py`), stateless: the transcript is parsed
  (WebVTT, SRT, or "Speaker: text" lines with optional `[hh:mm:ss]`), consecutive cues
  from one speaker are joined, and each question is scored per passage: +3 per "listen
  for" phrase found, +1 per related capability keyword (max 2), +1 per question key word
  (max 3), +1 when a "how many/how long/cost" question meets a passage with a number,
  +3 for the reply right after the SE asks that question. The best passage per question
  (score ≥ 3 with a real signal) becomes a proposal; at most two questions per passage.
  Questions with a confirmed answer are skipped. With AI on, the model's items are kept
  only if their quote is word for word in one passage. Accepting saves an `assumed`
  answer with the quote; nothing else is stored. Each proposal carries a receipt (HMAC,
  in-memory key) over its deal, question, quote, speaker, timestamp and file, and accept
  refuses quotes without one, so evidence can't be written that the server never found.
- **Gap analysis**: missing required personas (`coverage: required`), unanswered
  qualification checklist items, answers marked `assumed`, requirements without mapped
  capabilities, must-have requirements without success criteria, success criteria
  without a measurable outcome, and no saved demo plan.
- **Suggested next actions**: one deterministic suggestion per gap, which the user can
  turn into a `next_action` task.
- **Capability matching**: keyword matching of requirement text against capability
  `keywords`, plus the `suggests_capabilities` of the question the requirement came from.
  Each match reports the keywords that triggered it.

### Demo builder (`services/demo_builder.py`)

Scores each demo scenario:

- +3 / +2 / +1 for each must / should / could requirement whose capabilities overlap the
  scenario's capabilities;
- +1 for each scenario `pain_keywords` entry found in requirement text or discovery answers;
- +1 when the scenario's `contexts` overlap the deal's technical context.

Scenarios with a requirement match are selected first, then keyword-only matches, until
the time budget or `max_scenarios` is reached. The result contains an agenda, linked
pain points, what each scenario demonstrates, talking points per stakeholder persona,
prerequisites, data requirements, preparation tasks, uncovered requirements, assumptions
and missing evidence. Nothing is invented: every line comes from YAML content or saved
deal data.

### POV builder (`services/pov_builder.py`)

- Creates a POV plan with milestones from `knowledge/pov_template.yaml`, with due dates
  offset from the start date and dependencies mapped to task ids.
- Optionally creates draft success criteria for must/should requirements that have none.
  Drafts have an empty measurable outcome and are flagged as gaps until completed.
- Validation checklist = success criteria grouped by requirement, with evidence counts
  split into real and simulated.
- Markdown export of the plan and a success summary. Simulated evidence is listed under a
  separate heading and never counted.

## LogicMonitor integration: reuse public tooling

The app is the **planning front end**. It never calls the LogicMonitor REST API directly.
Portal work reuses public community projects, pinned in `knowledge/lm_ecosystem.yaml`:

```
             plan (this app)                          portal (customer's LogicMonitor)
┌───────────────────────────────────┐
│ POV plan ──▶ readiness check ─────┼── MCP HTTP ──▶ logicmonitor-api-mcp ──▶ LM API (read)
│          └─▶ setup script (.ps1) ─┼── person reviews & runs ──▶ Logic.Monitor ──▶ LM API (write)
│                │                  │        downloads pinned files from LogicMonitor-Dashboards
│ deal ──▶ handoff JSON ────────────┼──▶ POV tracker (e.g. LMDA)
└───────────────────────────────────┘
```

| Concern | Where | Notes |
|---------|-------|-------|
| Read portal state | `adapters/lm_mcp.py`, `adapters/mcp_client.py` | Minimal MCP Streamable HTTP client (initialize → tools/call, JSON or SSE replies, session header). Parses the server's result format: JSON payload for small lists, Markdown table for larger ones. **List operations only.** Mock mode returns fixtures in the same format. |
| Readiness checks | `services/pov_readiness.py` | Collectors (total/down), POV resource group (exists, resource count), critical alerts. Each check records the tool calls made. Results carry `simulated`. |
| Portal changes | `services/powershell_script.py` | Generates a Logic.Monitor script: dry run unless `-Apply`; credentials only from env vars or a cached credential; idempotent group creation; toolkit modules downloaded from pinned raw URLs, skipped if a module with the same name exists; PropertySources and credentialed suites are listed as manual steps. All interpolated text is emitted as escaped single-quoted literals. |
| Handoff | `services/handoff.py` | Pydantic models → JSON + JSON Schema; see `HANDOFF_FORMAT.md`. |
| Adapter contracts | `adapters/base.py` | Unchanged and standard-library only: actions are `read_only` or `state_changing`; state-changing actions require an `Authorization`. The MCP adapter declares read-only actions only. |

Private or internal repositories (for example LMDA) inform the design but are **reference
only**. No code from them is copied into this public repository.

## Optional LLM (`llm/`)

`LLMProvider.complete(prompt, system) -> str` with three implementations:

| `SEPB_LLM_PROVIDER` | Behaviour |
|---------------------|-----------|
| `none` (default) | Disabled. AI endpoints return HTTP 409 with an explanation. |
| `ollama` | `POST {SEPB_LLM_BASE_URL}/api/chat` |
| `openai_compatible` | `POST {SEPB_LLM_BASE_URL}/chat/completions` (Ollama, vLLM, LM Studio, llama.cpp server, ...) |

Used for an optional "draft discovery summary" and, when the SE ticks "Also ask AI", for
transcript answer suggestions. Summary output is returned as
`{ "draft": ..., "label": "AI-generated draft — verify before use" }` and not saved
automatically. Transcript suggestions are dropped unless their quote is word for word
in the transcript, and are reviewed like keyword matches. No vendor SDKs; plain `httpx`.

## HTTP API (summary)

All routes are under `/api`. Interactive docs: `http://127.0.0.1:8000/docs`.

| Area | Routes |
|------|--------|
| Meta | `GET /health`, `GET /meta`, `POST /sample-data` |
| Library | `GET /library/{personas,capabilities,discovery,demo-scenarios,workflows,pov-template}`, `POST /library/capabilities/match`, `POST /library/reload` |
| Accounts / deals | `GET/POST /accounts`, `GET/PATCH/DELETE /accounts/{id}`, `GET/POST /deals`, `GET/PATCH/DELETE /deals/{id}` |
| Stakeholders | `GET/POST /deals/{id}/stakeholders`, `PATCH/DELETE /stakeholders/{id}` |
| Discovery | `GET /deals/{id}/discovery/questions`, `PUT/DELETE /deals/{id}/discovery/answers/{question_id}`, `GET /deals/{id}/discovery/gaps`, `POST /deals/{id}/discovery/custom-questions[/bulk]`, `DELETE /deals/{id}/discovery/custom-questions/{question_id}` |
| Discovery import (stateless) | `POST /deals/{id}/discovery/transcript/proposals`, `POST /deals/{id}/discovery/transcript/accept`, `POST /deals/{id}/discovery/question-list/proposals` |
| Requirements | `GET/POST /deals/{id}/requirements`, `PATCH/DELETE /requirements/{id}` |
| Demo plans | `GET/POST /deals/{id}/demo-plans`, `GET/DELETE /demo-plans/{id}`, `GET /demo-plans/{id}/export` |
| POV | `GET/POST /deals/{id}/pov-plans`, `GET/PATCH /pov-plans/{id}`, `GET /pov-plans/{id}/export`, `GET/POST /deals/{id}/success-criteria`, `PATCH/DELETE /success-criteria/{id}`, `POST /success-criteria/{id}/evidence`, `DELETE /evidence/{id}` |
| Workflows / tasks | `GET/POST /deals/{id}/workflows`, `DELETE /workflow-runs/{id}`, `GET/POST /deals/{id}/tasks`, `PATCH/DELETE /tasks/{id}` |
| Adapters | `GET /adapters`, `POST /adapters/{id}/actions/{action}` |
| LogicMonitor work | `POST /pov-plans/{id}/readiness`, `POST /pov-plans/{id}/setup-script`, `GET /library/ecosystem` |
| Handoff | `GET /deals/{id}/handoff`, `GET /handoff/schema` |
| Integrations | `POST /integrations/opportunities` (link a system-of-record opportunity to a deal) |
| LLM | `GET /llm/status`, `POST /deals/{id}/llm/discovery-summary` |

## Security posture

| Concern | Default |
|---------|---------|
| Network binding | `127.0.0.1` (also in Docker Compose port mapping) |
| Authentication | None (single local user). Optional static bearer token via `SEPB_API_TOKEN`. |
| CORS | Only the local Vite dev origins |
| Outbound calls | None, unless an LLM provider or `SEPB_ADAPTER_MODE=mcp` is configured |
| LogicMonitor credentials | Never stored or sent by this app; held by the MCP server / the user's PowerShell session |
| Portal writes | Never made by this app; generated scripts are dry-run by default and run by a person |
| Logging | Method, path, status and timing only; request bodies are never logged |
| Secrets | Environment variables only; `.env` is git-ignored |

## Persistence

SQLite via SQLAlchemy 2.x. Tables are created with `metadata.create_all` at start-up.
New nullable columns are added to existing databases at start-up. Full schema migrations
(Alembic) are a planned milestone; for other schema changes delete `data/sepb.db` (the
sample engagement can be reloaded with one click).
