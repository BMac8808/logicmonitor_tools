# SE Demo & POV Builder — Acceptance Criteria (MVP)

Each criterion lists how it is verified. "Journey test" means
`backend/tests/test_user_journey.py`, which drives the full workflow through the HTTP API.

| # | Criterion | Verified by |
|---|-----------|-------------|
| AC1 | The tool starts locally with documented commands (`make install`, `make dev`, or `docker compose up`). | README; manual check |
| AC2 | A fictional account and a deal can be created, edited and listed. | Journey test; `DealsPage.test.tsx` |
| AC3 | Stakeholders can be added and assigned any persona from `personas/`. Unknown persona ids are rejected. | Journey test; `test_api_validation.py` |
| AC4 | Discovery questions are selected from the stakeholders' personas and the deal's technical context. | `test_discovery.py` |
| AC5 | Discovery answers can be saved, updated and reloaded, with evidence source and confidence. | Journey test; `Discovery.test.tsx` |
| AC6 | Gap analysis reports missing required personas, unanswered qualification items and assumed answers, and suggests next actions. | `test_discovery.py`; journey test |
| AC7 | Requirements can be captured and mapped to capabilities; matches explain which keywords triggered them. | `test_discovery.py`; journey test |
| AC8 | A demo plan is generated only from saved discovery data and YAML content, includes agenda, linked pain points, talking points per persona, prerequisites, assumptions and missing evidence, and fits the time budget. | `test_demo_builder.py`; journey test |
| AC9 | Generating a demo plan with no requirements still works and says why the plan is generic. | `test_demo_builder.py` |
| AC10 | POV success criteria can be defined with measurable outcome, target, validation method and owner, and their status tracked. | Journey test; `test_pov.py` |
| AC11 | A criterion cannot be marked `met` without at least one non-simulated evidence item. Simulated evidence is labelled in API responses, UI and exports. | `test_pov.py` |
| AC12 | A POV plan creates milestones with dependencies; a milestone cannot be completed before its dependencies. | `test_pov.py`; `test_workflow_engine.py` |
| AC13 | The POV plan and success summary export to Markdown. | Journey test |
| AC14 | Workflows are loaded from `workflows/*.yaml`; adding a file adds a workflow without code changes. | `test_knowledge.py` |
| AC15 | Next actions can be created, updated (owner, due date, status, blocker) and completed. | Journey test; `test_workflow_engine.py` |
| AC16 | The full journey works with `SEPB_LLM_PROVIDER=none`. | Journey test runs with LLM disabled |
| AC17 | Portal reads go through the public `logicmonitor-api-mcp` tools with list operations only; mock-mode results are labelled simulated; the base contract rejects state-changing actions without authorization; no LogicMonitor credential headers are sent. | `test_adapters.py` |
| AC18 | Persona, question, scenario and workflow content is validated; broken references are reported. | `test_knowledge.py`; `make validate-content` |
| AC19 | No secrets are committed; servers bind to loopback by default; request bodies are not logged. | Code review; `test_security.py` |
| AC20 | Documentation separates implemented, mock and proposed features. | `README.md` "Feature status" table |
| AC21 | A read-only POV readiness check reports collectors, the POV resource group and critical alerts, records the tool calls, and can be attached as evidence with the simulated flag preserved. | `test_lm_integration.py`; `PovTab.test.tsx` |
| AC22 | A Logic.Monitor setup script can be generated for a POV: dry run unless `-Apply`, no embedded credentials, pinned public sources, dependencies resolved, existing modules never overwritten, user text safely escaped. | `test_lm_integration.py` |
| AC23 | A versioned handoff package (with JSON Schema) can be exported for downstream SE platforms; simulated evidence is flagged. | `test_lm_integration.py` |
| AC24 | Public LM tooling is catalogued with pinned commits and licences; references are validated. | `test_knowledge.py`; `make validate-content` |
| AC25 | A system of record can link an opportunity to a deal idempotently; linked deals expose a "Send to LMDA" link built from the system's own template; URLs must be http(s). | `test_integrations.py`; `DealWorkspace.test.tsx` |
| AC26 | The handoff carries the deal link, stakeholder emails and per-requirement business impact for importers. | `test_integrations.py` |
| AC27 | Every deal can browse all bank questions (suggested ones flagged) and add, answer and delete its own custom questions; custom questions count towards the checklist, gaps, requirements and handoff. | `test_discovery_import.py`; `Discovery.test.tsx` |
| AC28 | Discovery shows a compact list grouped by category, a "Start here" box with 3–5 next questions and their reasons, and a checklist item filter. | `test_discovery_import.py`; `Discovery.test.tsx` |
| AC29 | A transcript (pasted, `.txt`, `.vtt`, `.srt`) yields proposals with the exact quote, speaker and time; nothing is stored until a proposal is accepted; accepted answers are `assumed` with the quote as evidence; confirmed answers are never replaced; AI proposals need a verbatim quote. | `test_discovery_import.py`; `Discovery.test.tsx` |
| AC30 | Requirements show the source question text and saved answer instead of a question id. | `PlanVisuals.test.tsx` |
| AC31 | One colour per state; generated text styled apart from user values; one unverified notice per section; demo plan and POV summary tiles with an amber callout for uncovered requirements. | `PlanVisuals.test.tsx`; light/dark screenshots |
