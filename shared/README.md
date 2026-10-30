# shared/

Empty on purpose.

Code moves here only when a **second tool actually needs it**. Copying "just in case"
creates coupling and maintenance cost without benefit.

When the time comes:

```
shared/
└── python/
    └── <package_name>/
        ├── pyproject.toml
        ├── src/<package_name>/
        └── tests/
```

- Move the code together with its tests.
- Keep packages small and free of application concerns (no web framework, no database).
- Update every consuming tool in the same pull request, and add `shared/python/<package>/**`
  to those tools' CI path filters.

**First likely candidate:** the integration adapter contracts in
`tools/se-demo-pov-builder/backend/se_pov_builder/adapters/base.py`. They only depend on
the Python standard library, so moving them later is straightforward.
