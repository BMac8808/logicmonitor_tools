# SE Demo & POV Builder

A local web app that helps Sales Engineers plan, run and track technical sales
engagements: stakeholders and personas, guided discovery, requirement-to-capability
mapping, tailored demo plans, measurable Proof of Value (POV) plans, and next actions.

> Community tool. **Not an official LogicMonitor product** and not endorsed by
> LogicMonitor, Inc. Use **synthetic data only**. Capability descriptions are unverified
> community summaries; check them against current official documentation before you
> present anything to a customer.

**Status: MVP.** The full journey works end to end without any AI service:

```
Create Deal → Identify Stakeholders → Conduct Discovery → Define Success Criteria
            → Generate Demo Plan → Build POV Plan → Track Next Actions
```

## Quick start

Requirements: Python 3.11+, Node.js 20+ (22 recommended), `make`.

```bash
cd tools/se-demo-pov-builder
make install      # creates .venv, installs backend + frontend dependencies
make dev          # API on http://127.0.0.1:8000, UI on http://127.0.0.1:5173
```

Open http://127.0.0.1:5173 and click **Load sample engagement** to explore a complete,
fictional engagement, or **New deal** to start your own.

Single-process alternative (build the UI once, then serve everything from the API):

```bash
make build
make serve        # http://127.0.0.1:8000
```

Docker (ports are published on `127.0.0.1` only):

```bash
docker compose up --build    # http://127.0.0.1:8000
```

Without `make`:

```bash
python3 -m venv .venv && .venv/bin/pip install -e "backend[dev]"
(cd frontend && npm ci)
.venv/bin/python -m se_pov_builder          # terminal 1
(cd frontend && npm run dev)                 # terminal 2
```

On Windows, use `.venv\Scripts\python` instead of `.venv/bin/python`.

## Tests

```bash
make test               # backend (pytest) + frontend (vitest)
make lint               # ruff + tsc type-check
make validate-content   # check personas/, knowledge/, workflows/ for errors
```

`backend/tests/test_user_journey.py` drives the whole primary journey through the HTTP
API with the LLM disabled. Acceptance criteria and how each is verified:
[docs/ACCEPTANCE_CRITERIA.md](docs/ACCEPTANCE_CRITERIA.md).

## Feature status

| Area | Status | Notes |
|------|--------|-------|
| Accounts & deals (fictional), technical context tags | **Implemented** | |
| Stakeholders with personas, influence, stance, persona guidance | **Implemented** | 7 personas in `personas/` |
| Persona library editable as YAML, reloadable at runtime | **Implemented** | Library → Reload content |
| Discovery coach: question selection by persona + context | **Implemented** | 31 deterministic questions |
| Answers with evidence source and confidence (confirmed/assumed) | **Implemented** | |
| Qualification checklist, gap analysis, suggested next actions | **Implemented** | Rule-based |
| Requirements with keyword/question-based capability mapping | **Implemented** | Matches explain their keywords |
| Demo plan generation (agenda, scenarios, talking points, prerequisites, assumptions, missing evidence) | **Implemented** | Versioned; Markdown export |
| POV plans: milestones with dependencies, success criteria, validation checklist, evidence | **Implemented** | Markdown export with success summary |
| Simulated-evidence safeguards | **Implemented** | Simulated items are labelled, excluded from counts, cannot mark a criterion met |
| Workflow engine (7 YAML workflows, stages, dependencies, blockers, evidence-required tasks) | **Implemented** | |
| Next actions (owner, due date, status, blocker, dependencies) | **Implemented** | |
| Optional API token | **Implemented** | `SEPB_API_TOKEN` |
| Optional LLM: discovery summary draft (Ollama / OpenAI-compatible) | **Implemented, off by default** | Output labelled as an AI draft, never auto-saved |
| Adapters: REST API, PowerShell, LogicModule utilities, MCP | **Mock only** | Synthetic fixtures; state-changing actions require authorization and only dry-run |
| Live integrations with any real portal | **Proposed** | Only after verification against official documentation |
| Multi-user, authentication, audit log | **Proposed** | |
| Database migrations (Alembic) | **Proposed** | Currently `create_all` |
| DOCX/PDF export | **Proposed** | Markdown today |

## Using the app

1. **Deals → New deal.** Pick the technologies in scope; they decide which technical
   questions appear.
2. **Stakeholders.** Add people and assign personas. A banner lists required personas
   (Champion, Economic Buyer, Technical Buyer) not yet identified. "Show guidance" shows
   the persona's engagement approach, objections and signals.
3. **Discovery.** Answer questions in the customer's words, with who said it, where, and
   whether it is confirmed or assumed. Use **→ Requirement** on an answered question to
   create a requirement that keeps its source. The side panel shows the qualification
   checklist and gaps; **Add next action** turns any gap into a task.
4. **Requirements.** Review priorities and capability mappings. All bundled capabilities
   are marked *unverified*.
5. **Demo plan.** Generate a plan for a time budget. Each scenario says why it was chosen,
   which requirements it covers, and talking points for the personas present. Uncovered
   requirements, assumptions and missing evidence are listed. Export to Markdown.
6. **POV.** Create a plan (milestones come from `knowledge/pov_template.yaml`); optionally
   draft criteria for must/should requirements. Define measurable outcomes, validation
   methods and owners; record evidence. Export the plan and success summary.
7. **Workflows / Next actions.** Start any workflow, then track tasks, owners, due dates,
   blockers and dependencies.

## Configuration

All settings are environment variables prefixed `SEPB_`; see [.env.example](.env.example).
Key defaults: bind `127.0.0.1:8000`, SQLite at `data/sepb.db`, adapters `mock`, LLM `none`.

### Optional LLM

```bash
# Ollama native API
SEPB_LLM_PROVIDER=ollama SEPB_LLM_BASE_URL=http://127.0.0.1:11434 SEPB_LLM_MODEL=llama3.1 make backend
# Any OpenAI-compatible server (vLLM, LM Studio, llama.cpp server, Ollama /v1, ...)
SEPB_LLM_PROVIDER=openai_compatible SEPB_LLM_BASE_URL=http://127.0.0.1:8001/v1 SEPB_LLM_MODEL=my-model make backend
```

When enabled, the Discovery tab offers **Draft summary**. Nothing else uses the LLM.

## Customising content (no code changes)

| What | Where | Docs |
|------|-------|------|
| Personas | `personas/*.yaml` | [personas/README.md](personas/README.md) |
| Capabilities, discovery questions, demo scenarios, POV milestones | `knowledge/*.yaml` | [knowledge/README.md](knowledge/README.md) |
| Workflows | `workflows/*.yaml` | [workflows/README.md](workflows/README.md) |
| Mock adapter responses | `adapters/mock_responses/*.json` | [adapters/README.md](adapters/README.md) |

Run `make validate-content` after editing, then **Library → Reload content from disk**
(or restart the server).

## Security and data handling

- Single local user. No accounts; binds to loopback. `SEPB_API_TOKEN` adds a shared
  bearer token but is not a substitute for real authentication. Don't expose the app
  on a network without your own access controls and TLS.
- No outbound network calls unless you configure an LLM endpoint.
- Request bodies are never logged; logs contain method, path, status and timing.
- Data lives in `data/` (git-ignored). Delete `data/sepb.db` to reset.
- Synthetic data only. The sample company and people are invented.

## Known limitations

- No schema migrations: after pulling model changes, delete `data/sepb.db` (sample data
  reloads with one click).
- Single user; no concurrency control between browser tabs (last write wins).
- Capability mapping is keyword-based and can miss synonyms; review mappings manually.
- Demo scenario selection is greedy and rule-based, not optimal scheduling.
- Workflow runs keep the tasks they were created with; editing a workflow YAML affects
  new runs only.
- The Docker image has not been built in CI yet; the documented `make` path is the
  tested one.

## Architecture and plans

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): components, data model, engines, API, security
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md): phases and next milestones
- [docs/ACCEPTANCE_CRITERIA.md](docs/ACCEPTANCE_CRITERIA.md): MVP criteria and verification
