# Performance evidence and capacity planning

## Measured locally

The build environment ran isolated generator processes on Linux x86_64 with Python 3.12.14 and 9 visible CPUs. The generator is synchronous and does not use all visible CPUs. These single-run observations include synthetic event construction, deterministic UUIDs, CSV writes, fsync, and hashing. They exclude preflight validation, network transport, ingestion, and queries. They are not production SLOs or repeated statistical estimates.

| Events | Rows/shard | CSV shards | Elapsed | Throughput | CSV bytes | Process peak RSS |
|---:|---:|---:|---:|---:|---:|---:|
| 10,000 | 10,000 | 1 | 0.459 s | 21,808 rows/s | 1,266,276 | 13.50 MiB |
| 100,000 | 10,000 | 10 | 5.487 s | 18,224 rows/s | 12,662,307 | 13.56 MiB |

The larger run produced ten times the records with a 60 KiB peak-RSS difference. This supports bounded event-buffer usage at these sizes; it does not establish a 50M production result. The legacy DataFrame path was not benchmarked, so no fabricated before/after speedup is reported.

Reproduce on Linux:

```bash
python infra/scripts/benchmarks/local_generation.py --counts 10000 100000 --output benchmark-output/local.json
```

Raw evidence is in `docs/benchmarks/local-generation.json`. RSS uses Linux `resource.getrusage().ru_maxrss` in KiB; do not interpret its units the same way on macOS.

## Illustrative 50M sizing scenario — not executed results

Assume the shipped two assets, one event per asset per second, the same CSV schema, 100k rows per shard, sequential generation, and storage throughput at least as fast as this local run.

| Quantity | Planning estimate | Basis |
|---|---:|---|
| Workload | 50,000,000 events | CLI configuration |
| Event-time span | ~289.35 days | 50M / 2 samples/s / 86,400 |
| CSV shards | 500 | 50M / 100k |
| CSV storage | ~6.33 GB decimal | 126.62 measured bytes/row × 50M |
| Generator runtime | ~46 minutes | Linear extrapolation at 18,224 rows/s |
| Manifest footprint | O(500 entries) | One metadata record per shard |

This is a defensible synthetic planning scenario, not an execution claim. JSON transport bytes differ from CSV bytes; replay throughput depends on SDK/network performance, Event Hub quotas, Fabric capacity, batching, and ingestion latency. Provision sufficient free disk beyond the estimated CSV size. Choose a start date appropriate for your dashboard horizon; the default workload starts on 2026-01-01 and is intentionally reproducible rather than always recent.

Cloud query latency, Eventhouse compression, scanned bytes, compaction effects and ingestion throughput require tenant measurements; no such measurements are included. CSV shards do not imply Eventhouse partition pruning or a physical file layout guarantee.

## Cloud benchmark procedure

1. Deploy base infrastructure and additive analytics; confirm view backfill and ingestion-time policy.
2. Generate, validate, and replay a known workload. Record manifest, capacity SKU, Event Hub configuration, region, SDK versions, and any throttling.
3. Stop all producers and confirm event counts and view health are stable.
4. Run `python infra/scripts/benchmarks/query_benchmark.py --help`; pass the actual cluster URI, database, UTC hour-aligned start/end, and a JSON output path.
5. The runner alternates raw and aggregate query order, discards one warmup pair, disables query-result cache, records each duration, and compares hourly keys, exact counts and numeric risk values with explicit floating-point tolerances for every query pair. Engine cache may still be warm.
6. Inspect the grouped parity results and aggregate values as well as counts. Explain duplicate arrivals and floating-point tolerance. Repeat cold/warm runs separately if those distinctions matter.

The benchmark measures arrival-weighted risk over equivalent hour bounds. It does not compare deduplicated financial semantics against raw arrival semantics. Record medians and tail distributions from sufficient repetitions and report cloud timings only after actual execution. E2E latency requires fresh event timestamps; historical replay age is not a useful freshness SLO.
