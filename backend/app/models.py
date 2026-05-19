from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class RecommendationType(str, Enum):
    IDLE_INSTANCE = "idle_instance"
    UNATTACHED_VOLUME = "unattached_volume"
    OVERSIZED_RDS = "oversized_rds"
    RIGHTSIZING = "rightsizing"
    RESERVED_INSTANCE = "reserved_instance"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceMetric(BaseModel):
    name: str
    value: float
    unit: str
    period_days: int


class Recommendation(BaseModel):
    id: str
    provider: CloudProvider
    account_id: str
    region: str
    resource_id: str
    resource_name: str
    resource_type: str
    recommendation_type: RecommendationType
    severity: Severity
    current_monthly_cost: float = Field(ge=0)
    projected_monthly_savings: float = Field(ge=0)
    savings_percentage: float = Field(ge=0, le=100)
    description: str
    action: str
    metrics: list[ResourceMetric] = []
    tags: dict[str, str] = {}
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = {}

    @field_validator("savings_percentage", mode="before")
    @classmethod
    def compute_savings_pct(cls, v: float, info: Any) -> float:
        if v:
            return v
        data = info.data
        current = data.get("current_monthly_cost", 0)
        if current > 0:
            savings = data.get("projected_monthly_savings", 0)
            return round((savings / current) * 100, 2)
        return 0.0


class CostDataPoint(BaseModel):
    date: str
    amount: float
    currency: str = "USD"


class ServiceCost(BaseModel):
    service: str
    provider: CloudProvider
    amount: float
    currency: str = "USD"
    period: str


class RegionCost(BaseModel):
    region: str
    provider: CloudProvider
    amount: float
    currency: str = "USD"
    period: str


class AccountCost(BaseModel):
    account_id: str
    account_name: str
    provider: CloudProvider
    amount: float
    currency: str = "USD"
    period: str


class CostSummary(BaseModel):
    total_monthly_spend: float
    total_projected_savings: float
    savings_percentage: float
    recommendation_count: int
    by_provider: dict[str, float]
    by_service: list[ServiceCost]
    by_region: list[RegionCost]
    by_account: list[AccountCost]
    trend: list[CostDataPoint]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class RecommendationSummary(BaseModel):
    total_recommendations: int
    total_projected_savings: float
    by_type: dict[str, int]
    by_severity: dict[str, int]
    by_provider: dict[str, int]
    recommendations: list[Recommendation]


class ExportRequest(BaseModel):
    include_providers: list[CloudProvider] = list(CloudProvider)
    include_types: list[RecommendationType] = list(RecommendationType)
    min_savings: float = 0.0
    format: Literal["pdf"] = "pdf"


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    providers: dict[str, bool]
