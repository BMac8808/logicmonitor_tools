# Knowledge content

| File | Purpose |
|------|---------|
| `capabilities.yaml` | Capability catalogue used to map requirements. Every entry is `verified: false` until confirmed in official documentation. |
| `discovery_questions.yaml` | Context tags, qualification checklist and the deterministic question library. |
| `demo_scenarios.yaml` | Demo scenarios the demo builder chooses from. |
| `pov_template.yaml` | POV milestones, owners, offsets and dependencies. |

All files are validated together (ids must be unique, references must resolve). Run
`make validate-content` from the tool directory after any change.

**Do not fabricate product capabilities.** Describe capabilities in general terms, and
keep demo `demonstrates` lines limited to what you can actually show in your own demo
environment.
