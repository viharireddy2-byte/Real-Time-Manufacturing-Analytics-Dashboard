"""Restore pinned sample telemetry and documentation images, verifying every byte.

Only manifest-listed assets are restored. Existing matching files are untouched;
existing mismatched files are rejected unless --replace is explicitly selected.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def restore(archive=None, replace=False):
    manifest = json.loads((ROOT/'infra/asset-manifest.json').read_text())
    if archive is None:
        repository, commit = manifest['source_repository'], manifest['source_commit']
        url = f'https://codeload.github.com/{repository}/zip/{commit}'
        with urllib.request.urlopen(url, timeout=120) as response:
            payload = response.read()
        archive = io.BytesIO(payload)
    restored = 0
    with zipfile.ZipFile(archive) as bundle:
        prefix = bundle.namelist()[0].split('/')[0] + '/'
        for entry in manifest['files']:
            relative = Path(entry['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Unsafe asset path')
            destination = ROOT/relative
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest() == entry['sha256']:
                    continue
                if not replace:
                    raise ValueError(f'Existing asset differs: {relative}')
            data = bundle.read(prefix + relative.as_posix())
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise ValueError(f'Pinned asset integrity mismatch: {relative}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name+'.partial')
            temporary.write_bytes(data)
            temporary.replace(destination)
            restored += 1
    return {'restored':restored,'verified_assets':len(manifest['files'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    print(json.dumps(restore(args.archive,args.replace)))
