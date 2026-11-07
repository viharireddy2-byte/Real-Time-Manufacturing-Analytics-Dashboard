"""Shared risk policy; legacy bands remain available without changing old tiles."""
import json
from pathlib import Path


def load_policy(path=None):
    policy = json.loads(Path(path or Path(__file__).with_name('risk_policy.json')).read_text())
    if policy.get('schema_version') != 1 or policy.get('comparison') != 'strictly_greater_than':
        raise ValueError('Unsupported risk policy')
    warning, critical, extreme = [policy[k] for k in ['warning_probability', 'critical_probability', 'legacy_extreme_probability']]
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in [warning, critical, extreme]):
        raise ValueError('Risk thresholds must be numeric')
    if not 0 <= warning < critical < extreme <= 1:
        raise ValueError('Risk thresholds must be ordered within [0,1]')
    return policy


def band(probability, policy=None):
    policy = policy or load_policy()
    if not 0 <= probability <= 1:
        raise ValueError('Probability must be finite and within [0,1]')
    if probability > policy['critical_probability']:
        return 'Critical'
    if probability > policy['warning_probability']:
        return 'Warning'
    return 'Normal'


def policy_kql(policy=None):
    policy = policy or load_policy()
    return f""".create-or-alter function with (folder='FactoryPulse/V2', docstring='Canonical sample risk bands, strict greater-than comparison.') RiskPolicyV2() {{
    datatable(WarningProbability:real, CriticalProbability:real, LegacyExtremeProbability:real)
    [{policy['warning_probability']}, {policy['critical_probability']}, {policy['legacy_extreme_probability']}]
}}
"""
