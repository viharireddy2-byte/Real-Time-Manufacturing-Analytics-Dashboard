"""Apply additive FactoryPulse KQL definitions after base deployment.

Usage: python infra/scripts/fabric/deploy_analytics.py --cluster HTTPS_URI --database NAME
Requires database-admin permissions. Backfill may take significant time on 50M rows.
"""
import argparse
import json
from pathlib import Path
import re
import time
import uuid


def wait_for_operation(client, database, operation_id, timeout=1800):
    operation_id = str(uuid.UUID(str(operation_id)))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.execute_mgmt(database, f".show operations {operation_id}")
        for row in response.primary_results[0]:
            state = str(row["State"])
            if state == "Completed":
                return
            if state in {"Failed", "PartiallySucceeded", "Abandoned", "BadInput", "Canceled", "Cancelled"}:
                raise RuntimeError(f"Backfill {operation_id}: {state}")
        time.sleep(5)
    raise TimeoutError(f"Backfill still pending: {operation_id}; inspect .show operations before retrying")


def deploy(cluster, database):
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
    path = Path(__file__).resolve().parents[3] / 'src/analytics/kql'
    results = []
    with KustoClient(KustoConnectionStringBuilder.with_az_cli_authentication(cluster)) as client:
        # Enable ingestion time before creating any dependent materialized view.
        files = sorted(path.glob('*.kql'), key=lambda p: (p.name != '05_ingestion_time.kql', p.name))
        for file in files:
            response = client.execute_mgmt(database, file.read_text())
            for table in response.primary_results:
                if 'OperationId' in [column.column_name for column in table.columns]:
                    for row in table:
                        wait_for_operation(client, database, row['OperationId'])
            results.append({'definition': file.name, 'status': 'applied',
                            'result_tables': len(response.primary_results)})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'https://[A-Za-z0-9.-]+(?::443)?/?', args.cluster):
        parser.error('cluster must be an HTTPS service hostname')
    print(json.dumps(deploy(args.cluster, args.database), indent=2))
