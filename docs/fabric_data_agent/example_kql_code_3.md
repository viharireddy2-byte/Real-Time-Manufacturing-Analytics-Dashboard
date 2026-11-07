events 
| summarize 
    EventCount = count(),
    DateFrom = min(Timestamp),
    DateTo = max(Timestamp),
    UniqueAssets = dcount(AssetId),
    AvgSpeed = round(avg(Speed), 1),
    AvgTemp = round(avg(Temperature), 1),
    AvgDefectRate = round(avg(DefectProbability) * 100, 2)

