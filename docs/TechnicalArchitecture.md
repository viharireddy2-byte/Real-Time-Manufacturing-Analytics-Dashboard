# Architecture and data flow

FactoryPulse is a Microsoft Fabric operational BI system, not a custom web application. It uses the same Python entities, simulator manager, Azure SDK services, Bicep modules, azd hooks, Fabric JSON definitions, and configuration notebook as the underlying deployment pattern.

## Modules and ownership

| Module | Responsibility | State |
|---|---|---|
| `src/entities` | Typed asset/event records and sensor-risk generation | Python dataclasses and reference dictionaries |
| `src/simulator` | Per-asset workers, console commands, synchronous sends | Worker flags, per-asset counters, one locked producer |
| `src/sample_data.py` | Small historical dataset and dimensions | pandas DataFrames; legacy API retained |
| `src/scale_data.py` | Large historical workload | One event at a time; dimension lists and shard manifest |
| `src/validate_workload.py` | Shard integrity and event contracts | Streaming validation plus small dimension key sets |
| `src/replay_workload.py` | Byte-limited batch sends | One SDK batch; acknowledged counters |
| `src/definitions` | Deployable Fabric items | JSON definitions managed through Fabric REST APIs |
| `infra/scripts/fabric` | Ordered provisioning and cleanup | Resource IDs and API responses |
| `src/analytics/kql` | Query semantics and aggregate view | Eventhouse tables/functions/materialized view |

## Paths

Live events flow through Event Hubs → Eventstream → Eventhouse, with an Eventstream branch for Activator. Historical sample ingestion uses Kusto ingestion utilities. Scale replay uses Event Hubs so its transport exercises the live path. Real-Time Dashboard and Data Agent read the Eventhouse database.

The fact table `events` contains time-stamped asset/product observations. `assets` joins to `sites`, which joins to `locations`; `products` supplies product/category/cost attributes. These are current-state dimensions. Historical prices, slowly changing dimensions, and transactional production outcomes are absent; do not treat modeled cost exposure as financial actuals.

## Delivery and consistency

SDK acknowledgement confirms broker acceptance, not downstream Fabric persistence. Ambiguous transport failures can produce duplicate deliveries. There is no exactly-once claim. IDs remain stable during replay. `EventsWindow` deduplicates by Id within an explicitly filtered event-time window; conflicting duplicates with equal timestamps have unspecified tie selection. Raw aggregates count all arrivals. Materialized-view queries include the unmaterialized tail under Fabric's query semantics; monitor view health during backfill and heavy ingestion.

## Scale design

The original DataFrame historical generator remains for compatibility. The added generator avoids a full event list and DataFrame. At 50M rows with 100k rows per shard it writes 500 shards. Memory grows with dimensions and shard metadata rather than the event population. CSV was retained; no Parquet/Iceberg/Delta layer was introduced. Files are workload shards, not Eventhouse physical partitions. Storage layout, extents, compression, and cache placement remain managed by Eventhouse.

The sender holds one producer and serializes access because the original simulator shares it across worker threads. This favors correctness and connection reuse over unrestricted parallel sends. Batching is used by replay; the low-rate interactive simulator still sends one acknowledged event at a time. No new framework, queue, background buffer, database, or frontend state manager was added.

The materialized-view deployer uses asynchronous backfill and waits for its operation before creating the dependent trend function, following the [Microsoft KQL creation contract](https://learn.microsoft.com/en-us/kusto/management/materialized-views/materialized-view-create?view=microsoft-fabric).

## Operational extensions

The base deployer delegates sample initialization to a preservation-first wrapper; the loader's public API remains unchanged. Replay uses a single-writer checkpoint module and per-acknowledged-batch callbacks; restart resumes at a row offset bound to the workload and destination. New V2 policy/functions and a separate dashboard definition add canonical quality risk, exact duplicate/conflict reconciliation and pipeline health alongside the existing pages. Tenant checks remain separate from the offline CI path. See [operations](Operations.md) for recovery semantics and [compatibility](EngineeringChanges.md) for migration details.
