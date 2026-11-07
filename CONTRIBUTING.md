# Contributing

Use Python 3.11 or 3.12. Keep event field names, dimension keys, and existing CLI arguments compatible. Add tests for changed transport or data-contract behavior and run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src infra/scripts
```

Changes to KQL, Bicep, or Fabric definitions need validation in a nonproduction tenant. Describe schema effects, query semantics, rollback steps, and measured evidence in the pull request. Never commit credentials or generated workload shards. Keep modeled quality risk distinct from observed defect outcomes.
