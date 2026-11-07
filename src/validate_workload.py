"""Verify manifest, hashes, row counts and event contracts before cloud replay."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from analytics.contracts import validate_event
from scale_data import FIELDS


def validate(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['schema_version'] != 1 or not manifest['files']:
        raise ValueError('Unsupported or empty manifest')
    dimensions = manifest.get('dimensions')
    if dimensions is not None:
        if {d['name'] for d in dimensions} != {'assets.csv','products.csv','sites.csv','locations.csv'} or len(dimensions) != 4:
            raise ValueError('Incomplete or repeated dimension snapshot metadata')
        for entry in dimensions:
            path = directory / entry['name']
            if path.is_symlink() or path.stat().st_size != entry['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError(f"{entry['name']}: dimension snapshot integrity mismatch")
    def keys(name):
        with (directory / name).open(newline='') as f:
            ids = [r['Id'] for r in csv.DictReader(f)]
        if not ids or len(ids) != len(set(ids)) or any(not x for x in ids):
            raise ValueError(f'{name}: dimension keys must be unique and nonempty')
        return set(ids)
    assets, products = keys('assets.csv'), keys('products.csv')
    sites, locations = keys('sites.csv'), keys('locations.csv')
    for name, field, valid in [('assets.csv', 'SiteId', sites), ('sites.csv', 'LocationId', locations)]:
        with (directory/name).open(newline='') as stream:
            if any(row[field] not in valid for row in csv.DictReader(stream)):
                raise ValueError(f'{name}: invalid {field} foreign key')
    total = 0
    seen = set()
    for entry in manifest['files']:
        name = entry['name']
        if Path(name).name != name or name in seen or not name.startswith('events-'):
            raise ValueError('Unsafe or repeated shard name')
        seen.add(name)
        path = directory / name
        if path.is_symlink() or path.stat().st_size != entry['bytes']:
            raise ValueError(f'{name}: size or file type mismatch')
        digest = hashlib.sha256()
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != entry['sha256']:
            raise ValueError(f'{name}: checksum mismatch')
        count = 0
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDS:
                raise ValueError(f'{name}: schema mismatch')
            for count, row in enumerate(reader, 1):
                errors = validate_event(row, assets, products)
                if errors:
                    raise ValueError(f'{name}:{count+1}: {errors}')
        if count != entry['rows']:
            raise ValueError(f'{name}: row count mismatch')
        total += count
    if total != manifest['rows']:
        raise ValueError('Manifest total mismatch')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = validate(args.directory)
    print(json.dumps({'valid': True, 'rows': result['rows'], 'shards': len(result['files'])}))
