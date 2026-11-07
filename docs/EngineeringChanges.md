# Compatibility and extension design

The Python entities, per-asset simulator manager, pandas sample generator, legacy KQL functions, original dashboard definition, Fabric provisioning approach, Bicep modules and azd hooks remain available. New capabilities use the same dependency families and folder conventions. MIT attribution is retained.

| Extension | Integration | Compatibility |
|---|---|---|
| Safe sample initialization | Base deployer calls `initialize_samples` | Existing rows retained by default; legacy replacement requires explicit environment settings; loader API unchanged |
| Durable replay | Optional checkpoint keyword on `replay`; enabled by CLI | Three-argument Python calls retain replay-from-start behavior; `--no-checkpoint` enables that behavior in CLI |
| Batch acknowledgement hook | Optional `on_batch_sent` callback | Existing `send_event` and `send_events` calls remain valid |
| Canonical risk policy | JSON configuration, generated KQL policy and V2 functions | Existing thresholds and legacy functions unchanged; V2 bands are separately named |
| Enhanced dashboard | Separate generated JSON definition and extension deployer | Original two pages and all existing queries/tiles retained; one page/four tiles added |
| Quarantine audit | Separate read-only CLI | Sources unchanged; invalid workloads remain blocked from replay |
| Grouped query parity | Existing benchmark output extended | Existing totals/timing fields retained; every pair now checks hourly keys, counts and numeric measures |
| Tenant checks | Separate isolated-database runner and live-pipeline probe | No cloud writes in ordinary CI; explicit manual tenant validation |
| Snapshot integrity | Optional dimension metadata added to manifest version 1 | Older manifests still accepted; new manifests verify all dimension hashes |

## Delivery guarantees

Replay state is written with fsync and atomic replace after SDK batch acknowledgement. A process crash after broker acceptance but before checkpoint persistence can repeat the last unconfirmed batch. Exactly-once delivery is not claimed. The checkpoint binds workload contents and destination; a single-writer lock prevents concurrent writers using the same checkpoint.

Legacy aggregates count all arrivals. Canonical risk tiles use event-ID deduplication within their selected event-time window. Conflicting duplicate IDs are reported by exact reconciliation rather than silently treated as trustworthy. Current-state dimensions cannot represent historical price or location changes.

## Deployment contract

Normal redeployment does not clear sample/operational tables. Explicit `replace` mode preserves the original destructive sample-refresh capability for disposable environments. Initialization is not a multi-table transaction and should not race multiple deployers. KQL extensions deploy before the enhanced dashboard. Materialized-view policy versions must be migrated explicitly if thresholds change; `ifnotexists` does not alter an existing view.

Cloud checks and performance measurements are recorded only after actual tenant execution. The checked-in local measurements cover synthetic CSV generation. Lower-bound cloud SDK requirements remain compatible with the existing deployment; capture a tested dependency freeze for each deployed environment using the provided environment-capture command.
