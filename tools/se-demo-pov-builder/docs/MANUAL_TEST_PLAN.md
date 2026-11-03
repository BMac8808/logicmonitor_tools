# Manual test plan

Hands-on checks for a person, alongside the automated tests (`make test`). Work top to
bottom and note each result (pass, fail, or a comment) in the findings table at the end.
Section A touches no portal; C only reads from one; D changes one.

Start the app (`make dev`, or `make build` then `make serve`) and open it. The LMDA round
trip (opportunity → deal → POV import) is checked separately, with the LMDA dev kit,
because the LMDA side is not in this repository.

## A. SE Builder on its own (no portal)

**Deals** → **Load sample engagement**.

| # | Check |
|---|-------|
| A1 | ☐ Overview shows summary tiles and top gaps. **Add next action** on a gap creates a task in Next actions. |
| A2 | ☐ Stakeholders: add one with an email. A bad email is rejected. "Show guidance" shows the persona's objections and approach. |
| A3 | ☐ Discovery: the suggested questions change when you add a persona or technology tag. Save an answer as *assumed*; its checklist item turns amber. |
| A4 | ☐ Discovery → **→ Requirement** creates a requirement that keeps its source question. |
| A5 | ☐ Requirements: edit business impact inline. "Related public tooling" links open the right public repos. |
| A6 | ☐ Demo plan: generate 45 and 60 minute plans. The agenda adds up to the time, each scenario says why it was picked, and uncovered requirements are listed. Export Markdown. Add a requirement afterwards: the saved plan says it's out of date. |
| A7 | ☐ POV: try to mark a criterion **met** with only *simulated* evidence; it must be refused. Add real evidence; now it's allowed. |
| A8 | ☐ POV milestones: completing one before its dependency is refused with a reason. |
| A9 | ☐ Workflows: start one; blocked needs a reason; evidence-required tasks need a note. |
| A10 | ☐ Library: personas, capabilities, scenarios, workflows, **LM tooling**. |
| A11 | ☐ Discovery: **Start here** shows 3–5 questions, each with a reason. Clicking one opens it in the list. |
| A12 | ☐ Questions are one line each, grouped by category, and expand when clicked. **All questions** shows all 31; the ones not suggested are marked "not suggested". |
| A13 | ☐ **+ Question** adds a custom question. It appears with a "custom" tag and can be answered and deleted. Link it to a checklist item and answer it as confirmed: that checklist item turns green. |
| A14 | ☐ Clicking a checklist item (e.g. Budget) shows only its questions. **Show all** clears the filter. |
| A15 | ☐ The gaps column reads normally (no 2–3 words per line). |
| A16 | ☐ **Import transcript / list**: drop a `.vtt` or `.srt`, or paste a transcript. Each proposal shows the exact quote with speaker and time. **Accept as assumed** saves the answer as amber *assumed*, and the quote shows when you open the question. Questions already confirmed are not proposed. Restart SE Builder between **Find answers** and **Accept**: the accept is refused and asks you to run Find answers again. |
| A17 | ☐ **Question list** mode: paste your own list. Near-identical questions are flagged "Similar to" and unticked; rewordings may show "Possibly similar to" and stay ticked. The ones you add become custom questions. |
| A18 | ☐ Requirements show "From discovery: <question text>" and the saved answer, not an id like `tech_network`. |
| A19 | ☐ Demo plan and POV show coloured summary tiles. Uncovered requirements appear in an amber box, and one "not yet verified" line appears per section. |
| A20 | ☐ Switch the OS to dark mode: all of the above is readable. Check the footer legend: red blocked, amber attention, blue in progress, green done, purple simulated, grey not started. |

Real call transcripts are customer data: for A16, use a call you're allowed to process
locally. The transcript isn't stored, but accepted quotes are.

## C. Real portal, read-only (MCP)

**Credentials:** an API-only user with a **read-only** role and a bearer token. Keep the
token in your shell only, never in an `.env` file.

1. Start the public MCP server **on localhost, with its own token**. Its defaults (all
   interfaces, no auth) would expose your portal to the network. Port 3100 avoids
   clashing with other local apps on 3000.

   ```bash
   export MCP_TOKEN=$(openssl rand -hex 24)
   ```
   ```bash
   ENABLE_HTTP=true ENABLE_STDIO=false HOST=127.0.0.1 PORT=3100 AUTH_MODE=bearer MCP_BEARER_TOKENS=$MCP_TOKEN LM_ACCOUNT=<your-portal> LM_BEARER_TOKEN=<read-only-token> npx -y logicmonitor-api-mcp@2
   ```

2. Restart SE Builder in MCP mode, in a shell where `MCP_TOKEN` is set:

   ```bash
   SEPB_ADAPTER_MODE=mcp SEPB_MCP_URL=http://127.0.0.1:3100/mcp SEPB_MCP_TOKEN=$MCP_TOKEN make serve
   ```

| # | Check |
|---|-------|
| C1 | ☐ The header says "adapters: mcp". Integrations shows **live via MCP**. |
| C2 | ☐ Integrations → `list_collectors` → **Run**: your real collectors, **no** SIMULATED banner, and no tokens or config files in the output. Try filter `isDown:true`. |
| C3 | ☐ `list_resource_groups` with filter `name:"<an existing group>"` finds it. `list_alerts` with `severity:4` matches the portal UI. |
| C4 | ☐ POV tab → set **Portal resource group** to a name that does **not** exist yet (e.g. `POV - SEB Test`) → **Run readiness check**: collectors correct, group "not found", alert count plausible. |
| C5 | ☐ **Attach** a readiness result to a criterion. The evidence is *not* simulated and its reference names the MCP tool. |
| C6 | ☐ Stop the MCP server and re-run the check: each check shows a clear "Cannot reach MCP server" error and the app keeps working. |
| C7 | ☐ A wrong `SEPB_MCP_TOKEN` gives a clear "check SEPB_MCP_TOKEN" error. |

## D. Real portal, changes (PowerShell setup script)

This creates resource groups and imports LogicModules. Use a portal where that's
acceptable and a token whose role can manage resource groups and LogicModules.

**Pick the first module carefully.** The *NoData* modules apply to every
collector-monitored resource. For the first apply, select only **Collector
configurations**, which applies to collectors only (it imports as a ConfigSource).

1. Install PowerShell 7 and the module (macOS shown):

   ```bash
   brew install --cask powershell
   ```
   ```bash
   pwsh -c "Install-Module -Name Logic.Monitor -Scope CurrentUser"
   ```

2. POV tab → tick **Collector configurations** only → **Download setup script (.ps1)**.
   Read the script before running it.
3. Dry run (changes nothing), then apply:

   ```bash
   LM_ACCOUNT=<your-portal> LM_BEARER_TOKEN=<token> pwsh ./pov-setup-<account>.ps1
   ```
   ```bash
   LM_ACCOUNT=<your-portal> LM_BEARER_TOKEN=<token> pwsh ./pov-setup-<account>.ps1 -Apply
   ```

| # | Check |
|---|-------|
| D1 | ☐ The dry run connects, lists collectors, prints `[DRY RUN] Would: …` for each group and import, offers no subgroups that already exist, and changes nothing. |
| D2 | ☐ `-Apply` creates `POV - SEB Test` under the root group plus one subgroup per technology tag, with `pov.*` properties, and imports **LogicMonitor_Collector_Configurations** as a ConfigSource. Check in the portal UI. |
| D3 | ☐ Run `-Apply` again: the group is reused, subgroups are "exists; skipped", and the module shows "already exists; skipped". Nothing is duplicated or updated. |
| D4 | ☐ Back in SE Builder → **Run readiness check**: the POV group is now **found** (resource count shown). |
| D5 | ☐ If you have a module with the same name as a toolkit item, it is *not* overwritten. |
| D6 | ☐ Manual steps (PropertySources, the Alert Duration suite) are printed, not executed. |

**Cleanup** (both cmdlets ask for confirmation):

```bash
pwsh -c 'Connect-LMAccount -BearerToken $env:LM_BEARER_TOKEN -AccountName $env:LM_ACCOUNT; Remove-LMDeviceGroup -Name "POV - SEB Test" -DeleteHostsandChildren $true; Remove-LMConfigsource -Name "LogicMonitor_Collector_Configurations"'
```

Only delete a module this test imported. If it existed before, D3/D5 skipped it, so leave
it in place.

## Findings

| # | Pass/Fail | What happened (error text, screenshot, steps) |
|---|-----------|-----------------------------------------------|
|   |           |                                               |

Before sharing logs or screenshots, remove portal names, tokens and customer data.
