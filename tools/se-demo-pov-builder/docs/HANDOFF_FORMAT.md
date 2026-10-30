# Handoff format (`se-demo-pov-builder/handoff`, version 1)

This app is the **planning front end**. When an engagement moves into a POV tracker or SE
platform (for example LogicMonitor's internal LMDA), export a handoff package instead of
re-typing discovery:

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
| `data_classification` | `synthetic` for sample/fictional accounts, otherwise `customer`. Importers should refuse `customer` data unless they are approved to hold it. |
| `account` | Name, industry, region, size band, `is_synthetic`. |
| `opportunity` | Deal name, stage, summary, business drivers, target close, `technical_scope` (technology tags and labels). |
| `contacts` | Stakeholders with title, persona, influence and stance. No email addresses are collected. |
| `discovery` | Every answered question with answer, `confidence` (`confirmed`/`assumed`), who answered and the evidence source. |
| `qualification` | Qualification checklist status: `confirmed`, `assumed` or `missing`. |
| `decision_criteria_notes` | The customer's answer about how options will be compared, if captured. |
| `challenges` | Requirements with pain point, priority (`must`/`should`/`could`), mapped capabilities (each with `verified`) and source question. |
| `pov` | Title, objectives, dates, status, portal resource group, `success_criteria` (measurable outcome, target, validation method, owner, status, `evidence`) and `activities` (milestones with owner, due date, status and dependencies). |
| `demo_plan` | Latest demo plan: version, title, duration, scenario titles, agenda. |
| `open_actions` | Open next actions with owner, due date, status and blocker. |
| `assumptions` | Unconfirmed answers and demo-plan assumptions. |
| `gaps` | Current gap analysis (severity and message). |

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
