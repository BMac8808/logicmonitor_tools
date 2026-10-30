# Contributing

Thanks for helping. This repository collects **independent** tools, so most
contributions touch exactly one directory under `tools/`.

## Before you start

1. Read [SECURITY.md](SECURITY.md). Never commit real customer data, credentials,
   portal names, internal URLs, or proprietary code.
2. Open an issue describing the change if it is larger than a bug fix.
3. Work on a feature branch and open a pull request against the default branch.

## Working on an existing tool

Each tool documents its own setup in its README. For the SE Demo & POV Builder:

```bash
cd tools/se-demo-pov-builder
make install
make test      # backend pytest + frontend vitest
make lint      # ruff + TypeScript type-check
```

CI runs the same commands (see `.github/workflows/`). Pull requests must be green.

### Content-only changes

Many tools are driven by versioned configuration (YAML) rather than code. For example,
SE Demo & POV Builder personas, discovery questions, demo scenarios and workflows live in
`tools/se-demo-pov-builder/{personas,knowledge,workflows}/`. To change them:

1. Edit or add the YAML file.
2. Run `make validate-content` in the tool directory.
3. Bump the `version` field of the file you changed.

Capability descriptions must be **conservative and verifiable**. Do not describe product
features you have not confirmed in current official documentation. Leave
`verified: false` unless you include a documentation reference in the pull request.

## Adding a new tool

1. Create `tools/<tool-name>/` using lowercase-kebab-case.
2. Include at minimum: `README.md` (purpose, status, install, run, test, configuration,
   implemented vs. proposed), a dependency manifest, tests, and an example config file if
   the tool needs configuration.
3. Add a path-filtered workflow in `.github/workflows/<tool-name>.yml`.
4. Add a row to the catalog in the root `README.md`.
5. Follow [docs/TOOL_STANDARDS.md](docs/TOOL_STANDARDS.md).

## Shared code

`shared/` starts empty on purpose. Extract code into it only when a **second** tool
actually needs it, and move it together with its tests. See [shared/README.md](shared/README.md).

## Reusing other projects

- **Prefer existing public LogicMonitor community tooling** (Logic.Monitor PowerShell
  module, logicmonitor-api-mcp, LogicMonitor-Dashboards, monitoring-recipes) over writing new
  API clients. Invoke or reference them, and pin the reviewed commit.
- **Respect licences.** Prefer referencing, invoking or downloading at run time over
  copying. If you do copy MPL-2.0 files, keep them in separate files under MPL-2.0 with
  their notices. Record every referenced project in the tool's `THIRD_PARTY_NOTICES.md`.
- **Private or internal repositories are reference only.** Their ideas can inform a
  design, but their code, schemas, configuration and data must not be copied into this
  public repository, even when the private copy carries an open-source licence file.
  Publishing that code is the owner's decision, not a contributor's.

## Integrations with real APIs

- Implement against official documentation only, and link the documentation section in
  the pull request.
- Separate read-only operations from state-changing ones. State-changing operations
  must require explicit authorization and must be off by default.
- Tests must never call live services; use recorded or hand-written mock responses.

## Style

- Python: formatted and linted with `ruff`; type hints on public functions.
- TypeScript: `strict` mode; `tsc --noEmit` must pass.
- Keep dependencies few and well-known. Justify new ones in the pull request.
- Commit messages: imperative mood, short subject line, explanatory body when useful.

## Trademarks

Use "LogicMonitor" only to describe compatibility (for example "for use with
LogicMonitor"). Do not use logos, product icons or wording that implies endorsement.
