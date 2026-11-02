# Integrations

This app **plans** engagements. Anything that touches a LogicMonitor portal reuses public
community tooling instead of a home-grown API client:

| Need | Tool reused | How |
|------|-------------|-----|
| Read portal state (collectors, groups, resources, alerts, dashboards) | [logicmonitor-api-mcp](https://github.com/logicmonitor/logicmonitor-api-mcp) (MPL-2.0) | `lm_mcp` adapter calls the server's tools over MCP Streamable HTTP, **list operations only** |
| Change the portal (POV resource groups, LogicModule imports) | [Logic.Monitor PowerShell module](https://github.com/logicmonitor/lm-powershell-module) (MPL-2.0) | Generated `.ps1` script, reviewed and run by a person; dry run by default |
| POV LogicModules (NoData, collector health, Windows events, ...) | [LogicMonitor-Dashboards](https://github.com/stevevillardi/LogicMonitor-Dashboards) (MPL-2.0) | Downloaded by the script at run time from a pinned commit |
| Custom monitoring guidance | [monitoring-recipes](https://github.com/logicmonitor/monitoring-recipes) (Apache-2.0), LMDA Composer docs | Linked from requirements |

The catalogue, pinned commits and licences are in `knowledge/lm_ecosystem.yaml`.

## `lm_mcp` adapter

- Code: `backend/se_pov_builder/adapters/` (`base.py` contracts, `mcp_client.py`
  Streamable HTTP client and result parser, `lm_mcp.py` adapter).
- Actions: `list_collectors`, `list_resource_groups`, `list_resources`, `list_alerts`,
  `list_dashboards`, mapped to the server's `lm_collector`, `lm_device_group`, `lm_device`,
  `lm_alert` and `lm_dashboard` tools with `operation: "list"`. They accept `filter`,
  `size` and `fields`.
- **Read-only.** The adapter declares no state-changing actions. The base contract still
  requires an `Authorization` for state-changing actions, should a future adapter add any.
- **No LogicMonitor credentials in this app.** The MCP server holds them (`LM_ACCOUNT`,
  `LM_BEARER_TOKEN` in its environment). `SEPB_MCP_TOKEN` is only the MCP server's own
  bearer token (its `AUTH_MODE=bearer`).

### Modes

| `SEPB_ADAPTER_MODE` | Behaviour |
|---------------------|-----------|
| `mock` (default) | Synthetic fixtures (`mock_responses/lm_mcp.json`) returned in the server's real result format, with a small filter emulation. Every result is labelled simulated. |
| `mcp` | Calls the server at `SEPB_MCP_URL` (default `http://127.0.0.1:3000/mcp`). |

### Running the MCP server locally

```bash
ENABLE_HTTP=true ENABLE_STDIO=false HOST=127.0.0.1 AUTH_MODE=bearer MCP_BEARER_TOKENS=<local-token> LM_ACCOUNT=<portal> LM_BEARER_TOKEN=<read-only-token> npx logicmonitor-api-mcp@2
```

Then start this app with `SEPB_ADAPTER_MODE=mcp` and `SEPB_MCP_TOKEN=<local-token>`. Keep
`HOST=127.0.0.1` and `AUTH_MODE=bearer`: the server's defaults are all interfaces and no
authentication. `<local-token>` is a random string you choose, not a LogicMonitor token. Use a least-privilege, read-only API
user for the token. This app only issues list operations, but the server itself supports
writes.

## Adding an integration

1. Prefer an existing public LogicMonitor community project over new API client code.
2. Verify tool, cmdlet and endpoint names against the project's source at a pinned commit,
   and record the commit in `knowledge/lm_ecosystem.yaml`.
3. Keep reads in adapters. Put changes behind reviewed, dry-run-by-default artifacts
   (scripts) or the `Authorization` contract.
4. Test against fakes (`httpx.MockTransport`). Never call a live portal in CI.
