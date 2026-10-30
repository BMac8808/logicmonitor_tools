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
| POV readiness check (collectors, POV resource group, critical alerts) | **Implemented** | Read-only, via the public [logicmonitor-api-mcp](https://github.com/logicmonitor/logicmonitor-api-mcp) server. Mock mode by default; `SEPB_ADAPTER_MODE=mcp` reads a real portal. Results can be attached as evidence (mock results are flagged simulated). |
| POV portal setup script | **Implemented** | Generated [Logic.Monitor](https://github.com/logicmonitor/lm-powershell-module) PowerShell: resource groups plus selected toolkit LogicModules from pinned public sources. Dry run unless `-Apply`. Not executed in CI (see limitations). |
| POV toolkit catalogue and links to public tooling | **Implemented** | `knowledge/lm_ecosystem.yaml`: community dashboards/LogicModules, monitoring recipes, LMDA Composer docs |
| Handoff export to downstream SE platforms (e.g. LMDA) | **Implemented** | Versioned JSON plus JSON Schema; see [docs/HANDOFF_FORMAT.md](docs/HANDOFF_FORMAT.md) |
| Direct LogicMonitor REST client in this app | **Not planned** | Portal access goes through the public MCP server and PowerShell module instead |
| LMDA round trip (opportunity → deal → POV import) | **Implemented (POC)** | This repo: integration endpoint, deal links, handoff fields. LMDA side (workspace tool card, preview/import into POV challenges, decision/success criteria with activities, contacts) is delivered to the LMDA team separately; tested end to end against a local LMDA instance with fictional data |
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
8. **Hand off.** **Export LMDA handoff (JSON)** in the deal header produces a versioned
   package for the POV tracker.

## Working with LogicMonitor (reuse, not reinvention)

This app is the **planning front end**: deals, discovery, demo and POV planning happen
here, before anything reaches a portal. Work that touches LogicMonitor reuses public
community tooling (pinned in `knowledge/lm_ecosystem.yaml`, details in
[adapters/README.md](adapters/README.md)):

| Step | Tool | In the app |
|------|------|------------|
| Check POV readiness (read-only) | [logicmonitor-api-mcp](https://github.com/logicmonitor/logicmonitor-api-mcp) | POV tab → **Run readiness check** |
| Create POV resource groups, import POV LogicModules | [Logic.Monitor PowerShell module](https://github.com/logicmonitor/lm-powershell-module) + [LogicMonitor-Dashboards](https://github.com/stevevillardi/LogicMonitor-Dashboards) | POV tab → **Download setup script (.ps1)** |
| Build custom monitoring for a requirement | [monitoring-recipes](https://github.com/logicmonitor/monitoring-recipes), [LMDA Composer](https://stevevillardi.github.io/lmda-composer-vscode-docs/) | Requirements tab → "Related public tooling" |
| Start from an LMDA opportunity | LMDA (internal) "SE Demo & POV Builder" workspace tool | Calls `POST /api/integrations/opportunities`; the deal is linked |
| Continue in the POV tracker | LMDA (internal) Scoping Doc → **Import from SE Builder** | Deal header → **Send to LMDA** (linked deals) or **Export LMDA handoff (JSON)** |

Run the setup script yourself after reviewing it:

```powershell
Install-Module -Name Logic.Monitor -Scope CurrentUser
$env:LM_ACCOUNT = '<portal>'; $env:LM_BEARER_TOKEN = '<token>'   # or LM_ACCESS_ID / LM_ACCESS_KEY, or New-LMCachedAccount
./pov-setup-<account>.ps1           # dry run: read-only checks + what would change
./pov-setup-<account>.ps1 -Apply    # make the changes
```

To read a real portal, run the MCP server yourself and point this app at it:

```bash
ENABLE_HTTP=true LM_ACCOUNT=<portal> LM_BEARER_TOKEN=<token> npx logicmonitor-api-mcp@2
SEPB_ADAPTER_MODE=mcp make backend
```

LogicMonitor credentials stay in the MCP server and in your PowerShell session. This app
never stores them.

## Configuration

All settings are environment variables prefixed `SEPB_`; see [.env.example](.env.example).
Key defaults: bind `127.0.0.1:8000`, SQLite at `data/sepb.db`, adapter `mock`
(`mcp` + `SEPB_MCP_URL` for real reads), LLM `none`.

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
| Public LM tooling, POV toolkit, reference links | `knowledge/lm_ecosystem.yaml` | [adapters/README.md](adapters/README.md) |
| Mock MCP responses | `adapters/mock_responses/lm_mcp.json` | [adapters/README.md](adapters/README.md) |

Run `make validate-content` after editing, then **Library → Reload content from disk**
(or restart the server).

## Security and data handling

- Single local user. No accounts; binds to loopback. `SEPB_API_TOKEN` adds a shared
  bearer token but is not a substitute for real authentication. Don't expose the app
  on a network without your own access controls and TLS.
- No outbound network calls unless you configure an LLM endpoint or `SEPB_ADAPTER_MODE=mcp`.
- No LogicMonitor credentials are stored or sent by this app. The MCP server and your
  PowerShell session hold them.
- Request bodies are never logged; logs contain method, path, status and timing.
- Data lives in `data/` (git-ignored). Delete `data/sepb.db` to reset.
- Synthetic data only. The sample company and people are invented.

## Known limitations

- No full schema migrations: new nullable columns are added automatically to existing
  databases; anything else requires deleting `data/sepb.db` (sample data reloads with one click).
- Generated PowerShell scripts are covered by content tests (dry-run guards, escaping,
  pinned sources, no credentials) but were **not executed** against PowerShell or a portal
  in this repository's CI. Run the dry run first.
- The MCP client was tested against a protocol-faithful fake, not a running
  `logicmonitor-api-mcp` server. Tool names and result formats follow its source at the
  pinned commit.
- Readiness critical-alert counts are portal-wide, as returned by the server's alert list.
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
- [docs/HANDOFF_FORMAT.md](docs/HANDOFF_FORMAT.md): handoff export for downstream SE platforms
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md): public projects referenced and their licences
