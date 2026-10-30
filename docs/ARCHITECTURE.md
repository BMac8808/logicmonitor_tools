# Repository Architecture

## Goals

- A **library of independent tools**, not one application.
- Each tool can be installed, tested and run on its own.
- Shared conventions (layout, CI, security rules) instead of shared runtime coupling.
- Room for Python, PowerShell, TypeScript, CLI and web tools side by side.

## Layout

```
logicmonitor_tools/
├── docs/            Repository-wide docs (this file, standards, roadmap)
├── shared/          Code reused by two or more tools (empty until needed)
├── tools/<name>/    One self-contained tool per directory
└── .github/
    └── workflows/   One path-filtered workflow per tool
```

## Independence rules

1. A tool never imports from another tool's directory.
2. A tool may depend on a package in `shared/` only after that package exists, has
   tests, and is used by at least two tools.
3. Each tool pins its own dependencies in its own manifest (`pyproject.toml`,
   `package.json`, `*.psd1`, ...). There is no repository-wide lockfile.
4. CI for a tool runs only when that tool (or `shared/` code it uses) changes.

## How shared code will emerge

The SE Demo & POV Builder is the **first consumer** of things like integration adapter
contracts. They live inside that tool for now
(`tools/se-demo-pov-builder/backend/se_pov_builder/adapters/`). They are deliberately
small and have no dependency on the rest of the application (no database, no FastAPI),
so a second tool (for example an inventory exporter) can lift them into
`shared/python/<package>/` without bringing the deal-management app along.

Extraction checklist:

- A second tool needs the same code *now* (not hypothetically).
- Move the code and its tests together; publish as a local package (`pip install -e
  shared/python/<package>`).
- Update both tools to depend on it in the same pull request.

## Integration principles (all tools)

- **Reuse public LogicMonitor tooling first.** Reads go through the public
  logicmonitor-api-mcp server or the Logic.Monitor PowerShell module; tools in this
  repository do not ship their own LogicMonitor API clients unless neither covers the need.
- **Plan here, change there.** Portal changes are emitted as reviewable artifacts
  (dry-run-by-default scripts) that a person runs, not executed by a web app.
- **Credentials stay with the tool that uses them** (MCP server, PowerShell session), never
  in these apps.

- Interfaces separate **read-only** from **state-changing** operations.
- State-changing operations require an explicit authorization object and are disabled
  by default.
- Tool names, cmdlets, endpoints and schemas are used only after checking them against
  official documentation or the reused project's source at a pinned commit. Mock modes
  say so in every result.
- No tool depends on a paid cloud service or a specific AI vendor at runtime. Optional
  AI features use self-hostable or OpenAI-compatible endpoints and are off by default.

## Language conventions

| Kind | Convention |
|------|------------|
| Python service/CLI | `pyproject.toml`, `pytest`, `ruff`, Python ≥ 3.11 |
| Web frontend | Vite + React + TypeScript (`strict`), `vitest` |
| PowerShell | Module manifest (`.psd1`), Pester tests, PSScriptAnalyzer |
| Containers | Optional `docker-compose.yml` per tool, ports bound to `127.0.0.1` |
