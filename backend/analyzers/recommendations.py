"""
CloudLens — Recommendation Engine.

Applies rule-based analysis to cloud resources and produces
ranked, actionable cost-optimisation recommendations.
Each rule is isolated, testable, and returns a typed Recommendation.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from models import (
    CloudProvider, RecommendationType, Recommendation,
    Resource, ResourceType, Severity,
)

logger = logging.getLogger(__name__)

# Thresholds — all configurable
IDLE_CPU_THRESHOLD      = 5.0    # %
IDLE_OBS_DAYS           = 7
RIGHTSIZE_CPU_THRESHOLD = 20.0   # %
MIN_SAVINGS_TO_REPORT   = 10.0   # USD / month


# ── Individual rules ──────────────────────────────────────────────────────────

def _rule_idle_instance(resource: Resource) -> Recommendation | None:
    """Terminate instances with average CPU < IDLE_CPU_THRESHOLD for 7+ days."""
    if resource.resource_type not in (ResourceType.EC2_INSTANCE, ResourceType.VM_INSTANCE):
        return None

    cpu_metric = next((m for m in resource.metrics if m.name == "avg_cpu_7d"), None)
    if cpu_metric is None or cpu_metric.value >= IDLE_CPU_THRESHOLD:
        return None

    savings = resource.monthly_cost * 0.95   # ~95% of cost recovered
    if savings < MIN_SAVINGS_TO_REPORT:
        return None

    provider_label = resource.provider.value.upper()
    res_label      = "EC2 instance" if resource.provider == CloudProvider.AWS else "VM"

    return Recommendation.from_resource(
        resource=resource,
        rec_type=RecommendationType.TERMINATE,
        severity=Severity.HIGH,
        title=f"Idle {provider_label} {res_label}: {resource.resource_name}",
        description=(
            f"{resource.resource_name} has averaged {cpu_metric.value:.1f}% CPU "
            f"over the last {IDLE_OBS_DAYS} days — well below the {IDLE_CPU_THRESHOLD}% "
            f"idle threshold. It is consuming ${resource.monthly_cost:.0f}/month "
            f"without providing value."
        ),
        monthly_savings=savings,
        effort="low",
        confidence=0.92,
        action_steps=[
            f"Verify no scheduled jobs run on {resource.resource_name}",
            "Create a final AMI/snapshot as backup",
            f"Terminate {resource.resource_id} via console or CLI",
            "Monitor CloudWatch for 48h to confirm no alerts",
        ],
    )


def _rule_unattached_volume(resource: Resource) -> Recommendation | None:
    """Delete EBS volumes / Managed Disks that are not attached to any instance."""
    if resource.resource_type not in (ResourceType.EBS_VOLUME, ResourceType.MANAGED_DISK):
        return None

    attached_metric = next((m for m in resource.metrics if m.name == "attached"), None)
    if attached_metric is None or int(attached_metric.value) != 0:
        return None

    savings = resource.monthly_cost  # 100% recovered

    return Recommendation.from_resource(
        resource=resource,
        rec_type=RecommendationType.DELETE,
        severity=Severity.MEDIUM,
        title=f"Unattached volume: {resource.resource_name}",
        description=(
            f"Volume {resource.resource_id} ({resource.resource_name}) has been "
            f"unattached for an extended period and costs ${resource.monthly_cost:.0f}/month."
        ),
        monthly_savings=savings,
        effort="low",
        confidence=0.98,
        action_steps=[
            f"Confirm volume data is not needed (check with {resource.tags.get('team', 'owner')})",
            "Create a final snapshot if archival is required",
            f"Delete volume {resource.resource_id}",
        ],
    )


def _rule_oversized_rds(resource: Resource) -> Recommendation | None:
    """Right-size RDS/CloudSQL instances with consistently low CPU and connection counts."""
    if resource.resource_type not in (ResourceType.RDS_INSTANCE, ResourceType.CLOUD_SQL):
        return None

    cpu_metric  = next((m for m in resource.metrics if m.name == "avg_cpu_7d"),         None)
    conn_metric = next((m for m in resource.metrics if m.name == "avg_connections_7d"), None)

    if cpu_metric is None or cpu_metric.value >= RIGHTSIZE_CPU_THRESHOLD:
        return None

    # If connections are low relative to instance size, it's a strong signal
    confidence = 0.80
    if conn_metric and conn_metric.value < 20:
        confidence = 0.91

    savings = resource.monthly_cost * 0.50  # downsize = ~50% cost reduction

    return Recommendation.from_resource(
        resource=resource,
        rec_type=RecommendationType.RIGHTSIZE,
        severity=Severity.HIGH,
        title=f"Oversized database: {resource.resource_name}",
        description=(
            f"{resource.resource_name} averages {cpu_metric.value:.1f}% CPU "
            f"with {conn_metric.value:.0f} connections — far below capacity. "
            f"Downsizing one instance class would save ~${savings:.0f}/month."
        ),
        monthly_savings=savings,
        effort="medium",
        confidence=confidence,
        action_steps=[
            "Take a final RDS snapshot before resizing",
            "Schedule a maintenance window (low-traffic period)",
            "Modify DB instance class down one tier (e.g., r5.4xlarge → r5.2xlarge)",
            "Monitor performance for 72h post-resize",
            "Resize again if performance is still acceptable",
        ],
    )


def _rule_reserve_steady_state(resource: Resource) -> Recommendation | None:
    """Recommend Reserved Instances for resources running > 90% of the month."""
    if resource.resource_type not in (ResourceType.EC2_INSTANCE, ResourceType.RDS_INSTANCE):
        return None

    # Idle check — don't recommend reserving idle resources
    cpu_metric = next((m for m in resource.metrics if m.name == "avg_cpu_7d"), None)
    if cpu_metric and cpu_metric.value < IDLE_CPU_THRESHOLD:
        return None

    # Only flag expensive resources
    if resource.monthly_cost < 200:
        return None

    savings = resource.monthly_cost * 0.35  # 1-yr RI ≈ 35% cheaper than on-demand

    return Recommendation.from_resource(
        resource=resource,
        rec_type=RecommendationType.RESERVE,
        severity=Severity.MEDIUM,
        title=f"Buy Reserved Instance: {resource.resource_name}",
        description=(
            f"{resource.resource_name} runs continuously at ${resource.monthly_cost:.0f}/month on-demand. "
            f"A 1-year Reserved Instance would save ~${savings:.0f}/month (35%)."
        ),
        monthly_savings=savings,
        effort="low",
        confidence=0.85,
        action_steps=[
            "Confirm resource runs 24/7 (check uptime metrics)",
            "Purchase 1-year No-Upfront Reserved Instance",
            "Apply RI to matching instance type and region",
        ],
    )


# ── Engine ────────────────────────────────────────────────────────────────────

_RULES: list[Callable[[Resource], Recommendation | None]] = [
    _rule_idle_instance,
    _rule_unattached_volume,
    _rule_oversized_rds,
    _rule_reserve_steady_state,
]


def generate_recommendations(resources: list[Resource]) -> list[Recommendation]:
    """
    Run all rules against every resource.
    Returns recommendations sorted by monthly_savings (highest first).
    """
    results: list[Recommendation] = []

    for resource in resources:
        for rule in _RULES:
            try:
                rec = rule(resource)
                if rec is not None:
                    results.append(rec)
                    logger.info(
                        "Recommendation generated",
                        extra={
                            "resource_id": resource.resource_id,
                            "type":        rec.recommendation_type,
                            "savings":     rec.monthly_savings,
                        },
                    )
            except Exception:
                logger.exception("Rule %s failed on %s", rule.__name__, resource.resource_id)

    results.sort(key=lambda r: r.monthly_savings, reverse=True)
    logger.info("Generated %d recommendations from %d resources", len(results), len(resources))
    return results


def build_savings_summary(recommendations: list[Recommendation]):
    """Aggregate recommendation data for the dashboard summary cards."""
    from models import SavingsSummary
    from collections import defaultdict

    by_provider: dict[str, float] = defaultdict(float)
    by_type:     dict[str, float] = defaultdict(float)
    by_severity: dict[str, int]   = defaultdict(int)

    for r in recommendations:
        by_provider[r.resource.provider.value] += r.monthly_savings
        by_type[r.recommendation_type.value]   += r.monthly_savings
        by_severity[r.severity.value]           += 1

    total_monthly = sum(r.monthly_savings for r in recommendations)

    return SavingsSummary(
        total_monthly_savings=round(total_monthly, 2),
        total_annual_savings=round(total_monthly * 12, 2),
        recommendations_count=len(recommendations),
        by_provider={k: round(v, 2) for k, v in by_provider.items()},
        by_type={k: round(v, 2) for k, v in by_type.items()},
        by_severity=dict(by_severity),
    )
