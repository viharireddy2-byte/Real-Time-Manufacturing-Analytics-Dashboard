"""Event schema and foreign-key checks shared by validation and replay."""
from datetime import datetime
import math


def validate_event(row, asset_ids, product_ids):
    errors = []
    for name in ['Id', 'AssetId', 'ProductId', 'BatchId', 'Timestamp']:
        if not row.get(name):
            errors.append(f'{name}: required')
    if row.get('AssetId') not in asset_ids:
        errors.append('AssetId: unknown dimension key')
    if row.get('ProductId') not in product_ids:
        errors.append('ProductId: unknown dimension key')
    try:
        timestamp = datetime.fromisoformat(row.get('Timestamp', ''))
        if timestamp.utcoffset() is None:
            errors.append('Timestamp: timezone required')
    except (ValueError, TypeError):
        errors.append('Timestamp: invalid ISO8601')
    for name in ['Vibration', 'Temperature', 'Humidity', 'Speed', 'DefectProbability']:
        try:
            value = float(row[name])
            if not math.isfinite(value) or value < 0:
                errors.append(f'{name}: finite nonnegative value required')
            if name == 'DefectProbability' and value > 1:
                errors.append('DefectProbability: exceeds 1')
        except (KeyError, ValueError, TypeError):
            errors.append(f'{name}: numeric value required')
    return errors
