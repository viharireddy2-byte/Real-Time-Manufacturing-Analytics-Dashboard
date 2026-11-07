# Manufacturing KQL examples

These queries support exploration of synthetic manufacturing telemetry. They do not establish measured downtime savings, uptime guarantees, prediction accuracy, production OEE or quality-standard compliance.

| Query | Purpose | Interpretation |
|---|---|---|
| manufacturing_data_overview.kql | Counts, date ranges and basic statistics | Telemetry observations; raw counts may include duplicate arrivals |
| baseline_statistics.kql | Per-asset sensor distributions | Descriptive statistics, not verified operating limits |
| business_intelligence_dashboard.kql | Illustrative product/operating scenarios | Scenario formulas use current product attributes; no actual financial transactions |
| predictive_maintenance_insights.kql | Rule-based maintenance prioritization | Heuristic score, not a validated failure predictor |
| production_efficiency_analysis.kql | Compare speed and modeled quality by shift | Legacy TotalProduction alias counts samples; efficiency score uses an assumed speed reference of 120 |
| quality_control_analytics.kql | Model-risk distributions and heuristic grades | Average probability is not an observed defective-unit rate |
| defect_analysis.kql | Risk-value percentiles and threshold counts | Threshold crossings describe modeled risk |
| dashboard_health_check.kql | Event recency and summary checks | A diagnostic query cannot guarantee dashboard availability |
| asset_performance_analysis.kql | Compare heuristic asset scores | Scores require domain calibration before operational use |
| service_order_enrichment_function.kql | Dimension enrichment helper | Deployed function is tabular; invoke directly or use joins, not a scalar extend assignment |
| create_service_order_payload_table.kql | Optional action payload schema | Deploy separately after reviewing its consumer requirements |

Legacy query aliases and formulas remain compatible. For new dashboard pages use the explicitly defined V2 API in `src/analytics/kql` and the [data contracts](../../../docs/DataContracts.md).
