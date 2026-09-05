# Experiment outputs

- `runs/<run_id>/` contains immutable artifacts for one evaluation run.
- `experiment_history.csv` is an append-only comparison table.
- `latest/` is a generated convenience copy and is ignored by version control.

Each run stores metrics, predictions, failures, configuration, package versions, and a source-code fingerprint. Do not tune against the held-out `test` split.

