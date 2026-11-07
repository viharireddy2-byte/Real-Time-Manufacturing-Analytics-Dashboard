"""Capture installed package versions without credentials, environment values or URLs."""
import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import platform


def capture():
    packages = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get('Name')
        if name:
            packages[name] = distribution.version
    return {'captured_utc': datetime.now(timezone.utc).isoformat(),
            'python': platform.python_version(), 'platform': platform.platform(),
            'packages': dict(sorted(packages.items(), key=lambda p:p[0].lower())),
            'scope': 'installed environment snapshot; not a hash-locked artifact manifest'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(capture(), indent=2)+'\n')
    print(args.output)
