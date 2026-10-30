# Personas

One YAML file per persona. The file is loaded at start-up (or via **Library → Reload
content** in the UI). To add a persona, copy an existing file, change `id`, and edit.

Required fields: `id`, `name`, `summary`, `coverage` (`required` | `recommended` |
`optional`), `typical_influence` (`high` | `medium` | `low`). Lists such as `objectives`,
`motivations`, `technical_concerns`, `typical_objections` (`objection` + `approach`),
`discovery_signals`, `engagement_approach`, `demo_focus` and `question_categories` are
optional but recommended.

- `coverage: required` personas are reported as a gap when no stakeholder on a deal has
  them.
- Persona ids are referenced by `knowledge/discovery_questions.yaml` (`personas`) and
  `knowledge/demo_scenarios.yaml` (`audience_talking_points`). Renaming an id breaks those
  references; `make validate-content` reports them.
- Keep content generic. Do not describe real people or customers.
