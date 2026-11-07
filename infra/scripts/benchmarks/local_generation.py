"""Measure local generator throughput and Linux process peak RSS in isolation."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def measure(count):
    program = '''import json, resource, tempfile
from pathlib import Path
from scale_data import generate
with tempfile.TemporaryDirectory() as tmp:
    result = generate(Path(tmp)/'workload', COUNT, 10000)
    print(json.dumps({'events': result['rows'], 'seconds': result['generation_seconds'],
        'rows_per_second': result['rows_per_second'],
        'csv_bytes': sum(f['bytes'] for f in result['files']),
        'shards': len(result['files']),
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))
'''.replace('COUNT', str(count))
    env = dict(os.environ, PYTHONPATH=str(ROOT/'src'))
    output = subprocess.check_output([sys.executable, '-c', program], env=env, text=True)
    return json.loads(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--counts', nargs='+', type=int, default=[10000, 100000])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'scope': 'local synthetic CSV generation only; not cloud ingestion or queries',
              'platform': platform.platform(), 'python': platform.python_version(),
              'cpu_count_visible': os.cpu_count(), 'rows_per_shard': 10000,
              'runs': [measure(n) for n in args.counts]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
