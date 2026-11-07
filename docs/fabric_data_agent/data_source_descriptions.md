# Manufacturing telemetry sources

The repository supplies synthetic manufacturing sensor data and dimensions for a fictional camping-equipment facility. Query deployed tables for current counts, available periods and names.

- `events`: event ID, event timestamp, asset/product/batch keys, vibration, temperature, humidity, speed and modeled defect probability.
- `assets`: current asset identity, type, site and maintenance-status attributes.
- `sites` and `locations`: current facility and geographic context.
- `products`: current catalog, category, price and unit-cost attributes.

Samples are not produced units. Probabilities are model outputs, not observed defects. Current prices are not historical transactions. Unit metadata and actual production outcomes require domain validation. Canonical risk and reconciliation functions are documented in docs/DataContracts.md.
