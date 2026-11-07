"""Write bounded-memory invalid-row quarantine reports without changing source data."""
import argparse
import csv
import json
from pathlib import Path
from analytics.contracts import validate_event
from validate_workload import validate


def audit(directory, output):
    directory, output = Path(directory), Path(output)
    manifest = json.loads((directory/'manifest.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    def keys(name):
        with (directory/name).open(newline='') as stream:
            return {row['Id'] for row in csv.DictReader(stream)}
    assets, products = keys('assets.csv'), keys('products.csv')
    scanned = rejected = 0
    with (output/'quarantine.jsonl').open('w') as quarantine:
        for entry in manifest['files']:
            name = entry['name']
            if Path(name).name != name or not name.startswith('events-'):
                raise ValueError('Unsafe shard path')
            path = directory/name
            if path.is_symlink():
                raise ValueError('Symlink shards are not accepted')
            with path.open(newline='') as stream:
                for line, row in enumerate(csv.DictReader(stream), 2):
                    scanned += 1
                    errors = validate_event(row, assets, products)
                    if errors:
                        rejected += 1
                        quarantine.write(json.dumps({'shard': name, 'line': line, 'errors': errors, 'record': row})+'\n')
    integrity_error = None
    try:
        validate(directory)
    except (ValueError, KeyError, FileNotFoundError) as error:
        integrity_error = str(error)
    report = {'scanned_rows': scanned, 'quarantined_rows': rejected,
              'integrity_passed': integrity_error is None, 'integrity_error': integrity_error,
              'source_modified': False, 'replay_allowed': integrity_error is None and rejected == 0}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.directory, args.output)
    print(json.dumps(result, indent=2))
    if not result['replay_allowed']:
        raise SystemExit(1)
