# Handoff format (`se-demo-pov-builder/handoff`, version 1)

When an engagement moves into a POV tracker or SE platform (for example LogicMonitor's
internal LMDA), export a handoff package instead of re-typing discovery. The handoff is a
temporary, one-way bridge while capabilities are prototyped in this app: version 1 gets
fixes but no new fields, and nothing syncs back.

- UI: **Export LMDA handoff (JSON)** in the deal header.
- API: `GET /api/deals/{deal_id}/handoff[?pov_plan_id=N]` (latest POV plan by default).
- JSON Schema: `GET /api/handoff/schema` (generated from
  `backend/se_pov_builder/services/handoff.py`, which is the source of truth).

The format belongs to this project and uses neutral names. Importers map it into their own
model. Nothing in this repository depends on, or contains code from, any internal platform.

## Top-level fields

| Field | Contents |
|-------|----------|
| `format`, `version` | Always `se-demo-pov-builder/handoff` and `1`. Breaking changes bump `version`. |
| `generated_at`, `generator` | Timestamp and app version. |
| `source` | `deal_id`, `deal_url` (link back to this deal), and `external_system` / `external_id` when the deal is linked to a system of record. |
| `data_classification` | `synthetic` for sample/fictional accounts, otherwise `customer`. Importers should refuse `customer` data unless they are approved to hold it. |
| `account` | Name, industry, region, size band, `is_synthetic`. |
| `opportunity` | Deal name, stage, summary, business drivers, target close, `technical_scope` (technology tags and labels). |
| `contacts` | Stakeholders with title, persona, influence, stance and an optional `email` (only when the SE entered one; needed to create POV contacts in LMDA). |
| `discovery` | Every answered question with answer, `confidence` (`confirmed`/`assumed`), who answered, the evidence source and an optional `evidence_quote` (the customer's exact words, when the answer came from a call transcript). `question_id` is a bank id, or `custom-<n>` for a question the SE added to this deal; `question` always holds the text. |
| `qualification` | Qualification checklist status: `confirmed`, `assumed` or `missing`. |
| `decision_criteria_notes` | The customer's answer about how options will be compared, if captured. |
| `challenges` | Requirements with pain point, optional `business_impact` (customer's numbers), priority (`must`/`should`/`could`), mapped capabilities (each with `verified`) and source question. |
| `pov` | Title, objectives, dates, status, portal resource group, `success_criteria` (measurable outcome, target, validation method, owner, status, `evidence`) and `activities` (milestones with owner, due date, status and dependencies). |
| `demo_plan` | Latest demo plan: version, title, duration, scenario titles, agenda. |
| `open_actions` | Open next actions with owner, due date, status and blocker. |
| `assumptions` | Unconfirmed answers and demo-plan assumptions. |
| `gaps` | Current gap analysis (severity and message). |

Fields added after the first release (`source`, `contacts[].email`,
`challenges[].business_impact`) are optional, so version stays `1`.

## Linking a system of record (opportunity → deal)

`POST /api/integrations/opportunities` creates or reuses the deal for an external
opportunity, keyed by `(system, external_id)`:

```json
{
  "system": "lmda",
  "external_id": "006...",
  "external_url": "https://lmda.example/opportunity/006...",
  "import_url_template": "https://lmda.example/opportunity/006.../scoping?seBuilderDeal={deal_url}",
  "account": {"name": "...", "industry": "...", "region": "...", "is_synthetic": false},
  "opportunity": {"name": "...", "stage": "...", "target_close": "2027-03-31", "technical_context": []}
}
```

Response: `{"deal_id": 3, "deal_url": "<SEPB_PUBLIC_URL>/#/deals/3", "created": true}`.
Re-linking updates the name, stage and URLs only; planning data entered here is kept.
The deal then shows **Send to LMDA**, which opens `import_url_template` with `{deal_url}`
filled in. URLs must be http(s). The endpoint is behind `SEPB_API_TOKEN` when set.

## Rules for importers

1. **`evidence[].simulated: true` is never a result.** It was produced with mock data
   (for example a mock-mode readiness check). Show it as such or drop it.
2. **Capabilities with `verified: false`** are community summaries, not confirmed product
   capabilities.
3. Treat `discovery[].confidence == "assumed"` and `qualification[].status != "confirmed"`
   as open questions, not facts.

## Mapping guidance (typical POV tracker concepts)

| POV tracker concept | Handoff source |
|---------------------|----------------|
| Customer / opportunity details | `account`, `opportunity` |
| Challenges / business pains | `challenges` (`pain_point`, `priority`) |
| Decision criteria | `decision_criteria_notes`, plus `must` challenges |
| Success criteria / use cases | `pov.success_criteria` (`title`, `measurable_outcome`, `validation_method`) |
| Activities / milestones | `pov.activities` |
| Customer contacts | `contacts` |
| Technical scope | `opportunity.technical_scope` |
| Assumptions / risks | `assumptions`, `gaps` |
