"""
Core recommendation engine.

Each detector is a pure function (resource_list → Recommendation list) so it
can be tested in isolation without cloud credentials or mocking the entire
provider SDK.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.models import (
    CloudProvider,
    Recommendation,
    RecommendationType,
    ResourceMetric,
    Severity,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Data transfer objects (provider-agnostic)
# ---------------------------------------------------------------------------


@dataclass
class RawInstance:
    provider: CloudProvider
    account_id: str
    region: str
    resource_id: str
    resource_name: str
    instance_type: str
    state: str
    monthly_cost: float
    avg_cpu_percent: float
    max_cpu_percent: float
    avg_network_mbps: float
    lookback_days: int
    tags: dict[str, str]


@dataclass
class RawVolume:
    provider: CloudProvider
    account_id: str
    region: str
    resource_id: str
    resource_name: str
    size_gb: int
    volume_type: str
    days_unattached: int
    monthly_cost: float
    tags: dict[str, str]


@dataclass
class RawDatabase:
    provider: CloudProvider
    account_id: str
    region: str
    resource_id: str
    resource_name: str
    instance_class: str
    engine: str
    avg_cpu_percent: float
    avg_connections: float
    free_storage_gb: float
    monthly_cost: float
    tags: dict[str, str]


# ---------------------------------------------------------------------------
# Severity computation
# ---------------------------------------------------------------------------


def _instance_severity(monthly_cost: float, cpu_pct: float) -> Severity:
    if monthly_cost >= 500 and cpu_pct < 2.0:
        return Severity.CRITICAL
    if monthly_cost >= 200 or cpu_pct < 1.0:
        return Severity.HIGH
    if monthly_cost >= 50:
        return Severity.MEDIUM
    return Severity.LOW


def _volume_severity(monthly_cost: float, days_unattached: int) -> Severity:
    if monthly_cost >= 100 and days_unattached >= 60:
        return Severity.HIGH
    if monthly_cost >= 50 or days_unattached >= 30:
        return Severity.MEDIUM
    return Severity.LOW


def _rds_severity(monthly_cost: float, avg_cpu: float) -> Severity:
    if monthly_cost >= 800 and avg_cpu < 10.0:
        return Severity.CRITICAL
    if monthly_cost >= 400 or avg_cpu < 10.0:
        return Severity.HIGH
    if monthly_cost >= 100:
        return Severity.MEDIUM
    return Severity.LOW


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def detect_idle_instances(
    instances: list[RawInstance],
    cpu_threshold: float | None = None,
) -> list[Recommendation]:
    """
    Flag instances whose average CPU is below *cpu_threshold* percent.

    Savings model: terminating an idle instance saves 95% of its monthly cost
    (5% retained for data transfer and snapshot storage).
    """
    threshold = cpu_threshold if cpu_threshold is not None else settings.idle_cpu_threshold_percent
    recommendations: list[Recommendation] = []

    for inst in instances:
        if inst.avg_cpu_percent >= threshold:
            continue
        if inst.state.lower() not in {"running", "active", "started"}:
            logger.debug("Skipping non-running instance %s (state=%s)", inst.resource_id, inst.state)
            continue

        savings_factor = 0.95
        savings = round(inst.monthly_cost * savings_factor, 2)

        rec = Recommendation(
            id=_stable_id(inst.provider, inst.resource_id, RecommendationType.IDLE_INSTANCE),
            provider=inst.provider,
            account_id=inst.account_id,
            region=inst.region,
            resource_id=inst.resource_id,
            resource_name=inst.resource_name,
            resource_type=inst.instance_type,
            recommendation_type=RecommendationType.IDLE_INSTANCE,
            severity=_instance_severity(inst.monthly_cost, inst.avg_cpu_percent),
            current_monthly_cost=inst.monthly_cost,
            projected_monthly_savings=savings,
            savings_percentage=round((savings / inst.monthly_cost) * 100, 2) if inst.monthly_cost else 0.0,
            description=(
                f"Instance {inst.resource_name!r} ({inst.instance_type}) averaged "
                f"{inst.avg_cpu_percent:.1f}% CPU over the past {inst.lookback_days} days, "
                f"below the {threshold}% idle threshold."
            ),
            action="Terminate the instance or resize to a smaller SKU. Consider a Reserved Instance if workload is confirmed low.",
            metrics=[
                ResourceMetric(name="avg_cpu_utilization", value=inst.avg_cpu_percent, unit="%", period_days=inst.lookback_days),
                ResourceMetric(name="max_cpu_utilization", value=inst.max_cpu_percent, unit="%", period_days=inst.lookback_days),
                ResourceMetric(name="avg_network_in", value=inst.avg_network_mbps, unit="MB/s", period_days=inst.lookback_days),
            ],
            tags=inst.tags,
        )
        recommendations.append(rec)
        logger.info(
            "Idle instance detected: %s | savings=$%.2f/mo",
            inst.resource_id,
            savings,
        )

    return recommendations


def detect_unattached_volumes(
    volumes: list[RawVolume],
    min_days_unattached: int = 30,
) -> list[Recommendation]:
    """
    Flag volumes that have been unattached longer than *min_days_unattached*.

    Savings: 100% (delete volume; optionally snapshot first).
    """
    recommendations: list[Recommendation] = []

    for vol in volumes:
        if vol.days_unattached < min_days_unattached:
            continue

        rec = Recommendation(
            id=_stable_id(vol.provider, vol.resource_id, RecommendationType.UNATTACHED_VOLUME),
            provider=vol.provider,
            account_id=vol.account_id,
            region=vol.region,
            resource_id=vol.resource_id,
            resource_name=vol.resource_name,
            resource_type=f"{vol.volume_type} {vol.size_gb} GB",
            recommendation_type=RecommendationType.UNATTACHED_VOLUME,
            severity=_volume_severity(vol.monthly_cost, vol.days_unattached),
            current_monthly_cost=vol.monthly_cost,
            projected_monthly_savings=vol.monthly_cost,
            savings_percentage=100.0,
            description=(
                f"Volume {vol.resource_name!r} ({vol.size_gb} GB {vol.volume_type}) "
                f"has been unattached for {vol.days_unattached} days."
            ),
            action="Take a final snapshot for archival, then delete the volume.",
            metrics=[
                ResourceMetric(name="days_unattached", value=vol.days_unattached, unit="days", period_days=vol.days_unattached),
                ResourceMetric(name="size_gb", value=vol.size_gb, unit="GB", period_days=1),
            ],
            tags=vol.tags,
        )
        recommendations.append(rec)
        logger.info(
            "Unattached volume detected: %s (%d days) | savings=$%.2f/mo",
            vol.resource_id,
            vol.days_unattached,
            vol.monthly_cost,
        )

    return recommendations


def detect_oversized_rds(
    databases: list[RawDatabase],
    cpu_threshold: float | None = None,
    connection_threshold: int | None = None,
) -> list[Recommendation]:
    """
    Flag RDS/Cloud SQL/Azure SQL instances with low CPU and connection count.

    Savings model: downsizing by one instance size class saves ~50%.
    """
    cpu_thresh = cpu_threshold if cpu_threshold is not None else settings.rds_cpu_threshold_percent
    conn_thresh = connection_threshold if connection_threshold is not None else settings.rds_connections_threshold
    recommendations: list[Recommendation] = []

    for db in databases:
        if db.avg_cpu_percent >= cpu_thresh and db.avg_connections >= conn_thresh:
            continue

        savings = round(db.monthly_cost * 0.50, 2)

        rec = Recommendation(
            id=_stable_id(db.provider, db.resource_id, RecommendationType.OVERSIZED_RDS),
            provider=db.provider,
            account_id=db.account_id,
            region=db.region,
            resource_id=db.resource_id,
            resource_name=db.resource_name,
            resource_type=f"{db.engine} {db.instance_class}",
            recommendation_type=RecommendationType.OVERSIZED_RDS,
            severity=_rds_severity(db.monthly_cost, db.avg_cpu_percent),
            current_monthly_cost=db.monthly_cost,
            projected_monthly_savings=savings,
            savings_percentage=50.0,
            description=(
                f"Database {db.resource_name!r} ({db.instance_class}) shows low utilisation: "
                f"avg CPU {db.avg_cpu_percent:.1f}%, avg connections {db.avg_connections:.1f}."
            ),
            action=(
                "Downsize to the next smaller instance class. "
                "For variable workloads consider Aurora Serverless v2 or Flexible Server."
            ),
            metrics=[
                ResourceMetric(name="avg_cpu_utilization", value=db.avg_cpu_percent, unit="%", period_days=7),
                ResourceMetric(name="avg_connections", value=db.avg_connections, unit="count", period_days=7),
                ResourceMetric(name="free_storage_gb", value=db.free_storage_gb, unit="GB", period_days=7),
            ],
            tags=db.tags,
        )
        recommendations.append(rec)
        logger.info(
            "Oversized RDS detected: %s | savings=$%.2f/mo",
            db.resource_id,
            savings,
        )

    return recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stable_id(provider: CloudProvider, resource_id: str, rec_type: RecommendationType) -> str:
    """Deterministic recommendation ID derived from provider + resource + type."""
    import hashlib

    raw = f"{provider.value}:{resource_id}:{rec_type.value}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def aggregate_recommendations(
    instances: list[RawInstance],
    volumes: list[RawVolume],
    databases: list[RawDatabase],
) -> list[Recommendation]:
    """Run all detectors and return the combined, deduplicated list."""
    results: list[Recommendation] = []
    results.extend(detect_idle_instances(instances))
    results.extend(detect_unattached_volumes(volumes))
    results.extend(detect_oversized_rds(databases))

    # Deduplicate by recommendation id (stable hash)
    seen: set[str] = set()
    unique: list[Recommendation] = []
    for r in results:
        if r.id not in seen:
            seen.add(r.id)
            unique.append(r)

    logger.info(
        "Recommendation engine: %d total, %d unique",
        len(results),
        len(unique),
    )
    return sorted(unique, key=lambda r: -r.projected_monthly_savings)
