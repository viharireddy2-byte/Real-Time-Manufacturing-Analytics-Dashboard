"""Build additive dashboard and risk definitions from checked-in policy.

Idempotent: legacy dashboard bytes are left untouched. The enhanced definition
is separately deployable after KQL analytics, with stable object identifiers.
"""
import copy
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from analytics.policy import load_policy, policy_kql


def stable_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'factorypulse:v2:' + name))


def build():
    policy = load_policy()
    kql = ROOT / 'src/analytics/kql'
    (kql / '07_risk_policy_v2.kql').write_text(policy_kql(policy))
    (kql / '10_quality_hourly_arrivals_v2.kql').write_text(f""".create async ifnotexists materialized-view with (backfill=true) QualityHourlyArrivalsV2 on table events {{
    events
    | summarize Samples=count(), RiskSum=sum(DefectProbability), CriticalSamples=countif(DefectProbability > {policy['critical_probability']}),
        WarningSamples=countif(DefectProbability > {policy['warning_probability']} and DefectProbability <= {policy['critical_probability']}) by AssetId, Hour=bin(Timestamp, 1h)
}}
""")
    source = ROOT / 'src/definitions/realTimeDashboard/RealTimeDashboard.json'
    enhanced = json.loads(source.read_text())
    page_id = stable_id('quality-page')
    enhanced['pages'].append({'name': 'Quality Risk & Pipeline Health', 'id': page_id})
    data_source = copy.deepcopy(enhanced['queries'][0]['dataSource'])
    # Asset filtering is explicit in sample-risk tiles; health/reconciliation are pipeline-wide.
    base = "QualityEventsV2(_startTime, _endTime)\n| where isempty(tostring(['AssetFilter'])) or AssetName == tostring(['AssetFilter'])\n"
    definitions = [
        ('risk-summary', 'Quality risk by asset — logical samples', base + "| summarize LogicalSamples=count(), CriticalSamples=countif(RiskBand == 'Critical'), WarningSamples=countif(RiskBand == 'Warning'), AverageRisk=avg(DefectProbability), MissingCostSamples=countif(isnull(UnitCost)), MissingSiteSamples=countif(isnull(SiteId)) by AssetId, AssetName, SiteId\n| extend CriticalSamplePct=100.0 * CriticalSamples / LogicalSamples", 'Canonical warning >2%, critical >5%; current dimensions, duplicate event IDs removed within selected window.'),
        ('risk-trend', 'Hourly critical risk — logical samples', base + "| summarize LogicalSamples=count(), CriticalSamples=countif(RiskBand == 'Critical') by Hour=bin(Timestamp, 1h)\n| extend CriticalSamplePct=100.0 * CriticalSamples / LogicalSamples\n| order by Hour asc", 'Exact selected time range including partial hours; samples are observations, not produced units.'),
        ('health', 'Pipeline arrival health — all assets', 'PipelineHealth(_startTime, _endTime)', 'Arrival-time window; ignores asset selector. Historical event age is not live ingestion latency.'),
        ('reconcile', 'Exact event reconciliation — all assets', 'ReconcileWindowV2(_startTime, _endTime)', 'Event-time window; ignores asset selector. Conflicting IDs and duplicate arrivals are reported explicitly.')]
    for index, (name, title, query, description) in enumerate(definitions):
        query_id = stable_id(name + '-query')
        enhanced['queries'].append({'id': query_id, 'dataSource': data_source, 'text': query})
        tile = copy.deepcopy(enhanced['tiles'][0])
        tile.update({'id': stable_id(name + '-tile'), 'title': title, 'description': description,
                     'pageId': page_id, 'queryRef': {'kind': 'query', 'queryId': query_id},
                     'layout': {'x': 0, 'y': index*4, 'width': 12, 'height': 4}})
        if name == 'risk-trend':
            line_template = next(t for t in enhanced['tiles'] if t['visualType'] == 'line')
            tile['visualType'] = 'line'
            tile['visualOptions'] = copy.deepcopy(line_template['visualOptions'])
            tile['visualOptions'].update({'xColumn':'Hour','yColumns':['CriticalSamplePct'],'seriesColumns':[], 'xColumnTitle':'UTC hour'})
            if 'multipleYAxes' in tile['visualOptions']:
                tile['visualOptions']['multipleYAxes']['base']['label'] = 'Critical sample %'
        enhanced['tiles'].append(tile)
    destination = source.with_name('FactoryPulseEnhancedDashboard.json')
    destination.write_text(json.dumps(enhanced, indent=2) + '\n')
    return destination


if __name__ == '__main__':
    print(build())
