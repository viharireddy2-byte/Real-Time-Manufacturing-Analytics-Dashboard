# Data source query instructions

Use `events` as the telemetry fact table; join `AssetId` to `assets.Id`, `ProductId` to `products.Id`, `assets.SiteId` to `sites.Id`, and `sites.LocationId` to `locations.Id`. Dimensions represent current state. Prefer left joins and expose missing keys.

Use UTC half-open time windows. State whether output counts raw arrivals or logical event identities. For canonical analytics after extension deployment:

```kql
QualityEventsV2(ago(1d), now())
| summarize Samples=count(), AverageTemperature=avg(Temperature), AverageSpeed=avg(Speed),
    AverageModeledRisk=avg(DefectProbability), CriticalSamples=countif(RiskBand == 'Critical') by AssetId, AssetName
```

For base deployment without extensions:

```kql
events
| where Timestamp >= ago(1d) and Timestamp < now()
| summarize arg_max(Timestamp, *) by Id
| join kind=leftouter (assets | project AssetId=Id, AssetName=Name) on AssetId
| summarize Samples=count(), AverageTemperature=avg(Temperature), AverageModeledRisk=avg(DefectProbability) by AssetId, AssetName
```

Do not translate telemetry counts into produced units or modeled probabilities into observed defect rates. Refer to `docs/DataContracts.md` for canonical metrics. Sensor units, historical prices, production schedules and observed outcomes require separately verified metadata.
