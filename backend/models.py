"""
CloudLens — Pydantic models for the entire application.
All domain types are defined here to ensure consistent
validation and serialisation across the API.
"""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime


# ── Enumerations ──────────────────────────────────────────────────────────────

class CloudProvider(str, Enum):
    AWS   = "aws"
    AZURE = "azure"
    GCP   = "gcp"


class ResourceType(str, Enum):
    EC2_INSTANCE   = "ec2_instance"
    VM_INSTANCE    = "vm_instance"
    EBS_VOLUME     = "ebs_volume"
    MANAGED_DISK   = "managed_disk"
    RDS_INSTANCE   = "rds_instance"
    CLOUD_SQL      = "cloud_sql"
    S3_BUCKET      = "s3_bucket"
    BLOB_STORAGE   = "blob_storage"
    IDLE_RESOURCE  = "idle_resource"


class Severity(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class RecommendationType(str, Enum):
    TERMINATE        = "terminate"
    RIGHTSIZE        = "rightsize"
    DELETE           = "delete"
    RESERVE          = "reserve"
    STORAGE_TIER     = "storage_tier"


# ── Cost data ─────────────────────────────────────────────────────────────────

class ServiceCost(BaseModel):
    service:  str
    cost:     float = Field(..., ge=0, description="USD cost for the period")
    region:   str
    account:  str
    provider: CloudProvider


class DailySpend(BaseModel):
    date:  str   # ISO-8601 date string
    spend: float = Field(..., ge=0)


class CostSummary(BaseModel):
    provider:        CloudProvider
    total_spend:     float
    period_days:     int
    by_service:      list[ServiceCost]
    daily_trend:     list[DailySpend]
    currency:        str = "USD"


# ── Resource health ───────────────────────────────────────────────────────────

class ResourceMetric(BaseModel):
    name:  str
    value: float
    unit:  str


class Resource(BaseModel):
    resource_id:   str
    resource_name: str
    resource_type: ResourceType
    provider:      CloudProvider
    region:        str
    account:       str
    monthly_cost:  float
    metrics:       list[ResourceMetric] = []
    tags:          dict[str, str]       = {}
    created_at:    str | None           = None


# ── Recommendations ───────────────────────────────────────────────────────────

class Recommendation(BaseModel):
    recommendation_id:   str
    resource:            Resource
    recommendation_type: RecommendationType
    severity:            Severity
    title:               str
    description:         str
    monthly_savings:     float = Field(..., ge=0)
    annual_savings:      float = Field(..., ge=0)
    effort:              str   = Field(..., description="low | medium | high")
    confidence:          float = Field(..., ge=0.0, le=1.0)
    action_steps:        list[str] = []
    detected_at:         str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    def from_resource(
        cls,
        resource: Resource,
        rec_type: RecommendationType,
        severity: Severity,
        title: str,
        description: str,
        monthly_savings: float,
        effort: str,
        confidence: float,
        action_steps: list[str],
    ) -> "Recommendation":
        import uuid
        return cls(
            recommendation_id=str(uuid.uuid4()),
            resource=resource,
            recommendation_type=rec_type,
            severity=severity,
            title=title,
            description=description,
            monthly_savings=round(monthly_savings, 2),
            annual_savings=round(monthly_savings * 12, 2),
            effort=effort,
            confidence=confidence,
            action_steps=action_steps,
        )


# ── API response wrappers ─────────────────────────────────────────────────────

class SavingsSummary(BaseModel):
    total_monthly_savings: float
    total_annual_savings:  float
    recommendations_count: int
    by_provider:           dict[str, float]
    by_type:               dict[str, float]
    by_severity:           dict[str, int]


class DashboardResponse(BaseModel):
    generated_at:    str
    cost_summaries:  list[CostSummary]
    recommendations: list[Recommendation]
    savings_summary: SavingsSummary
    total_spend:     float


class HealthResponse(BaseModel):
    status:  str
    version: str
    providers_configured: list[str]
