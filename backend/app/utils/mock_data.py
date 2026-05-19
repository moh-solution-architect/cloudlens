"""
Deterministic mock data for demo mode. Seeded RNG ensures consistent results
across restarts so the UI looks stable during demos.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

from app.models import (
    AccountCost,
    CloudProvider,
    CostDataPoint,
    CostSummary,
    Recommendation,
    RecommendationType,
    RegionCost,
    ResourceMetric,
    ServiceCost,
    Severity,
)

_SEED = 42
_rng = random.Random(_SEED)


def _uid() -> str:
    return str(uuid.UUID(int=_rng.getrandbits(128)))


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

_AWS_INSTANCES = [
    ("i-0a1b2c3d4e5f", "prod-api-server-01", "m5.4xlarge", "us-east-1", 340.0),
    ("i-1b2c3d4e5f6a", "staging-worker-02", "c5.2xlarge", "us-west-2", 200.0),
    ("i-2c3d4e5f6a7b", "analytics-batch-03", "r5.2xlarge", "eu-west-1", 290.0),
    ("i-3d4e5f6a7b8c", "dev-sandbox-04", "t3.xlarge", "ap-southeast-1", 120.0),
]

_AWS_VOLUMES = [
    ("vol-0a1b2c3d4e5f6789", "orphaned-data-vol-01", 500, "us-east-1", 50.0),
    ("vol-1b2c3d4e5f67890a", "orphaned-logs-vol-02", 200, "us-west-2", 20.0),
    ("vol-2c3d4e5f678901b", "old-backup-vol-03", 1000, "eu-west-1", 100.0),
]

_AWS_RDS = [
    ("db-prod-analytics", "prod-analytics-db", "db.r5.4xlarge", "us-east-1", 960.0),
    ("db-staging-app", "staging-app-db", "db.m5.2xlarge", "us-west-2", 480.0),
]

_AZURE_INSTANCES = [
    ("vm-prod-web-01", "prod-web-server-01", "Standard_D8s_v3", "eastus", 280.0),
    ("vm-dev-test-02", "dev-test-server-02", "Standard_D4s_v3", "westeurope", 140.0),
]

_GCP_INSTANCES = [
    ("projects/my-proj/zones/us-central1-a/instances/gke-node-01", "gke-node-01", "n1-standard-8", "us-central1", 220.0),
    ("projects/my-proj/zones/europe-west1-b/instances/batch-worker-01", "batch-worker-01", "n1-standard-4", "europe-west1", 110.0),
]


def _idle_metrics(cpu_pct: float, lookback_days: int = 7) -> list[ResourceMetric]:
    return [
        ResourceMetric(name="avg_cpu_utilization", value=cpu_pct, unit="%", period_days=lookback_days),
        ResourceMetric(name="max_cpu_utilization", value=cpu_pct * 2.1, unit="%", period_days=lookback_days),
        ResourceMetric(name="network_in", value=_rng.uniform(0.1, 2.0), unit="MB/s", period_days=lookback_days),
    ]


def _rds_metrics() -> list[ResourceMetric]:
    return [
        ResourceMetric(name="avg_cpu_utilization", value=_rng.uniform(3.0, 18.0), unit="%", period_days=7),
        ResourceMetric(name="avg_connections", value=_rng.uniform(1.0, 4.0), unit="count", period_days=7),
        ResourceMetric(name="free_storage_gb", value=_rng.uniform(200.0, 800.0), unit="GB", period_days=7),
    ]


def build_recommendations() -> list[Recommendation]:
    recs: list[Recommendation] = []

    # AWS idle EC2
    for resource_id, name, instance_type, region, monthly_cost in _AWS_INSTANCES:
        cpu = _rng.uniform(0.4, 4.2)
        savings = monthly_cost * 0.95  # terminate saves ~95%
        recs.append(
            Recommendation(
                id=_uid(),
                provider=CloudProvider.AWS,
                account_id="123456789012",
                region=region,
                resource_id=resource_id,
                resource_name=name,
                resource_type=f"EC2 {instance_type}",
                recommendation_type=RecommendationType.IDLE_INSTANCE,
                severity=Severity.HIGH if monthly_cost > 250 else Severity.MEDIUM,
                current_monthly_cost=monthly_cost,
                projected_monthly_savings=round(savings, 2),
                savings_percentage=round((savings / monthly_cost) * 100, 2),
                description=(
                    f"Instance {name} ({instance_type}) has averaged {cpu:.1f}% CPU "
                    f"over the past 7 days — below the {5.0}% idle threshold."
                ),
                action="Terminate the instance or downsize to a t3.micro reserved instance.",
                metrics=_idle_metrics(cpu),
                tags={"env": "prod" if "prod" in name else "non-prod", "team": "platform"},
            )
        )

    # AWS unattached EBS
    for resource_id, name, size_gb, region, monthly_cost in _AWS_VOLUMES:
        recs.append(
            Recommendation(
                id=_uid(),
                provider=CloudProvider.AWS,
                account_id="123456789012",
                region=region,
                resource_id=resource_id,
                resource_name=name,
                resource_type=f"EBS gp3 {size_gb} GB",
                recommendation_type=RecommendationType.UNATTACHED_VOLUME,
                severity=Severity.MEDIUM,
                current_monthly_cost=monthly_cost,
                projected_monthly_savings=monthly_cost,
                savings_percentage=100.0,
                description=(
                    f"EBS volume {name} ({size_gb} GB) has been unattached for over 30 days."
                ),
                action="Create a snapshot for archival, then delete the volume.",
                metrics=[
                    ResourceMetric(name="days_unattached", value=_rng.randint(31, 120), unit="days", period_days=120),
                    ResourceMetric(name="size_gb", value=size_gb, unit="GB", period_days=1),
                ],
            )
        )

    # AWS oversized RDS
    for resource_id, name, instance_class, region, monthly_cost in _AWS_RDS:
        metrics = _rds_metrics()
        savings = monthly_cost * 0.5
        recs.append(
            Recommendation(
                id=_uid(),
                provider=CloudProvider.AWS,
                account_id="123456789012",
                region=region,
                resource_id=resource_id,
                resource_name=name,
                resource_type=f"RDS PostgreSQL {instance_class}",
                recommendation_type=RecommendationType.OVERSIZED_RDS,
                severity=Severity.HIGH if monthly_cost > 700 else Severity.MEDIUM,
                current_monthly_cost=monthly_cost,
                projected_monthly_savings=round(savings, 2),
                savings_percentage=round((savings / monthly_cost) * 100, 2),
                description=(
                    f"RDS instance {name} ({instance_class}) shows low utilization: "
                    f"avg CPU {metrics[0].value:.1f}%, avg connections {metrics[1].value:.1f}."
                ),
                action=f"Downsize to db.r5.xlarge and enable Aurora Serverless v2 for variable workloads.",
                metrics=metrics,
            )
        )

    # Azure idle VMs
    for resource_id, name, vm_size, region, monthly_cost in _AZURE_INSTANCES:
        cpu = _rng.uniform(0.5, 3.8)
        savings = monthly_cost * 0.92
        recs.append(
            Recommendation(
                id=_uid(),
                provider=CloudProvider.AZURE,
                account_id="sub-azure-prod-001",
                region=region,
                resource_id=resource_id,
                resource_name=name,
                resource_type=f"Azure VM {vm_size}",
                recommendation_type=RecommendationType.IDLE_INSTANCE,
                severity=Severity.MEDIUM,
                current_monthly_cost=monthly_cost,
                projected_monthly_savings=round(savings, 2),
                savings_percentage=round((savings / monthly_cost) * 100, 2),
                description=(
                    f"Azure VM {name} ({vm_size}) averaged {cpu:.1f}% CPU over 7 days."
                ),
                action="Deallocate the VM or resize to B-series burstable.",
                metrics=_idle_metrics(cpu),
            )
        )

    # GCP idle GCE
    for resource_id, name, machine_type, region, monthly_cost in _GCP_INSTANCES:
        cpu = _rng.uniform(0.6, 4.5)
        savings = monthly_cost * 0.90
        recs.append(
            Recommendation(
                id=_uid(),
                provider=CloudProvider.GCP,
                account_id="gcp-project-cloudlens-demo",
                region=region,
                resource_id=resource_id,
                resource_name=name,
                resource_type=f"GCE {machine_type}",
                recommendation_type=RecommendationType.IDLE_INSTANCE,
                severity=Severity.MEDIUM,
                current_monthly_cost=monthly_cost,
                projected_monthly_savings=round(savings, 2),
                savings_percentage=round((savings / monthly_cost) * 100, 2),
                description=(
                    f"GCE instance {name} ({machine_type}) averaged {cpu:.1f}% CPU over 7 days."
                ),
                action="Stop the instance or resize to e2-standard-2 with committed use discount.",
                metrics=_idle_metrics(cpu),
            )
        )

    return recs


# ---------------------------------------------------------------------------
# Cost Summary
# ---------------------------------------------------------------------------

def build_cost_summary() -> CostSummary:
    recs = build_recommendations()
    total_savings = sum(r.projected_monthly_savings for r in recs)

    by_service = [
        ServiceCost(service="Amazon EC2", provider=CloudProvider.AWS, amount=4820.0, period="2024-01"),
        ServiceCost(service="Amazon RDS", provider=CloudProvider.AWS, amount=2340.0, period="2024-01"),
        ServiceCost(service="Amazon S3", provider=CloudProvider.AWS, amount=890.0, period="2024-01"),
        ServiceCost(service="AWS Lambda", provider=CloudProvider.AWS, amount=120.0, period="2024-01"),
        ServiceCost(service="Azure Virtual Machines", provider=CloudProvider.AZURE, amount=1820.0, period="2024-01"),
        ServiceCost(service="Azure SQL Database", provider=CloudProvider.AZURE, amount=740.0, period="2024-01"),
        ServiceCost(service="Azure Blob Storage", provider=CloudProvider.AZURE, amount=310.0, period="2024-01"),
        ServiceCost(service="GCE Instances", provider=CloudProvider.GCP, amount=1340.0, period="2024-01"),
        ServiceCost(service="Cloud SQL", provider=CloudProvider.GCP, amount=620.0, period="2024-01"),
        ServiceCost(service="Cloud Storage", provider=CloudProvider.GCP, amount=190.0, period="2024-01"),
    ]

    by_region = [
        RegionCost(region="us-east-1", provider=CloudProvider.AWS, amount=4200.0, period="2024-01"),
        RegionCost(region="us-west-2", provider=CloudProvider.AWS, amount=2100.0, period="2024-01"),
        RegionCost(region="eu-west-1", provider=CloudProvider.AWS, amount=1870.0, period="2024-01"),
        RegionCost(region="ap-southeast-1", provider=CloudProvider.AWS, amount=600.0, period="2024-01"),
        RegionCost(region="eastus", provider=CloudProvider.AZURE, amount=1400.0, period="2024-01"),
        RegionCost(region="westeurope", provider=CloudProvider.AZURE, amount=1470.0, period="2024-01"),
        RegionCost(region="us-central1", provider=CloudProvider.GCP, amount=1120.0, period="2024-01"),
        RegionCost(region="europe-west1", provider=CloudProvider.GCP, amount=1030.0, period="2024-01"),
    ]

    by_account = [
        AccountCost(account_id="123456789012", account_name="AWS Production", provider=CloudProvider.AWS, amount=8770.0, period="2024-01"),
        AccountCost(account_id="sub-azure-prod-001", account_name="Azure Production", provider=CloudProvider.AZURE, amount=2870.0, period="2024-01"),
        AccountCost(account_id="gcp-project-cloudlens-demo", account_name="GCP Main Project", provider=CloudProvider.GCP, amount=2150.0, period="2024-01"),
    ]

    total_monthly = sum(a.amount for a in by_account)

    # 90-day daily trend
    base = datetime(2024, 1, 1)
    trend = []
    daily_base = total_monthly / 30
    for i in range(90):
        jitter = _rng.uniform(0.85, 1.15)
        trend.append(
            CostDataPoint(
                date=(base + timedelta(days=i)).strftime("%Y-%m-%d"),
                amount=round(daily_base * jitter, 2),
            )
        )

    return CostSummary(
        total_monthly_spend=total_monthly,
        total_projected_savings=round(total_savings, 2),
        savings_percentage=round((total_savings / total_monthly) * 100, 2),
        recommendation_count=len(recs),
        by_provider={
            "aws": 8770.0,
            "azure": 2870.0,
            "gcp": 2150.0,
        },
        by_service=by_service,
        by_region=by_region,
        by_account=by_account,
        trend=trend,
    )
