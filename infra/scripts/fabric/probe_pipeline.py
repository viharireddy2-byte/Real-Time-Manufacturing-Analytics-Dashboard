"""Send one fresh synthetic event and verify Event Hubs -> Eventstream -> Eventhouse.

Requires a nonproduction environment with the live path already deployed. This
probe may trigger configured alerts. Run only with authorized alert recipients.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))


def probe(cluster, database, namespace, hub, timeout=180):
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
    from simulator.event_hub_service import EventHubService
    from entities.asset import AssetType
    with KustoClient(KustoConnectionStringBuilder.with_az_cli_authentication(cluster)) as client:
        asset_rows = client.execute(database, 'assets | take 1').primary_results[0]
        product_rows = client.execute(database, 'products | take 1').primary_results[0]
        if not len(asset_rows) or not len(product_rows):
            raise ValueError('Deploy dimensions before probing the live pipeline')
        asset, product = asset_rows[0], product_rows[0]
        event = AssetType.get_types()[asset['Type']].create_random_event(
            asset_id=asset['Id'], product_id=product['Id'], batch_id='PIPELINE_PROBE',
            timestamp=datetime.now(timezone.utc), anomaly=False).to_dict()
        event['Id'] = 'probe-' + uuid.uuid4().hex
        begin = time.perf_counter()
        with EventHubService(namespace, hub) as sender:
            sender.send_event(event)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # ID is generated internally from a fixed prefix and hexadecimal UUID.
            result = client.execute(database, f"events | where Id == '{event['Id']}' | summarize Arrivals=count()").primary_results[0][0]
            if result['Arrivals']:
                return {'status': 'passed', 'event_id': event['Id'], 'visible_arrivals': result['Arrivals'],
                        'observed_visibility_seconds': time.perf_counter()-begin,
                        'scope': 'single live pipeline probe; polling latency included, not an SLO'}
            time.sleep(3)
        raise TimeoutError(f"Probe not visible before timeout: {event['Id']}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ['cluster', 'database', 'namespace', 'hub']:
        parser.add_argument('--'+argument, required=True)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    result = probe(args.cluster, args.database, args.namespace, args.hub, args.timeout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
