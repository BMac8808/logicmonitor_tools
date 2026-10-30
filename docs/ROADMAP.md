# Roadmap

Statuses: **Done**, **In progress**, **Proposed** (not started).

## SE Demo & POV Builder

| Milestone | Status |
|-----------|--------|
| MVP: deal → stakeholders → discovery → criteria → demo plan → POV plan → next actions | Done |
| Database migrations (Alembic) instead of `create_all` | Proposed |
| Multi-user mode with authentication and audit log | Proposed |
| Read-only LogicMonitor REST adapter, verified against official docs | Proposed |
| Export POV plan to DOCX/PDF | Proposed |
| Optional LLM drafting for talking points (beyond discovery summary) | Proposed |

See `tools/se-demo-pov-builder/docs/IMPLEMENTATION_PLAN.md` for detail.

## Candidate future tools

| Tool | Notes | Status |
|------|-------|--------|
| Inventory exporter | Read-only export of resources/groups to CSV. Would be the second consumer of the adapter contracts, which would move them into `shared/`. | Proposed |
| LogicModule linter | Offline checks of exported module definitions. | Proposed |
| PowerShell helpers | Scripts built on a community PowerShell module, with Pester tests. | Proposed |
