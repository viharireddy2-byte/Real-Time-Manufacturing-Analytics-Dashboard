# Database, event API, and KPI contracts

## Event payload

The event transport contract is JSON over Event Hubs. There is no custom HTTP API.

| Field | JSON / KQL type | Meaning |
|---|---|---|
| Id | string / string | Stable event identity used for replay deduplication |
| AssetId | string / string | Foreign key to assets.Id |
| ProductId | string / string | Foreign key to products.Id |
| Timestamp | ISO8601 string / datetime | Event time, timezone required by preflight |
| BatchId | string / string | Manufacturing simulation batch identifier |
| Vibration, Temperature, Humidity, Speed | number / real | Synthetic sensor measurements |
| DefectProbability | number / real | Modeled risk in [0,1]; not a defect observation |

Sensor units are not formally specified by the source entity model. Establish calibrated units and acceptable ranges with domain owners before ingesting physical equipment data. The validator checks nonnegative finite sensor values, required keys, timezone-aware timestamps, dimension references, probability bounds, headers, shard sizes, hashes, and row totals. It does not perform an unbounded in-memory duplicate-ID check; use KQL for full-dataset reconciliation.

Dimension schemas live in `infra/scripts/fabric/fabric_database.py`; the event model exposes `Event.get_table_schema()`. Existing lower-case table names remain unchanged: `events`, `assets`, `products`, `sites`, `locations`. Do not rename columns in CSV or JSON without updating mappings and dashboard definitions.

## Query API

All functions accept `Start:datetime` and `End:datetime` with half-open bounds `[Start, End)`. Use UTC and `Start < End`.

```kql
EventsWindow(datetime(2026-01-01), datetime(2026-01-02))
| summarize LogicalEvents=count()

SiteRisk(datetime(2026-01-01), datetime(2026-01-02))
| order by Hour asc

RiskTrend(datetime(2026-01-01), datetime(2026-01-02))
| order by Hour asc

PipelineHealth(ago(1h), now())
```

| Measure | Definition / caveat |
|---|---|
| Logical event count | Count of `EventsWindow` rows; latest timestamp per Id inside window |
| High-risk sample percentage | 100 × samples with probability ≥ 0.5 / sample count |
| Expected defects | Sum of modeled probabilities; assumes each sample represents one comparable trial |
| Expected cost exposure | Sum(probability × current product UnitCost); missing costs excluded and reported separately |
| Missing-site / missing-cost samples | Counts expose incomplete joins instead of silently hiding them |
| Average risk | Sum(probability) / sample count |
| Ingestion delay | ingestion_time − event Timestamp, in seconds; historical replay includes historical age |
| ApproxDistinctEvents | Approximate dcount of event IDs for operational monitoring, not exact reconciliation |

`SiteRisk` uses event-ID deduplication. `RiskTrend` uses `AssetHourlyArrivals` and deliberately counts duplicates as arrivals. Its bounds must be UTC hour boundaries for exact raw-query parity; partial-hour requests select whole precomputed bins. Existing dashboard queries are unchanged and can have different definitions—label each tile accordingly.

Expected defect counts are an experimental model output. Actual yield, scrap, availability, OEE, and realized cost savings require observed outcomes and production schedules. No such metrics are claimed.

## Python service API

`EventHubService(namespace, hub)` remains supported. `send_event(data)` synchronously sends one record. `send_events(iterable, partition_key=None)` splits a stream into SDK byte-limited batches and returns acknowledged event count. It raises on oversized records or send errors. A failure after some batches does not roll those batches back. `close()` is idempotent, context-manager use is recommended, and sends after close raise RuntimeError.

`generate(...)` requires a new output directory and writes a completion manifest only after all event shards are finalized. A failed generation directory must be removed or retained for diagnosis and a new directory chosen. Resume is not implemented. `validate(directory)` fails fast with the offending shard/row; validation does not repair or quarantine data silently.

## Canonical V2 API

`src/analytics/risk_policy.json` is the canonical policy source. `build_analytics_assets.py` generates `RiskPolicyV2` and the V2 hourly view from it. Current strict bands are **Normal ≤0.02**, **Warning >0.02 and ≤0.05**, and **Critical >0.05**. The existing >0.02 alert is an early-warning threshold; the existing ≥0.5 analytic threshold is a legacy extreme-risk measure. They remain compatible and are not interchangeable with critical-risk percentage.

- `QualityEventsV2(Start, End)` returns logical samples, current dimensions and a risk band.
- `QualitySiteSummaryV2(Start, End)` returns site-level logical sample counts and critical/warning counts. `RiskWeightedUnitCostIndex` is the average of probability × current UnitCost over samples with known cost. It is a model index, not realized loss.
- `QualityHourlyTrendV2(Start, End)` uses arrival-weighted aggregates and requires complete UTC-hour bounds. Duplicate arrivals count as samples.
- `ReconcileWindowV2(Start, End)` returns exact raw arrivals, logical events, duplicate arrivals and IDs with conflicting payloads. Exact distinct-payload aggregation can be costly on large windows.

The enhanced dashboard uses deduplicated raw-window queries for sample-risk tiles, including partial-hour ranges. Global health/reconciliation tiles explicitly ignore the asset selector. Missing dimensions remain visible. Legacy dashboard formulas are preserved and should be interpreted using their documented heuristic definitions.

`send_events` also accepts optional `on_batch_sent(count)`, invoked after each acknowledged batch. If checkpoint persistence fails, replay stops and the last acknowledged batch may repeat on restart. New generated manifests include dimension hashes; older manifests remain valid but lack that additional integrity evidence.
