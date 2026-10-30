# Adapters

Contracts and mock data for future integrations. **Every adapter in the MVP is a mock.**

| Adapter id | Purpose | Mode | Verified |
|------------|---------|------|----------|
| `lm_rest_api` | Platform REST API (resources, groups, alerts, collectors) | mock | no |
| `lm_powershell` | Scripts using a community PowerShell module | mock | no |
| `logicmodule_tools` | Review/edit LogicModule definitions | mock | no |
| `lm_mcp` | Model Context Protocol bridge | mock | no |

- Code: `backend/se_pov_builder/adapters/` (`base.py` = contracts, `mock.py` = mocks).
- Fixtures: `mock_responses/<adapter_id>.json`. All data is synthetic; field names are
  illustrative, **not** the real API schema.
- Action names are abstract (`list_resources`, ...) and are not mapped to endpoint paths
  or cmdlets. That mapping is added only when a live adapter is built and checked against
  official documentation.

## Read-only vs state-changing

Every action is declared `read_only` or `state_changing`. State-changing actions require
an `Authorization` (approver, reason, scope `"<adapter>:<action>"`, expiry), even in mock
mode, and mock adapters only return a dry-run description.

## Adding a live adapter (future)

1. Confirm endpoints, authentication, pagination and rate limits in official docs, and
   link them in the pull request.
2. Implement a new `Adapter` subclass with `mode = "live"`; start with read-only actions.
3. Read credentials from environment variables only; never log them.
4. Keep tests on mocks (`httpx.MockTransport`); never call a live portal in CI.
5. Keep state-changing actions behind `Authorization` and an explicit opt-in setting.
