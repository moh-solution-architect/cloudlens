"""
CloudLens — Realistic mock data so the demo works without cloud credentials.
All figures are representative of real-world multi-cloud environments.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import random

from models import (
    CloudProvider, ResourceType, ServiceCost, DailySpend,
    CostSummary, Resource, ResourceMetric,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso(days_ago: int = 0) -> str:
    return (datetime.utcnow() - timedelta(days=days_ago)).isoformat()


def _daily_trend(base: float, days: int = 30) -> list[DailySpend]:
    random.seed(42)
    result = []
    for i in range(days, 0, -1):
        date  = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        noise = random.uniform(-0.08, 0.12)
        result.append(DailySpend(date=date, spend=round(base * (1 + noise), 2)))
    return result


# ── AWS mock data ─────────────────────────────────────────────────────────────

AWS_SERVICES: list[ServiceCost] = [
    ServiceCost(service="Amazon EC2",          cost=12_450.00, region="us-east-1",      account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="Amazon RDS",          cost=4_320.00,  region="us-east-1",      account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="Amazon S3",           cost=1_870.00,  region="us-west-2",      account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="AWS Lambda",          cost=320.00,    region="us-east-1",      account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="Amazon CloudFront",   cost=580.00,    region="global",         account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="Amazon EBS",          cost=2_100.00,  region="us-east-1",      account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="Amazon DynamoDB",     cost=760.00,    region="eu-west-1",      account="prod-account",    provider=CloudProvider.AWS),
    ServiceCost(service="Amazon EC2",          cost=3_200.00,  region="ap-southeast-1", account="dev-account",     provider=CloudProvider.AWS),
]

AWS_COST_SUMMARY = CostSummary(
    provider=CloudProvider.AWS,
    total_spend=sum(s.cost for s in AWS_SERVICES),
    period_days=30,
    by_service=AWS_SERVICES,
    daily_trend=_daily_trend(850, 30),
)


# ── Azure mock data ───────────────────────────────────────────────────────────

AZURE_SERVICES: list[ServiceCost] = [
    ServiceCost(service="Virtual Machines",    cost=8_900.00,  region="eastus",         account="azure-prod-sub",  provider=CloudProvider.AZURE),
    ServiceCost(service="Azure SQL Database",  cost=2_340.00,  region="eastus",         account="azure-prod-sub",  provider=CloudProvider.AZURE),
    ServiceCost(service="Azure Blob Storage",  cost=430.00,    region="westeurope",     account="azure-prod-sub",  provider=CloudProvider.AZURE),
    ServiceCost(service="Azure Kubernetes",    cost=3_100.00,  region="eastus2",        account="azure-prod-sub",  provider=CloudProvider.AZURE),
    ServiceCost(service="Azure Functions",     cost=190.00,    region="eastus",         account="azure-prod-sub",  provider=CloudProvider.AZURE),
    ServiceCost(service="Managed Disks",       cost=780.00,    region="eastus",         account="azure-dev-sub",   provider=CloudProvider.AZURE),
]

AZURE_COST_SUMMARY = CostSummary(
    provider=CloudProvider.AZURE,
    total_spend=sum(s.cost for s in AZURE_SERVICES),
    period_days=30,
    by_service=AZURE_SERVICES,
    daily_trend=_daily_trend(520, 30),
)


# ── GCP mock data ─────────────────────────────────────────────────────────────

GCP_SERVICES: list[ServiceCost] = [
    ServiceCost(service="Compute Engine",      cost=5_600.00,  region="us-central1",    account="gcp-prod-project", provider=CloudProvider.GCP),
    ServiceCost(service="Cloud SQL",           cost=1_800.00,  region="us-central1",    account="gcp-prod-project", provider=CloudProvider.GCP),
    ServiceCost(service="Cloud Storage",       cost=310.00,    region="us-multi",       account="gcp-prod-project", provider=CloudProvider.GCP),
    ServiceCost(service="BigQuery",            cost=920.00,    region="us-central1",    account="gcp-prod-project", provider=CloudProvider.GCP),
    ServiceCost(service="Cloud Run",           cost=240.00,    region="us-east1",       account="gcp-dev-project",  provider=CloudProvider.GCP),
    ServiceCost(service="GKE",                 cost=2_100.00,  region="us-central1",    account="gcp-prod-project", provider=CloudProvider.GCP),
]

GCP_COST_SUMMARY = CostSummary(
    provider=CloudProvider.GCP,
    total_spend=sum(s.cost for s in GCP_SERVICES),
    period_days=30,
    by_service=GCP_SERVICES,
    daily_trend=_daily_trend(360, 30),
)


# ── Idle / oversized resources ────────────────────────────────────────────────

IDLE_EC2_INSTANCES: list[Resource] = [
    Resource(
        resource_id="i-0a1b2c3d4e5f60001",
        resource_name="legacy-batch-server",
        resource_type=ResourceType.EC2_INSTANCE,
        provider=CloudProvider.AWS,
        region="us-east-1",
        account="prod-account",
        monthly_cost=312.00,
        tags={"env": "prod", "team": "data"},
        created_at=_iso(180),
        metrics=[
            ResourceMetric(name="avg_cpu_7d", value=1.2,  unit="percent"),
            ResourceMetric(name="avg_net_7d", value=0.04, unit="MB/s"),
        ],
    ),
    Resource(
        resource_id="i-0a1b2c3d4e5f60002",
        resource_name="old-jenkins-master",
        resource_type=ResourceType.EC2_INSTANCE,
        provider=CloudProvider.AWS,
        region="us-east-1",
        account="dev-account",
        monthly_cost=156.00,
        tags={"env": "dev", "team": "platform"},
        created_at=_iso(240),
        metrics=[
            ResourceMetric(name="avg_cpu_7d", value=0.8,  unit="percent"),
            ResourceMetric(name="avg_net_7d", value=0.01, unit="MB/s"),
        ],
    ),
    Resource(
        resource_id="i-0a1b2c3d4e5f60003",
        resource_name="unused-ml-training",
        resource_type=ResourceType.EC2_INSTANCE,
        provider=CloudProvider.AWS,
        region="us-west-2",
        account="prod-account",
        monthly_cost=876.00,   # p3.2xlarge — expensive!
        tags={"env": "prod", "team": "ml"},
        created_at=_iso(45),
        metrics=[
            ResourceMetric(name="avg_cpu_7d", value=2.1,  unit="percent"),
            ResourceMetric(name="avg_gpu_7d", value=0.0,  unit="percent"),
        ],
    ),
]

UNATTACHED_EBS_VOLUMES: list[Resource] = [
    Resource(
        resource_id="vol-0a1b2c3d00000001",
        resource_name="snap-backup-vol-1",
        resource_type=ResourceType.EBS_VOLUME,
        provider=CloudProvider.AWS,
        region="us-east-1",
        account="prod-account",
        monthly_cost=48.00,
        tags={"env": "prod"},
        created_at=_iso(90),
        metrics=[ResourceMetric(name="attached", value=0, unit="bool")],
    ),
    Resource(
        resource_id="vol-0a1b2c3d00000002",
        resource_name="old-data-volume",
        resource_type=ResourceType.EBS_VOLUME,
        provider=CloudProvider.AWS,
        region="us-east-1",
        account="prod-account",
        monthly_cost=120.00,
        tags={"env": "prod", "size": "500GB"},
        created_at=_iso(120),
        metrics=[ResourceMetric(name="attached", value=0, unit="bool")],
    ),
]

OVERSIZED_RDS_INSTANCES: list[Resource] = [
    Resource(
        resource_id="db-prod-reporting-01",
        resource_name="prod-reporting-db",
        resource_type=ResourceType.RDS_INSTANCE,
        provider=CloudProvider.AWS,
        region="us-east-1",
        account="prod-account",
        monthly_cost=1_460.00,   # db.r5.4xlarge
        tags={"env": "prod", "team": "analytics"},
        created_at=_iso(365),
        metrics=[
            ResourceMetric(name="avg_cpu_7d",        value=8.4,   unit="percent"),
            ResourceMetric(name="avg_connections_7d", value=12.0, unit="count"),
            ResourceMetric(name="storage_used_gb",    value=42.0, unit="GB"),
        ],
    ),
]

IDLE_AZURE_VMS: list[Resource] = [
    Resource(
        resource_id="/subscriptions/xxx/resourceGroups/prod-rg/providers/Microsoft.Compute/virtualMachines/idle-vm-01",
        resource_name="idle-vm-01",
        resource_type=ResourceType.VM_INSTANCE,
        provider=CloudProvider.AZURE,
        region="eastus",
        account="azure-prod-sub",
        monthly_cost=248.00,
        tags={"env": "prod", "team": "infra"},
        created_at=_iso(200),
        metrics=[
            ResourceMetric(name="avg_cpu_7d", value=1.5, unit="percent"),
        ],
    ),
]

IDLE_GCP_VMS: list[Resource] = [
    Resource(
        resource_id="projects/gcp-prod/zones/us-central1-a/instances/idle-gce-01",
        resource_name="idle-gce-01",
        resource_type=ResourceType.VM_INSTANCE,
        provider=CloudProvider.GCP,
        region="us-central1",
        account="gcp-prod-project",
        monthly_cost=190.00,
        tags={"env": "prod"},
        created_at=_iso(150),
        metrics=[
            ResourceMetric(name="avg_cpu_7d", value=0.9, unit="percent"),
        ],
    ),
]

ALL_RESOURCES: list[Resource] = (
    IDLE_EC2_INSTANCES
    + UNATTACHED_EBS_VOLUMES
    + OVERSIZED_RDS_INSTANCES
    + IDLE_AZURE_VMS
    + IDLE_GCP_VMS
)
