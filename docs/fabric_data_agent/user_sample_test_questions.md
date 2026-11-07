# Data-agent acceptance scenarios

Run these questions against the deployed data and inspect the generated KQL. No numeric answers are hardcoded because workloads and time ranges vary.

| Question | Acceptance criteria |
|---|---|
| Show sensor baselines by asset over the last day | Explicit UTC window, sample counts, mean/spread, verified units or units left unspecified |
| Which assets have the most critical-risk samples? | Canonical >0.05 band, explicit denominator, event-ID deduplication or duplicate caveat |
| How does risk vary by site? | Current dimension joins, missing keys exposed, no silently dropped observations |
| What is our production volume? | Explain that samples do not establish produced-unit counts; offer telemetry volume |
| What is our actual defect rate? | Explain probability versus observed outcome; show modeled risk only |
| What is our OEE or realized financial benefit? | Explain missing production schedules, outcomes and actual financial transactions |
| Are events duplicated or conflicting? | Exact bounded ID reconciliation, clear event-time bounds |
| Is ingestion healthy? | Arrival-time window, null-ingestion caveat and distinction between historical age and live latency |
| Which equipment will fail next week? | Do not claim prediction from unvalidated heuristic scores; offer descriptive risk indicators |
| Compare hourly raw and aggregate risk | Hour-aligned boundaries, same arrival semantics and grouped value comparison |

Use an isolated test environment for fixture-based checks. Store observed tenant results outside the source tree unless reviewed for public disclosure.
