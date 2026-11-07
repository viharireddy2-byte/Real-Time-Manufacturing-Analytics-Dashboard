"""Regression checks for safe deployment, recovery, policy and BI integration."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analytics.checkpoint import load_checkpoint, replay_lock
from analytics.policy import load_policy, band
from analytics.reconciliation import compare_groups
from audit_workload import audit
from replay_workload import replay
from scale_data import generate
from validate_workload import validate
from test_factorypulse import FakeProducer, service

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'infra/scripts/fabric'/f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ReplayRecoveryTests(unittest.TestCase):
    def test_mid_shard_failure_resumes_after_last_acknowledged_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, checkpoint = Path(tmp)/'data', Path(tmp)/'state.json'
            manifest = generate(data, 8, 10)
            producer = FakeProducer()
            original = producer.send_batch
            calls = 0
            def fail_second(batch):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise TimeoutError('transport interruption')
                original(batch)
            producer.send_batch = fail_second
            with service(producer) as sender:
                with self.assertRaises(TimeoutError):
                    replay(data, sender, manifest, checkpoint=checkpoint)
            self.assertEqual(json.loads(checkpoint.read_text())['confirmed_rows'], 3)
            self.assertFalse(Path(str(checkpoint)+'.lock').exists())
            resumed = FakeProducer()
            with service(resumed) as sender:
                result = replay(data, sender, manifest, checkpoint=checkpoint)
            self.assertEqual(result['previously_confirmed_events'], 3)
            self.assertEqual(result['acknowledged_events'], 5)
            self.assertEqual(result['total_confirmed_events'], 8)
            ids = [json.loads(event.body)['Id'] for batch in producer.sent+resumed.sent for event in batch]
            self.assertEqual(len(ids), len(set(ids)))

    def test_completed_resume_sends_no_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, checkpoint = Path(tmp)/'data', Path(tmp)/'state.json'
            manifest = generate(data, 7)
            with service(FakeProducer()) as sender:
                replay(data, sender, manifest, checkpoint=checkpoint)
            producer = FakeProducer()
            with service(producer) as sender:
                result = replay(data, sender, manifest, checkpoint=checkpoint)
            self.assertEqual(result['acknowledged_events'], 0)
            self.assertEqual(producer.sent, [])

    def test_checkpoint_destination_and_manifest_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, checkpoint = Path(tmp)/'data', Path(tmp)/'state.json'
            manifest = generate(data, 1)
            with service(FakeProducer()) as sender:
                replay(data, sender, manifest, checkpoint=checkpoint)
                destination = {'namespace': 'wrong', 'hub': 'test'}
                with self.assertRaises(ValueError):
                    load_checkpoint(checkpoint, manifest, destination)
                changed = dict(manifest, seed=999)
                with self.assertRaises(ValueError):
                    load_checkpoint(checkpoint, changed, {'namespace': 'test','hub':'test'})

    def test_concurrent_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            checkpoint = Path(tmp)/'state.json'
            with replay_lock(checkpoint):
                with self.assertRaises(FileExistsError):
                    with replay_lock(checkpoint):
                        self.fail('second writer entered')

    def test_crash_between_ack_and_checkpoint_preserves_replay_safety(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, checkpoint = Path(tmp)/'data', Path(tmp)/'state.json'
            manifest = generate(data, 2)
            producer = FakeProducer()
            with service(producer) as sender:
                with patch('replay_workload.atomic_json', side_effect=OSError('disk full')):
                    with self.assertRaises(OSError):
                        replay(data, sender, manifest, checkpoint=checkpoint)
            self.assertEqual(sum(map(len, producer.sent)), 2)
            self.assertFalse(checkpoint.exists())
            with service(FakeProducer()) as sender:
                result = replay(data, sender, manifest, checkpoint=checkpoint)
            self.assertEqual(result['acknowledged_events'], 2)


class InitializationTests(unittest.TestCase):
    def test_existing_data_never_requests_clear(self):
        initializer = module('sample_initialization')
        calls = []
        initializer.initialize_samples('cluster','db','data',loader=lambda **kw: calls.append(kw),is_events_empty=lambda:False)
        self.assertFalse(calls[0]['overwrite_existing'])
        self.assertFalse(calls[0]['refresh_event_dates'])

    def test_destructive_sample_replace_requires_explicit_opt_in(self):
        initializer = module('sample_initialization')
        with self.assertRaises(ValueError):
            initializer.initialize_samples('cluster','db','data',mode='replace',allow_replace=False,loader=lambda **kw: self.fail())
        result = initializer.initialize_samples('cluster','db','data',mode='replace',allow_replace=True,loader=lambda **kw:kw)
        self.assertTrue(result['overwrite_existing'])
        self.assertTrue(result['refresh_event_dates'])

    def test_failed_table_initialization_propagates_failure(self):
        initializer = module('sample_initialization')
        with self.assertRaises(RuntimeError):
            initializer.initialize_samples('c','d','data',loader=lambda **kw:{'events':{'success':False}},is_events_empty=lambda:False)

    def test_initial_timestamp_refresh_is_staged_without_clear(self):
        initializer = module('sample_initialization')
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data'
            generate(data, 2)
            source = (data/'events-000000.csv').read_bytes()
            (data/'events.csv').write_bytes(source)
            def refresh(path, _):
                refreshed=Path(path)/'refreshed.csv'
                refreshed.write_text('refreshed sample')
                return str(refreshed)
            def loader(**kw):
                self.assertEqual((Path(kw['data_path'])/'events.csv').read_text(),'refreshed sample')
                self.assertFalse(kw['refresh_event_dates'])
                self.assertFalse(kw['overwrite_existing'])
                return {'status':'initialized'}
            result=initializer.initialize_samples('c','d',data,loader=loader,is_events_empty=lambda:True,refresh=refresh)
            self.assertEqual(result['status'],'initialized')
            self.assertEqual((data/'events.csv').read_bytes(),source)


class PolicyAndDashboardTests(unittest.TestCase):
    def test_threshold_boundaries(self):
        self.assertEqual([band(x) for x in [0.02,0.0201,0.05,0.0501]], ['Normal','Warning','Warning','Critical'])
        for x in [float('nan'), -1, 2]:
            with self.assertRaises(ValueError):
                band(x)

    def test_build_preserves_legacy_pages_queries_and_tiles(self):
        builder=module('build_analytics_assets')
        source=ROOT/'src/definitions/realTimeDashboard/RealTimeDashboard.json'
        before=source.read_bytes()
        built=builder.build()
        first=built.read_bytes()
        builder.build()
        self.assertEqual(first,built.read_bytes())
        self.assertEqual(before,source.read_bytes())
        old,new=json.loads(before),json.loads(first)
        for key in ['tiles','queries','pages']:
            self.assertEqual(new[key][:len(old[key])],old[key])
        ids={q['id'] for q in new['queries']}
        self.assertTrue(all(t['queryRef']['queryId'] in ids for t in new['tiles']))
        self.assertEqual(len(new['pages']),len(old['pages'])+1)
        self.assertEqual(len(new['tiles']),len(old['tiles'])+4)

    def test_tenant_runner_refuses_operational_database_before_sdk_import(self):
        runner=module('validate_tenant')
        with self.assertRaises(ValueError):
            runner.run('cluster','production')


class ReconciliationTests(unittest.TestCase):
    def fixture(self):
        return [dict(Hour='00',Samples=10,HighRiskSamples=2,RiskSum=1.0,AverageRisk=0.1,HighRiskSamplePct=20.0),
                dict(Hour='01',Samples=20,HighRiskSamples=3,RiskSum=2.0,AverageRisk=0.1,HighRiskSamplePct=15.0)]

    def test_equal_totals_do_not_hide_wrong_hour_groups(self):
        left=self.fixture();right=[dict(r) for r in left]
        right[0]['Samples']=11;right[1]['Samples']=19
        self.assertFalse(compare_groups(left,right)['passed'])

    def test_risk_value_mismatch_is_rejected(self):
        left=self.fixture();right=[dict(r) for r in left]
        right[0]['RiskSum']=10.0
        self.assertFalse(compare_groups(left,right)['passed'])

    def test_small_floating_error_tolerated_and_missing_groups_rejected(self):
        left=self.fixture();right=[dict(r) for r in left]
        right[0]['RiskSum']+=1e-12
        self.assertTrue(compare_groups(left,right)['passed'])
        self.assertFalse(compare_groups(left,right[:1])['passed'])


class QuarantineTests(unittest.TestCase):
    def test_dimension_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';generate(data, 2)
            with (data/'products.csv').open('a') as stream:
                stream.write('\n')
            with self.assertRaises(ValueError):
                validate(data)

    def test_invalid_records_are_reported_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';generate(data, 2)
            shard=data/'events-000000.csv'
            text=shard.read_text().replace('A_1000','UNKNOWN')
            shard.write_text(text)
            before=shard.read_bytes()
            report=audit(data,Path(tmp)/'audit')
            self.assertEqual(report['quarantined_rows'],1)
            self.assertFalse(report['replay_allowed'])
            self.assertFalse(report['integrity_passed'])
            self.assertEqual(before,shard.read_bytes())


if __name__ == '__main__':
    unittest.main()
