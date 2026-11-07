"""Bounded-memory, reproducible CSV workload generation using existing entities.

Run from repository root: python src/scale_data.py --events 50000000 --output workload
A completed manifest is the commit marker. Incomplete directories are not ingestible.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from entities.asset import AssetType

FIELDS = ['Id', 'AssetId', 'ProductId', 'Timestamp', 'BatchId', 'Vibration',
          'Temperature', 'Humidity', 'Speed', 'DefectProbability']


def generate(output, count=10000, rows_per_file=100000, seed=36,
             start='2026-01-01T00:00:00+00:00', anomaly_rate=0.03,
             data_dir=None):
    if count < 1 or rows_per_file < 1 or not 0 <= anomaly_rate <= 1:
        raise ValueError('Positive counts and anomaly_rate in [0,1] required')
    origin = datetime.fromisoformat(start)
    if origin.utcoffset() is None:
        raise ValueError('start must include timezone')
    origin = origin.astimezone(timezone.utc)
    data_dir = Path(data_dir or Path(__file__).resolve().parents[1] / 'infra/data')
    with (data_dir / 'assets.csv').open(newline='') as f:
        assets = list(csv.DictReader(f))
    with (data_dir / 'products.csv').open(newline='') as f:
        products = list(csv.DictReader(f))
    if not assets or not products:
        raise ValueError('Assets and products must be nonempty')
    types = AssetType.get_types()
    for asset in assets:
        if asset['Type'] not in types:
            raise ValueError('Unknown asset type')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    # Preserve dimension snapshots so every workload has its joinable context.
    import shutil
    for name in ['assets', 'products', 'sites', 'locations']:
        shutil.copyfile(data_dir / f'{name}.csv', output / f'{name}.csv')
    dimensions = []
    for name in ["assets", "products", "sites", "locations"]:
        snapshot = output / f"{name}.csv"
        dimensions.append({"name": snapshot.name, "bytes": snapshot.stat().st_size,
                           "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()})
    state = random.getstate()
    random.seed(seed)
    files = []
    begin = time.perf_counter()
    try:
        for offset in range(0, count, rows_per_file):
            size = min(rows_per_file, count - offset)
            name = f'events-{offset // rows_per_file:06d}.csv'
            temporary = output / (name + '.partial')
            with temporary.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                for index in range(offset, offset + size):
                    asset = assets[index % len(assets)]
                    # One sample per asset per second; ordered across shards.
                    timestamp = origin + timedelta(seconds=index // len(assets))
                    event = types[asset['Type']].create_random_event(
                        asset_id=asset['Id'], product_id=random.choice(products)['Id'],
                        batch_id=f"BATCH_{asset['Id']}_{index // (len(assets)*3600):08d}",
                        timestamp=timestamp, anomaly=random.random() < anomaly_rate)
                    row = event.to_dict()
                    row['Id'] = str(uuid.uuid5(uuid.NAMESPACE_URL, f'factorypulse:{seed}:{start}:{index}'))
                    writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
            destination = output / name
            temporary.rename(destination)
            digest = hashlib.sha256()
            with destination.open('rb') as f:
                for chunk in iter(lambda: f.read(1024*1024), b''):
                    digest.update(chunk)
            files.append({'name': name, 'rows': size, 'bytes': destination.stat().st_size,
                          'sha256': digest.hexdigest()})
        elapsed = time.perf_counter() - begin
        manifest = {'schema_version': 1, 'rows': count, 'seed': seed,
                    'start': start, 'anomaly_rate': anomaly_rate,
                    'rows_per_file': rows_per_file, 'assets': len(assets),
                    'files': files, 'dimensions': dimensions, 'generation_seconds': elapsed,
                    'rows_per_second': count / elapsed}
        temp = output / 'manifest.json.partial'
        temp.write_text(json.dumps(manifest, indent=2) + '\n')
        temp.rename(output / 'manifest.json')
        return manifest
    finally:
        random.setstate(state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=10000)
    parser.add_argument('--rows-per-file', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=36)
    parser.add_argument('--start', default='2026-01-01T00:00:00+00:00')
    parser.add_argument('--anomaly-rate', type=float, default=0.03)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.output, args.events, args.rows_per_file,
                              args.seed, args.start, args.anomaly_rate), indent=2))
