# Third-party projects

This tool **references and invokes** the public projects below. It does not copy or
redistribute their source code. Pinned commits live in `knowledge/lm_ecosystem.yaml`.

| Project | Licence | How it is used |
|---------|---------|----------------|
| [logicmonitor/lm-powershell-module](https://github.com/logicmonitor/lm-powershell-module) (Logic.Monitor, PowerShell Gallery) | MPL-2.0 | Generated POV setup scripts call its cmdlets. Users install the module themselves. |
| [logicmonitor/logicmonitor-api-mcp](https://github.com/logicmonitor/logicmonitor-api-mcp) | MPL-2.0 | Users run the MCP server themselves. This app calls its tools over HTTP for read-only checks. |
| [stevevillardi/LogicMonitor-Dashboards](https://github.com/stevevillardi/LogicMonitor-Dashboards) | MPL-2.0 | Generated scripts download selected LogicModule files at run time from a pinned commit. The UI links to them. |
| [logicmonitor/monitoring-recipes](https://github.com/logicmonitor/monitoring-recipes) | Apache-2.0 | Linked as reference material for custom-monitoring requirements. |
| [LMDA Composer docs](https://github.com/stevevillardi/lmda-composer-vscode-docs) | not stated | Linked as documentation. |

Field names in `adapters/mock_responses/lm_mcp.json` follow the LogicMonitor REST API schema.
All values are invented.

Private or internal projects may inform the design of this tool, but their code is never
copied into this public repository (see `CONTRIBUTING.md`, "Reusing other projects").
