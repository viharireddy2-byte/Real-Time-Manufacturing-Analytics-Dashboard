"""Deploy additive KQL and enhanced dashboard after base provisioning."""
import argparse
import json
from pathlib import Path
from build_analytics_assets import build
from deploy_analytics import deploy


def deploy_extensions(cluster, database, workspace_id, database_item_id, dashboard_title):
    dashboard_path = build()
    results = deploy(cluster, database)
    from fabric_auth import authenticate_workspace
    from fabric_real_time_dashboard import setup_real_time_dashboard
    client = authenticate_workspace(workspace_id)
    if client is None:
        raise RuntimeError('Workspace authentication failed')
    result = setup_real_time_dashboard(
        workspace_client=client, workspace_id=workspace_id,
        dashboard_title=dashboard_title, rti_dashboard_file_path=str(dashboard_path),
        cluster_uri=cluster, eventhouse_database_id=database_item_id)
    return {'analytics': results, 'dashboard_id': result['id'], 'dashboard_title': dashboard_title}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ['cluster', 'database', 'workspace-id', 'database-item-id', 'dashboard-title']:
        parser.add_argument('--'+arg, required=True)
    args = parser.parse_args()
    print(json.dumps(deploy_extensions(args.cluster, args.database, args.workspace_id,
                                      args.database_item_id, args.dashboard_title), indent=2))
