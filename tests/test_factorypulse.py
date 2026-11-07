"""Offline regression tests for scale, contracts, transport and replay boundaries."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import importlib.util
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from scale_data import generate
from validate_workload import validate
from replay_workload import replay
from analytics.contracts import validate_event
from simulator.event_hub_service import EventHubService


class FakeEvent:
    def __init__(self, body):
        self.body = body
        self.properties = {}


class FakeBatch:
    def __init__(self):
        self.records = []

    def add(self, event):
        if len(event.body) > 1000 or len(self.records) == 3:
            raise ValueError('batch limit')
        self.records.append(event)


class FakeProducer:
    def __init__(self):
        self.sent = []
        self.closed = False

    def create_batch(self, **kwargs):
        return FakeBatch()

    def send_batch(self, batch):
        self.sent.append(batch.records[:])

    def close(self):
        self.closed = True


def service(producer):
    return EventHubService('test', 'test', producer=producer, event_factory=FakeEvent)


class TransportTests(unittest.TestCase):
    def test_batch_rollover_and_acknowledged_counters(self):
        producer = FakeProducer()
        with service(producer) as sender:
            self.assertEqual(sender.send_events({'Id': str(i)} for i in range(8)), 8)
            self.assertEqual([len(b) for b in producer.sent], [3, 3, 2])
            self.assertEqual(sender.events_sent, 8)
            self.assertEqual(sender.batches_sent, 3)
        self.assertTrue(producer.closed)
        with self.assertRaises(RuntimeError):
            sender.send_event({'Id': 'closed'})

    def test_oversized_record_is_not_dropped(self):
        with service(FakeProducer()) as sender:
            with self.assertRaises(ValueError):
                sender.send_event({'Id': 'x'*1001})
            self.assertEqual(sender.events_sent, 0)

    def test_failure_does_not_increment_acknowledged_counter(self):
        producer = FakeProducer()
        with service(producer) as sender:
            with patch.object(producer, 'send_batch', side_effect=TimeoutError):
                with self.assertRaises(TimeoutError):
                    sender.send_event({'Id': '1'})
            self.assertEqual(sender.events_sent, 0)

    def test_shared_producer_serializes_asset_threads(self):
        producer = FakeProducer()
        with service(producer) as sender:
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(sender.send_event, ({'Id': str(i)} for i in range(40))))
            ids = [json.loads(e.body)['Id'] for b in producer.sent for e in b]
            self.assertEqual(len(set(ids)), 40)
            self.assertEqual(sender.events_sent, 40)


class WorkloadTests(unittest.TestCase):
    def test_reproducible_shards_and_replay_numeric_types(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a', Path(temp)/'b'
            first = generate(a, 17, 6)
            second = generate(b, 17, 6)
            self.assertEqual([f['rows'] for f in first['files']], [6, 6, 5])
            self.assertEqual(first['files'], second['files'])
            self.assertEqual(validate(a)['rows'], 17)
            producer = FakeProducer()
            with service(producer) as sender:
                result = replay(a, sender, first)
            self.assertEqual(result['acknowledged_events'], 17)
            event = json.loads(producer.sent[0][0].body)
            self.assertIsInstance(event['Temperature'], float)

    def test_corruption_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'data'
            generate(output, 4, 3)
            with (output/'events-000001.csv').open('a') as f:
                f.write('corrupt')
            with self.assertRaises(ValueError):
                validate(output)

    def test_missing_commit_marker_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                validate(temp)

    def test_no_overwrite_and_invalid_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):
                generate(temp, 2)
            for count, size in [(0, 1), (1, 0)]:
                with self.assertRaises(ValueError):
                    generate(Path(temp)/'new', count, size)

    def test_contract_rejects_nan_probability_and_bad_keys(self):
        row = {'Id': 'x', 'AssetId': 'missing', 'ProductId': 'P', 'BatchId': 'B',
               'Timestamp': '2026-01-01', 'Temperature': 'nan', 'Vibration': 1,
               'Humidity': 2, 'Speed': 3, 'DefectProbability': 1.5}
        errors = validate_event(row, {'A'}, {'P'})
        self.assertEqual(len(errors), 4)

    def test_manifest_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'data'
            generate(output, 2)
            path = output/'manifest.json'
            content = json.loads(path.read_text())
            content['files'][0]['name'] = '../outside.csv'
            path.write_text(json.dumps(content))
            with self.assertRaises(ValueError):
                validate(output)


class AnalyticsDeploymentTests(unittest.TestCase):
    @staticmethod
    def loader():
        path = Path(__file__).resolve().parents[1] / 'infra/scripts/fabric/deploy_analytics.py'
        spec = importlib.util.spec_from_file_location('deploy_analytics', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_completed_backfill_allows_dependent_definitions(self):
        module = self.loader()
        client = SimpleNamespace(execute_mgmt=lambda *_: SimpleNamespace(primary_results=[[{'State': 'Completed'}]]))
        module.wait_for_operation(client, 'db', '00000000-0000-0000-0000-000000000001')

    def test_failed_backfill_stops_deployment(self):
        module = self.loader()
        client = SimpleNamespace(execute_mgmt=lambda *_: SimpleNamespace(primary_results=[[{'State': 'Failed'}]]))
        with self.assertRaises(RuntimeError):
            module.wait_for_operation(client, 'db', '00000000-0000-0000-0000-000000000001')

    def test_operation_id_is_not_interpolated_unvalidated(self):
        module = self.loader()
        with self.assertRaises(ValueError):
            module.wait_for_operation(None, 'db', 'not-a-guid')


if __name__ == '__main__':
    unittest.main()
