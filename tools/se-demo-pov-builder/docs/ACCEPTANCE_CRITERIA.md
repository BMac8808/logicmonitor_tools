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
| AC17 | Adapters are mock-only, label results as simulated, and reject state-changing actions without authorization. | `test_adapters.py` |
| AC18 | Persona, question, scenario and workflow content is validated; broken references are reported. | `test_knowledge.py`; `make validate-content` |
| AC19 | No secrets are committed; servers bind to loopback by default; request bodies are not logged. | Code review; `test_security.py` |
| AC20 | Documentation separates implemented, mock and proposed features. | `README.md` "Feature status" table |
