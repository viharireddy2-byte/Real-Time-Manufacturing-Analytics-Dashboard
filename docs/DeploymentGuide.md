# Deployment and teardown

## Prerequisites

Use Python 3.11/3.12, Azure CLI, Azure Developer CLI satisfying `azure.yaml`, Bicep, and PowerShell 7 (`pwsh`, including on Linux). The azd hooks invoke PowerShell helpers. A VS Code dev container is provided.

The deploying user needs Azure resource creation permission and permission to assign RBAC roles. The Fabric tenant must allow workspace creation and the relevant workloads; the user must be able to assign the workspace to a supported Fabric capacity. Data Agent setup additionally depends on the tenant's supported Data Agent features. The interactive path uses Azure CLI credentials; do not assume every module supports unattended identities without tenant testing.

The default Bicep capacity SKU is F2. It is a starting configuration, not evidence that F2 supports a 50M workload or a particular latency. Provisioning and capacity usage incur charges.

## Configure a local checkout

Extract the repository ZIP, open its root directory, and run:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
az login
azd auth login
azd env new factorypulse-dev
azd env set EXISTING_EVENT_HUB_NAMESPACE_ID ""
azd env set EXISTING_FABRIC_CAPACITY_NAME ""
azd env set AZURE_TAGS '{}'
```

Set `FABRIC_ACTIVATOR_ALERTS_EMAIL` to the real, authorized alert mailbox using `azd env set`. This setting is required before Fabric deployment; there is no default destination mailbox. Select the intended subscription and region when azd prompts. The environment's values are consumed by `infra/main.parameters.json` and the deployment hooks.

To reuse infrastructure, set `EXISTING_EVENT_HUB_NAMESPACE_ID` to the full Event Hub namespace resource ID and/or `EXISTING_FABRIC_CAPACITY_NAME` to the capacity name instead of an empty string. Review cross-subscription permissions before using the existing namespace path.

```bash
azd up
```

`azure.yaml` provisions Bicep resources and calls `infra/scripts/fabric/deploy_fabric_rti.py`. The orchestrator creates/configures the workspace, administrators, Eventhouse, KQL database, historical data, Event Hub connection, dashboard, Eventstream, Activator, environment, and data-agent notebook. Check the entire log and resolve failed steps before declaring deployment complete.

## Add the BI query layer

Obtain the Eventhouse query URI and database name from the deployed Fabric database. Pass those actual values as `--cluster` and `--database`:

```bash
python infra/scripts/fabric/deploy_analytics.py --help
```

The script applies `src/analytics/kql/*.kql` in sequence. It is deliberately separate from `azd up` so analytics can be rolled out after base resources are healthy. It requires KQL database administration permissions. The hourly view uses asynchronous backfill; the deployer waits up to 30 minutes before applying dependent functions. On timeout inspect `.show operations` and rerun after completion. Backfill can be expensive; create it before bulk replay when possible. The ingestion-time policy affects future ingestion only. Existing events may have null ingestion times.

The original dashboard JSON remains unchanged. Run `python infra/scripts/fabric/deploy_bi_extensions.py --help` and pass the deployed cluster URI, database name, workspace ID, database item ID, and the intended dashboard title. The wrapper generates the enhanced JSON, deploys all KQL definitions, then creates/updates the dashboard. Using the existing title preserves both original pages and adds the quality-risk/health page; a new title creates a separate dashboard. The cluster query URI, database name and Fabric database item ID are distinct values—use their actual deployed values.

Normal deployment now preserves populated tables. `FACTORYPULSE_SAMPLE_DATA_MODE=skip` bypasses sample loading. The original replacement path remains available only with mode `replace` and `FACTORYPULSE_ALLOW_SAMPLE_REPLACE=true`, for disposable sample environments.

## Live simulation and scale replay

From repository root:

```bash
python src/simulator/event_simulator.py --interval 2 --max-runtime 300
python src/scale_data.py --events 10000 --output workload/smoke
python src/validate_workload.py workload/smoke
```

For replay, export `AZURE_EVENT_HUB_NAMESPACE_HOSTNAME` and `AZURE_EVENT_HUB_NAME` from the deployed environment into the shell. Unlike the interactive simulator, the replay CLI does not automatically load azd values. Then:

```bash
python src/replay_workload.py workload/smoke
```

Replay checkpoints after acknowledged batches and resumes by default. `--no-checkpoint` preserves intentional full replay behavior. Replay publishes events only; confirm that the workload's dimension snapshots match the dimensions already loaded into Eventhouse. Default workloads use the shipped dimensions. Preserve generated workload files until reconciliation is complete. Never modify shards while validation/replay is running.

## Acceptance checks

1. In Fabric, confirm all items exist and the Eventstream source and destinations are healthy.
2. Generate a short live run, then query recent rows and compare asset/product keys to dimensions.
3. Switch one asset into anomaly mode; verify dashboard changes and authorized alert delivery.
4. Execute the KQL functions over the known workload time range and reconcile exact counts with the manifest. Use raw arrival totals for replay transport counts and deduplicated IDs for logical events.
5. Confirm the Data Agent can answer a documented example question with appropriate permissions.
6. Run a fixed workload with ingestion paused before comparing raw and aggregate query results.

Two runnable acceptance tools are included:

- `validate_tenant.py`: pass `--cluster`, an empty `--database` whose name starts with `fp_test_`, `--allow-write`, and `--output`. It creates fixture tables/rows and verifies the deployed KQL, duplicates, risk bands, missing dimensions, aggregate parity and ingestion-time health. Test data remains in that isolated database for inspection.
- `probe_pipeline.py`: pass `--cluster`, `--database`, `--namespace`, `--hub`, and `--output`. It sends one fresh synthetic record and polls Eventhouse for visibility. It may exercise configured alert rules.

A manually dispatched `Tenant validation` GitHub Actions workflow supports isolated KQL checks with OIDC. Configure the `fabric-validation` environment variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID`, and grant the test identity the required database permissions. No tenant credentials are embedded in the repository. These cloud checks have not been executed in this offline environment.

## Cleanup

```bash
azd down
```

The predown hook invokes Fabric cleanup before Azure teardown. Review the target environment and resource IDs first. Verify Fabric items were removed and any deliberately reused capacity or Event Hub namespace still exists. Do not assume an interrupted cleanup completed; inspect both Azure and Fabric. See [operations](Operations.md).

## Upload to GitHub

Create an empty repository named `factorypulse-manufacturing-bi`. In this extracted folder, initialize Git, add the files, commit, add your repository URL as `origin`, and push `main`. Keep LICENSE and NOTICE. No account-specific GitHub URL is embedded in deployment scripts.
