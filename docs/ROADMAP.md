# Roadmap

Statuses: **Done**, **In progress**, **Proposed** (not started).

## SE Demo & POV Builder

| Milestone | Status |
|-----------|--------|
| MVP: deal → stakeholders → discovery → criteria → demo plan → POV plan → next actions | Done |
| Database migrations (Alembic) instead of `create_all` | Proposed |
| Multi-user mode with authentication and audit log | Proposed |
| Read-only portal checks via public logicmonitor-api-mcp | Done |
| POV setup scripts via the public Logic.Monitor PowerShell module | Done |
| Handoff export for LMDA (JSON + schema) | Done |
| Validate MCP checks and setup scripts against a sandbox portal; PSScriptAnalyzer in CI | Proposed |
| LMDA-side importer for the handoff format (in LMDA's repository) | Proposed |
| Export POV plan to DOCX/PDF | Proposed |
| Optional LLM drafting for talking points (beyond discovery summary) | Proposed |

See `tools/se-demo-pov-builder/docs/IMPLEMENTATION_PLAN.md` for detail.

## Candidate future tools

| Tool | Notes | Status |
|------|-------|--------|
| Inventory exporter | Read-only export of resources/groups to CSV, built on the Logic.Monitor module or the MCP adapter. Would be the second consumer of the adapter contracts, which would move them into `shared/`. | Proposed |
| LogicModule linter | Offline checks of exported module definitions. | Proposed |
| PowerShell helpers | Scripts built on a community PowerShell module, with Pester tests. | Proposed |
