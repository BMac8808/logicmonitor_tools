# Workflows

One YAML file per workflow. Files are loaded in `order`, then by file name. Adding a file
adds a workflow to the application; no code change is needed.

```yaml
id: unique_id            # used in the API; never change after use
name: Display name
version: 1               # bump on every change
order: 10                # display order
description: ...
stages:
  - id: stage_id
    name: Stage name
    tasks:
      - key: task_key            # unique within the workflow
        title: What to do
        description: Optional detail
        owner_role: se           # se | customer | joint | account_executive | other text
        depends_on: [other_key]  # keys in this workflow; cycles are rejected
        evidence_required: false # true: task cannot be completed without an evidence note
    exit_criteria: [Optional human-readable checks]
```

Validate after editing: `make validate-content` (from the tool directory).
Existing workflow runs keep the tasks they were created with; edits affect new runs only.
