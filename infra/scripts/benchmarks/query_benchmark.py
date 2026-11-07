"""Measure equivalent raw vs aggregate arrival-risk queries, excluding result cache.

Queries use hour-aligned half-open UTC bounds. Generation and ingestion are separate.
The materialized view must be deployed before running this benchmark.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import statistics
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))
from analytics.reconciliation import compare_groups


def run(cluster, database, start, end, repetitions):
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder, ClientRequestProperties
    bounds = f'let Start=datetime({start}); let End=datetime({end});\n'
    raw = bounds + '''events | where Timestamp >= Start and Timestamp < End
| summarize Samples=count(), RiskSum=sum(DefectProbability), HighRiskSamples=countif(DefectProbability >= 0.5) by Hour=bin(Timestamp, 1h)
| extend AverageRisk=RiskSum / Samples, HighRiskSamplePct=100.0 * HighRiskSamples / Samples
| order by Hour asc'''
    aggregate = bounds + 'RiskTrend(Start, End) | order by Hour asc'
    timings = {'raw': [], 'aggregate': []}
    counts = {}
    pairs = []
    with KustoClient(KustoConnectionStringBuilder.with_az_cli_authentication(cluster)) as client:
        for iteration in range(repetitions + 1):
            # Alternate order to reduce systematic warm-cache bias.
            order = ['raw', 'aggregate'] if iteration % 2 == 0 else ['aggregate', 'raw']
            grouped = {}
            for name in order:
                props = ClientRequestProperties()
                props.set_option('query_results_cache_max_age', timedelta(0))
                began = time.perf_counter()
                response = client.execute(database, raw if name == 'raw' else aggregate, props)
                seconds = time.perf_counter() - began
                table = response.primary_results[0]
                grouped[name] = [{column: row[column] for column in ['Hour', 'Samples', 'RiskSum', 'HighRiskSamples', 'AverageRisk', 'HighRiskSamplePct']} for row in table]
                counts[name] = sum(int(row['Samples']) for row in grouped[name])
                if iteration:
                    timings[name].append(seconds)
            pairs.append(compare_groups(grouped['raw'], grouped['aggregate']))
    return {'cluster': cluster, 'database': database, 'start': start, 'end': end,
            'repetitions': repetitions, 'warmup_pairs': 1, 'cache': 'result cache disabled; engine cache may be warm',
            'arrival_sample_counts': counts, 'count_parity': counts['raw'] == counts['aggregate'],
            'grouped_parity': {'passed': all(p['passed'] for p in pairs), 'pairs': pairs},
            'timings_seconds': timings,
            'median_seconds': {k: statistics.median(v) for k, v in timings.items()}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ['cluster', 'database', 'start', 'end']:
        parser.add_argument('--' + field, required=True)
    parser.add_argument('--repetitions', type=int, default=7)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parsed = []
    for value in [args.start, args.end]:
        instant = datetime.fromisoformat(value)
        if instant.utcoffset() != timedelta(0) or (instant.minute, instant.second, instant.microsecond) != (0, 0, 0):
            parser.error('start/end must be UTC hour-aligned ISO8601 timestamps')
        parsed.append(instant)
    if parsed[0] >= parsed[1] or args.repetitions < 1:
        parser.error('start must precede end; repetitions must be positive')
    result = run(args.cluster, args.database, args.start, args.end, args.repetitions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['count_parity'] or not result['grouped_parity']['passed']:
        raise SystemExit('KPI mismatch: freeze ingestion, check view health, then rerun')
