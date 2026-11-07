# Operations and recovery

## Initialization

The default `FACTORYPULSE_SAMPLE_DATA_MODE=preserve` initializes empty tables and retains populated tables. Initial sample timestamps are refreshed in a private staging directory without executing table-clear logic. `skip` bypasses sample loading. For disposable sample environments only, `replace` plus `FACTORYPULSE_ALLOW_SAMPLE_REPLACE=true` enables the legacy destructive replacement path. Serialize deployers; initialization is not transactional across tables.

## Replay and recovery

The CLI writes `replay.checkpoint.json` inside the workload directory by default. Run the same replay command to resume. Progress is recorded per acknowledged SDK batch, including offsets within a shard. Checkpoints are bound to manifest contents and destination namespace/hub, and offsets are validated before use.

A crash between broker acknowledgement and checkpoint fsync can repeat a batch. Stable event IDs and downstream exact reconciliation are still required. A completed checkpoint makes a repeated invocation a no-op. Use `--no-checkpoint` for an intentional full replay or a separate `--checkpoint` path for an independently tracked run.

A `.lock` file prevents a second writer using the same checkpoint. After a hard process kill, a lock can remain. Confirm the recorded process and all replay workers are stopped before manually removing only that stale lock. Never remove a live writer's lock. Preserve checkpoint files until downstream reconciliation completes.

| Failure | Recovery |
|---|---|
| Interrupted generation | No manifest means incomplete workload. Preserve for diagnosis and generate into a new directory. |
| Invalid row or checksum | Run `python src/audit_workload.py workload/smoke --output benchmark-output/audit`. Review quarantine/report files and regenerate from corrected inputs. Sources are never repaired silently. |
| Mid-shard transport failure | Resume the same workload/checkpoint. Already committed offsets are skipped; ambiguous last-batch deliveries can repeat. |
| Checkpoint write failure | Fix disk/permissions before restarting. Last unpersisted acknowledged batch may repeat. |
| Manifest/destination mismatch | Select the correct checkpoint and destination. Do not edit offsets to bypass validation. |
| Oversized event | Investigate source data; the sender raises and retains earlier successful batches. |
| Delayed Fabric ingestion | Inspect Event Hubs, Eventstream, Kusto ingestion errors, quotas and capacity. Broker acknowledgement is not downstream persistence. |
| View backfill timeout | Inspect `.show operations`; rerun after completion. Do not drop the fact table. |

## Monitoring and reconciliation

Monitor ingress throttling, Eventstream connection health, Kusto ingestion failures, materialized-view backfill/health, capacity pressure and dashboard query latency. `PipelineHealth` uses arrival-time bounds and needs ingestion-time policy for newly ingested rows. Historical event age is not a live latency SLO.

`ReconcileWindowV2` reports exact logical IDs, duplicate arrivals and conflicting IDs. Compare expected logical counts to the workload manifest within matching event-time bounds. `query_benchmark.py` checks every hourly group and count/risk value with explicit floating tolerance, in addition to timing. Stop ingestion before fixed-data comparisons.

Dimension snapshots are checksummed by newly generated manifests. Older manifests retain compatibility without dimension checksum evidence. Files are trusted local inputs and must stay immutable during validation and replay. Quarantine output contains source telemetry and is ignored by Git when kept under benchmark-output/.

## Validation and rollback

Ordinary CI is offline. `validate_tenant.py` creates deterministic fixtures only in an empty `fp_test_*` database with explicit write opt-in. It tests KQL deployment, exact duplicates, risk boundaries, unmatched dimensions, materialized parity and ingestion times. `probe_pipeline.py` sends one fresh synthetic event through the live Event Hubs/Eventstream path; review alert recipients before use. These are runnable checks, not pre-recorded tenant evidence.

Deploy extensions in a nonproduction environment, verify the generated dashboard, then update the intended dashboard title. The original JSON remains available for rollback. Remove dependent new tiles before removing V2 functions/views. Never drop base event/dimension tables to roll back analytics.

Retention and hot-cache policies remain workload-specific. Establish them before bulk replay. Capture actual installed dependencies and platform metadata for each environment; do not infer reproducibility from lower-bound requirements alone. Review Azure and Fabric resources after teardown and preserve deliberately reused infrastructure.
