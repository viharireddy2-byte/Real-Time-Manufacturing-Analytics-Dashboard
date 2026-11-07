"""Compare grouped benchmark results; counts alone do not establish KPI parity."""
import math


def compare_groups(raw, aggregate, *, key='Hour', exact=('Samples', 'HighRiskSamples'),
                   approximate=('RiskSum', 'AverageRisk', 'HighRiskSamplePct'),
                   relative_tolerance=1e-9, absolute_tolerance=1e-9):
    def index(rows):
        indexed = {}
        for row in rows:
            group = str(row[key])
            if group in indexed:
                raise ValueError(f'Duplicate result group: {group}')
            indexed[group] = row
        return indexed
    left, right = index(raw), index(aggregate)
    differences = []
    for group in sorted(set(left) | set(right)):
        if group not in left or group not in right:
            differences.append({'group': group, 'field': key, 'reason': 'missing group'})
            continue
        for field in exact:
            if left[group][field] != right[group][field]:
                differences.append({'group': group, 'field': field, 'reason': 'exact mismatch'})
        for field in approximate:
            a, b = left[group][field], right[group][field]
            if a is None and b is None:
                continue
            if a is None or b is None or not math.isclose(float(a), float(b), rel_tol=relative_tolerance, abs_tol=absolute_tolerance):
                differences.append({'group': group, 'field': field, 'reason': 'numeric mismatch'})
    return {'passed': not differences, 'groups_compared': len(set(left) | set(right)),
            'differences': differences, 'relative_tolerance': relative_tolerance,
            'absolute_tolerance': absolute_tolerance}
