"""Replay validated CSV shards, optionally resuming from durable SDK batch offsets."""
import argparse
from contextlib import nullcontext
import csv
from itertools import islice
import json
import os
from pathlib import Path
import time
from analytics.checkpoint import atomic_json, load_checkpoint, replay_lock
from simulator.event_hub_service import EventHubService
from validate_workload import validate


def replay(directory, service, manifest, *, checkpoint=None):
    """Retain the three-argument API; checkpointing is additive and opt-in here.

    CLI enables checkpointing by default. A failed send or a crash between broker
    acknowledgement and local fsync can duplicate the last uncheckpointed batch.
    Stable IDs and downstream logical-event reconciliation remain required.
    """
    destination = {'namespace': service.fully_qualified_namespace, 'hub': service.event_hub_name}
    lock = replay_lock(checkpoint) if checkpoint else nullcontext()
    with lock:
        state = load_checkpoint(checkpoint, manifest, destination) if checkpoint else {'confirmed_rows': 0}
        initial = state['confirmed_rows']
        skipped = initial
        started = time.perf_counter()
        batches_before = service.batches_sent

        def acknowledged(count):
            state['confirmed_rows'] += count
            if checkpoint:
                atomic_json(checkpoint, state)

        for entry in manifest['files']:
            if skipped >= entry['rows']:
                skipped -= entry['rows']
                continue
            with (Path(directory) / entry['name']).open(newline='') as stream:
                reader = islice(csv.DictReader(stream), skipped, None)
                skipped = 0

                def records():
                    for row in reader:
                        for name in ['Vibration', 'Temperature', 'Humidity', 'Speed', 'DefectProbability']:
                            row[name] = float(row[name])
                        yield row
                service.send_events(records(), on_batch_sent=acknowledged)
        # Empty no-op resume still writes valid state if checkpoint was requested.
        if checkpoint:
            atomic_json(checkpoint, state)
        elapsed = time.perf_counter() - started
        sent = state['confirmed_rows'] - initial
        return {'acknowledged_events': sent, 'previously_confirmed_events': initial,
                'total_confirmed_events': state['confirmed_rows'], 'send_seconds': elapsed,
                'events_per_second': sent / elapsed if elapsed else 0,
                'sdk_batches': service.batches_sent - batches_before}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--no-checkpoint', action='store_true', help='Legacy replay from beginning')
    args = parser.parse_args()
    if args.no_checkpoint and args.checkpoint:
        parser.error('--no-checkpoint and --checkpoint are mutually exclusive')
    manifest = validate(args.directory)
    checkpoint = None if args.no_checkpoint else args.checkpoint or args.directory / 'replay.checkpoint.json'
    with EventHubService(os.environ['AZURE_EVENT_HUB_NAMESPACE_HOSTNAME'],
                         os.environ['AZURE_EVENT_HUB_NAME']) as service:
        print(json.dumps(replay(args.directory, service, manifest, checkpoint=checkpoint), indent=2))
