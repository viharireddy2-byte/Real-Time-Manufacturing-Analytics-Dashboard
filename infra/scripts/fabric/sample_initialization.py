"""Non-destructive deployment initialization with explicit sample replacement mode."""
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone


def initialize_samples(cluster_uri, database_name, data_path, *, mode=None,
                       allow_replace=None, loader=None, is_events_empty=None,
                       refresh=None):
    """Keep existing rows by default; retain the legacy replacement path explicitly.

    The legacy load_data_to_fabric API is unchanged. Timestamp refresh happens in
    a private staging directory and is passed to the loader with refresh disabled
    so normal redeployments never execute its event-table clear branch.
    """
    def checked(result):
        if isinstance(result, dict):
            failures = [name for name, status in result.items() if isinstance(status, dict) and status.get('success') is False]
            if failures:
                raise RuntimeError(f'Sample initialization failed for tables: {failures}')
        return result

    if loader is None:
        from fabric_data_ingester import load_data_to_fabric
        loader = load_data_to_fabric
    mode = mode or os.getenv('FACTORYPULSE_SAMPLE_DATA_MODE', 'preserve')
    allow_replace = allow_replace if allow_replace is not None else os.getenv('FACTORYPULSE_ALLOW_SAMPLE_REPLACE') == 'true'
    if mode not in {'preserve', 'replace', 'skip'}:
        raise ValueError('FACTORYPULSE_SAMPLE_DATA_MODE must be preserve, replace or skip')
    if mode == 'skip':
        return {'mode': mode, 'status': 'skipped'}
    if mode == 'replace':
        if not allow_replace:
            raise ValueError('Sample replacement requires FACTORYPULSE_ALLOW_SAMPLE_REPLACE=true')
        return checked(loader(cluster_uri=cluster_uri, database_name=database_name,
                      data_path=data_path, refresh_event_dates=True, overwrite_existing=True))
    if is_events_empty is None:
        from fabric_data_ingester import create_kusto_client, check_table_empty
        with create_kusto_client(cluster_uri) as client:
            empty = check_table_empty(client, database_name, 'events')
    else:
        empty = is_events_empty()
    if not empty:
        return checked(loader(cluster_uri=cluster_uri, database_name=database_name,
                      data_path=data_path, refresh_event_dates=False, overwrite_existing=False))
    # First initialization: keep the sample horizon recent without clearing data.
    if refresh is None:
        from fabric_data_ingester import refresh_event_csv_timestamps
        refresh = refresh_event_csv_timestamps
    with tempfile.TemporaryDirectory(prefix='factorypulse-samples-') as temporary:
        stage = Path(temporary)
        for name in ['events', 'assets', 'products', 'sites', 'locations']:
            shutil.copyfile(Path(data_path) / f'{name}.csv', stage / f'{name}.csv')
        refreshed = refresh(str(stage), datetime.now(timezone.utc))
        shutil.copyfile(refreshed, stage / 'events.csv')
        result = loader(cluster_uri=cluster_uri, database_name=database_name,
                        data_path=str(stage), refresh_event_dates=False, overwrite_existing=False)
        return checked(result)
