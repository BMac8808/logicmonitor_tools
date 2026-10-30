# Tool Standards

Every directory under `tools/` must meet these standards before it is listed as
anything beyond "Experimental" in the root catalog.

## Required files

| File | Purpose |
|------|---------|
| `README.md` | Purpose, status, install, run, test, configuration, **implemented vs. proposed** |
| Dependency manifest | `pyproject.toml`, `package.json`, `*.psd1`, ... |
| Tests | Automated tests runnable with one documented command |
| `.env.example` (if configurable) | Every setting documented, no real values |
| `.github/workflows/<tool>.yml` | Path-filtered CI |

## Status levels

- **Experimental** – may be incomplete; README explains what works.
- **MVP** – primary workflow works end to end and is covered by automated tests.
- **Stable** – versioned releases, upgrade notes, no known data-loss bugs.

## Configuration

- Environment variables, prefixed per tool (for example `SEPB_` for SE Demo & POV Builder).
- Secure defaults: bind to loopback, outbound integrations disabled, writes disabled.
- Generated artifacts and local data go in an ignored directory (for example `data/`).

## Documentation honesty

READMEs must separate:

- **Implemented** – works today and is tested.
- **Mock / simulated** – exists but returns synthetic data.
- **Proposed** – designed or planned, not built.

## Testing

- Unit tests for logic, integration tests for the main user journey.
- No network access in tests. Mock every external call.
- CI must run the same commands documented in the README.
