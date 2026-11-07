"""Event data model for manufacturing operations."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Event:
    """Represents a manufacturing event with sensor metrics."""

    Id: str
    AssetId: str
    ProductId: str
    BatchId: str
    Vibration: Decimal
    Temperature: Decimal
    Humidity: Decimal
    Speed: Decimal
    DefectProbability: Decimal
    Timestamp: datetime

    def to_dict(self) -> dict:
        """Convert event to dictionary representation."""
        return {
            "Id": self.Id,
            "AssetId": self.AssetId,
            "ProductId": self.ProductId,
            "Timestamp": self.Timestamp.isoformat(),
            "BatchId": self.BatchId,
            "Vibration": float(self.Vibration),
            "Temperature": float(self.Temperature),
            "Humidity": float(self.Humidity),
            "Speed": float(self.Speed),
            "DefectProbability": float(self.DefectProbability)
        }

    @staticmethod
    def get_table_schema() -> str:
        """Get KQL table schema for events."""
        return """(
            Id: string,
            AssetId: string,
            ProductId: string,
            Timestamp: datetime,
            BatchId: string,
            Vibration: real,
            Temperature: real,
            Humidity: real,
            Speed: real,
            DefectProbability: real
        )"""
