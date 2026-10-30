# LogicMonitor Tools (Community)

A community-maintained toolbox of independent utilities for people who work with
LogicMonitor: Sales Engineers, administrators, consultants and technical leaders.

> **Not an official LogicMonitor product.** This repository is maintained independently
> and is not affiliated with, sponsored by, or endorsed by LogicMonitor, Inc.
> "LogicMonitor" is used only to describe the platform these tools are meant to work
> alongside. All bundled data is synthetic. Nothing here makes production API calls.

## Tool catalog

| Tool | Status | Stack | Description |
|------|--------|-------|-------------|
| [SE Demo & POV Builder](tools/se-demo-pov-builder/) | MVP | Python (FastAPI) + React (TypeScript) + SQLite | Plan and track technical sales engagements: stakeholders, discovery, demo plans, Proof of Value plans and next actions. Runs locally and works without an LLM. Portal work reuses the public MCP server and Logic.Monitor PowerShell module; exports a handoff package for LMDA. |

Planned ideas (not started): inventory exporter, DataSource/LogicModule validator,
PowerShell helper scripts. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Reuse before reinventing

Tools here plan, prepare and document work. Anything that touches a LogicMonitor portal
reuses existing public community projects instead of new API clients:

| Project | Licence | Used for |
|---------|---------|----------|
| [lm-powershell-module](https://github.com/logicmonitor/lm-powershell-module) (Logic.Monitor) | MPL-2.0 | Generated setup scripts (portal changes, reviewed and run by a person) |
| [logicmonitor-api-mcp](https://github.com/logicmonitor/logicmonitor-api-mcp) | MPL-2.0 | Read-only portal checks over MCP |
| [LogicMonitor-Dashboards](https://github.com/stevevillardi/LogicMonitor-Dashboards) | MPL-2.0 | POV LogicModules and dashboards, downloaded from pinned commits |
| [monitoring-recipes](https://github.com/logicmonitor/monitoring-recipes) | Apache-2.0 | Module authoring guidance and recipes |
| [LMDA Composer docs](https://stevevillardi.github.io/lmda-composer-vscode-docs/) | — | LogicModule script development |

Private or internal repositories may inform designs but their code is never copied here.
See [CONTRIBUTING.md](CONTRIBUTING.md#reusing-other-projects).

## Repository layout

```
logicmonitor_tools/
├── README.md              # This catalog
├── CONTRIBUTING.md        # How to contribute and add a tool
├── SECURITY.md            # Data handling rules and vulnerability reporting
├── docs/                  # Repository-wide architecture, standards, roadmap
├── shared/                # Reusable code, extracted only when a 2nd tool needs it
├── tools/                 # One directory per independent tool
│   └── se-demo-pov-builder/
└── .github/workflows/     # CI, one workflow per tool (path-filtered)
```

Every tool is self-contained: its own README, dependencies, configuration, tests and
install instructions. Tools do not import from each other. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/TOOL_STANDARDS.md](docs/TOOL_STANDARDS.md).

## Quick start (SE Demo & POV Builder)

```bash
cd tools/se-demo-pov-builder
make install    # Python venv + npm packages
make dev        # API on 127.0.0.1:8000, UI on 127.0.0.1:5173
```

Full instructions: [tools/se-demo-pov-builder/README.md](tools/se-demo-pov-builder/README.md).

## Ground rules

- Synthetic data only. Never commit customer names, credentials, portal names,
  screenshots of real environments or anything confidential.
- No hardcoded secrets. Configuration is read from environment variables; only
  `*.example` files are committed.
- Integrations against real APIs are added only after they are checked against official
  documentation, and anything that changes state needs explicit authorization.
- Each tool's README states plainly what is implemented and what is only proposed.

## License

**No license has been selected yet.** Until the owner adds one, default copyright
applies and nobody else may reuse the code. A recommendation is in
[docs/LICENSE_RECOMMENDATION.md](docs/LICENSE_RECOMMENDATION.md).
