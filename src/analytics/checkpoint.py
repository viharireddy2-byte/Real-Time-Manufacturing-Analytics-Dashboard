"""Single-writer, crash-consistent replay state using standard-library files."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def fingerprint(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


@contextmanager
def replay_lock(checkpoint):
    path = Path(str(checkpoint) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'pid': os.getpid(), 'checkpoint': str(checkpoint)}, stream)
        yield
    finally:
        path.unlink(missing_ok=True)


def load_checkpoint(path, manifest, destination):
    expected = {'schema_version': 1, 'manifest_sha256': fingerprint(manifest),
                'destination': destination, 'confirmed_rows': 0}
    path = Path(path)
    if not path.exists():
        return expected
    state = json.loads(path.read_text())
    for key in ['schema_version', 'manifest_sha256', 'destination']:
        if state.get(key) != expected[key]:
            raise ValueError(f'Checkpoint {key} mismatch; choose the correct workload and destination')
    rows = state.get('confirmed_rows')
    if isinstance(rows, bool) or not isinstance(rows, int) or not 0 <= rows <= manifest['rows']:
        raise ValueError('Invalid checkpoint offset')
    return state
