# Security and Data Handling

## Reporting a vulnerability

Please do not open a public issue for security problems. Use GitHub's
"Report a vulnerability" (private security advisory) on this repository instead.

## Data rules for contributors

- **Synthetic data only.** Sample accounts, people and environments must be invented.
  Do not reuse real company or person names from your work.
- **No secrets in git.** API keys, tokens, portal names and passwords are read from
  environment variables. Only `*.example` files are committed; `.env` files are ignored.
- **No live calls in tests or CI.** Integrations are exercised with mock responses.
- **Local by default.** Servers bind to `127.0.0.1` unless the operator explicitly
  changes it. Tools do not phone home and do not send telemetry.
- **Explicit opt-in for outbound calls.** Features that contact external services
  (for example an optional LLM endpoint) are disabled until configured.

## Operator responsibilities

The tools assume a single trusted local user unless a tool's README says otherwise.
If you choose to expose a tool on a network, put it behind your own authentication and
TLS, and review its README for the configuration options it offers.
