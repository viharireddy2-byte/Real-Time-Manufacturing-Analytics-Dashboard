# Troubleshooting

- **Import failure:** activate the Python environment and install requirements.txt. Offline smoke tests need only standard-library modules; cloud SDKs are imported on cloud use.
- **Azure authentication failure:** run `az login`, confirm subscription and tenant, then check actual role assignments. A successful login does not grant Fabric administration rights.
- **azd hook cannot find pwsh:** install PowerShell 7, including on Linux. Hooks invoke the retained PowerShell helpers.
- **Missing alert recipient:** set FABRIC_ACTIVATOR_ALERTS_EMAIL to the authorized destination before Fabric provisioning.
- **Empty dashboard:** confirm deployed database, event-time filter, Eventstream destination and actual ingestion. Reproducible scale workloads can be outside the default recent-time filter.
- **Null ingestion time:** policy applies prospectively; redeploying it does not give old records ingestion timestamps.
- **Duplicate counts:** raw aggregates count arrivals. Use EventsWindow for event-ID deduplication, and review retry/replay history.
- **Slow historical view creation:** check backfill status and capacity; create analytics before large replay when possible.
- **Generator output exists:** choose a new directory. It deliberately refuses overwrite/resume to preserve completed evidence.

See [deployment](DeploymentGuide.md), [operations](Operations.md), and [metric contracts](DataContracts.md) for exact behavior.
