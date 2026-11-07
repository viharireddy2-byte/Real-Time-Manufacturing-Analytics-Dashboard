"""Run live KQL integration checks in an EMPTY dedicated fp_test_* database.

Requires an existing isolated KQL database, admin permissions, and --allow-write.
Never run in an operational database. Test rows are intentionally retained for
inspection; use a fresh test database per run. No test data enters Event Hubs.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from analytics.reconciliation import compare_groups


def run(cluster, database):
    if not database.startswith('fp_test_') or not database.replace('_', '').isalnum():
        raise ValueError('Only dedicated fp_test_* databases are accepted')
    from deploy_analytics import deploy
    from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
    from fabric_database import get_table_schemas
    checks = []
    with KustoClient(KustoConnectionStringBuilder.with_az_cli_authentication(cluster)) as client:
        existing = client.execute_mgmt(database, '.show tables')
        if len(existing.primary_results[0]):
            raise ValueError('Test database must be empty; use a fresh test database')
        for name, schema in get_table_schemas().items():
            client.execute_mgmt(database, f'.create table {name} {schema}')
        client.execute_mgmt(database, '.alter table events policy ingestiontime true')
        client.execute_mgmt(database, '.set-or-append assets <| datatable(Id:string,Name:string,SiteId:int,Type:string,SerialNumber:string,MaintenanceStatus:string)["A","Test Press",1,"Press","TEST","Done"]')
        client.execute_mgmt(database, '.set-or-append products <| datatable(Id:string,CategoryId:int,CategoryName:string,Name:string,Description:string,BrandName:string,Number:string,Status:string,Color:string,ListPrice:real,UnitCost:real,IsoCurrencyCode:string)["P",1,"Test","Test Product","Test","Synthetic","TEST","Active","Blue",10.0,5.0,"USD"]')
        # Four arrivals, three logical IDs, one duplicate, one missing dimension.
        row = lambda identity, asset, probability: f'"{identity}","{asset}","P",datetime(2026-01-01T00:10:00Z),"B",0.2,25.0,50.0,40.0,{probability}'
        values = ','.join([row('e1','A',0.01),row('e2','A',0.08),row('e2','A',0.08),row('e3','MISSING',0.03)])
        schema = 'Id:string,AssetId:string,ProductId:string,Timestamp:datetime,BatchId:string,Vibration:real,Temperature:real,Humidity:real,Speed:real,DefectProbability:real'
        client.execute_mgmt(database, f'.set-or-append events <| datatable({schema})[{values}]')
    deploy(cluster, database)
    with KustoClient(KustoConnectionStringBuilder.with_az_cli_authentication(cluster)) as client:
        def query(text):
            response = client.execute(database, text)
            table = response.primary_results[0]
            return [{column.column_name: row[column.column_name] for column in table.columns} for row in table]
        bounds = 'datetime(2026-01-01),datetime(2026-01-02)'
        result = query(f'ReconcileWindowV2({bounds})')[0]
        if (result['RawArrivals'], result['LogicalEvents'], result['DuplicateArrivals'], result['ConflictingIds']) != (4, 3, 1, 0):
            raise RuntimeError(f'Event reconciliation failed: {result}')
        checks.append('exact_duplicate_reconciliation')
        result = query(f'QualityEventsV2({bounds}) | summarize Critical=countif(RiskBand=="Critical"), Warning=countif(RiskBand=="Warning"), MissingSite=countif(isnull(SiteId))')[0]
        if (result['Critical'], result['Warning'], result['MissingSite']) != (1, 1, 1):
            raise RuntimeError(f'Risk semantics failed: {result}')
        checks.append('canonical_bands_and_left_join')
        raw = query('events | summarize Samples=count(), RiskSum=sum(DefectProbability), HighRiskSamples=countif(DefectProbability>=0.5) by Hour=bin(Timestamp,1h) | extend AverageRisk=RiskSum/Samples, HighRiskSamplePct=100.0*HighRiskSamples/Samples')
        aggregate = query(f'RiskTrend({bounds})')
        parity = compare_groups(raw, aggregate)
        if not parity['passed']:
            raise RuntimeError(f'Aggregate mismatch: {parity}')
        checks.append('materialized_view_grouped_parity')
        health = query('PipelineHealth(ago(1h),now())')[0]
        if health['Arrivals'] != 4:
            raise RuntimeError(f'Ingestion-time policy check failed: {health}')
        checks.append('ingestion_time_health')
    return {'scope': 'isolated Fabric KQL integration', 'database': database,
            'status': 'passed', 'checks': checks, 'run_utc': datetime.now(timezone.utc).isoformat()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cluster', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--allow-write', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_write:
        parser.error('--allow-write is required for an isolated test database')
    result = run(args.cluster, args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
