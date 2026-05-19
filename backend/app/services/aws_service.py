"""AWS data retrieval: Cost Explorer, CloudWatch, EC2, RDS."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.services.recommendation_engine import RawDatabase, RawInstance, RawVolume
from app.models import CloudProvider

logger = logging.getLogger(__name__)
settings = get_settings()

_PROVIDER = CloudProvider.AWS

# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def _session() -> boto3.Session:
    kwargs: dict[str, Any] = {"region_name": settings.aws_default_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.Session(**kwargs)


# ---------------------------------------------------------------------------
# EC2 idle instance detection
# ---------------------------------------------------------------------------


def fetch_idle_ec2_instances(
    lookback_days: int = 7,
    cpu_threshold: float = 5.0,
) -> list[RawInstance]:
    """Return EC2 instances whose avg CPU is below *cpu_threshold*."""
    session = _session()
    ec2 = session.client("ec2")
    cw = session.client("cloudwatch")

    try:
        paginator = ec2.get_paginator("describe_instances")
        pages = paginator.paginate(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        )
        raw_instances: list[RawInstance] = []
        end = datetime.utcnow()
        start = end - timedelta(days=lookback_days)

        for page in pages:
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    iid = inst["InstanceId"]
                    itype = inst.get("InstanceType", "unknown")
                    tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                    name = tags.get("Name", iid)

                    # CloudWatch CPU metrics
                    avg_cpu = _get_cw_stat(cw, "AWS/EC2", "CPUUtilization", "Average", iid, start, end)
                    max_cpu = _get_cw_stat(cw, "AWS/EC2", "CPUUtilization", "Maximum", iid, start, end)
                    net_in = _get_cw_stat(cw, "AWS/EC2", "NetworkIn", "Average", iid, start, end)

                    if avg_cpu is None:
                        logger.debug("No CloudWatch data for %s — skipping", iid)
                        continue

                    monthly_cost = _estimate_ec2_cost(itype)

                    raw_instances.append(
                        RawInstance(
                            provider=_PROVIDER,
                            account_id=settings.aws_account_id,
                            region=session.region_name or settings.aws_default_region,
                            resource_id=iid,
                            resource_name=name,
                            instance_type=itype,
                            state="running",
                            monthly_cost=monthly_cost,
                            avg_cpu_percent=avg_cpu,
                            max_cpu_percent=max_cpu or avg_cpu,
                            avg_network_mbps=(net_in or 0) / 1_000_000,
                            lookback_days=lookback_days,
                            tags=tags,
                        )
                    )
    except (BotoCoreError, ClientError) as exc:
        logger.error("AWS EC2 fetch failed: %s", exc)

    return raw_instances


def _get_cw_stat(
    cw: Any,
    namespace: str,
    metric: str,
    stat: str,
    instance_id: str,
    start: datetime,
    end: datetime,
) -> float | None:
    try:
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric,
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start,
            EndTime=end,
            Period=3600,
            Statistics=[stat],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return None
        return sum(dp[stat] for dp in datapoints) / len(datapoints)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("CloudWatch stat %s/%s for %s failed: %s", namespace, metric, instance_id, exc)
        return None


def _estimate_ec2_cost(instance_type: str) -> float:
    """Rough on-demand Linux USD/month pricing for common instance types."""
    pricing: dict[str, float] = {
        "t2.micro": 8.5, "t2.small": 17.0, "t2.medium": 34.0, "t2.large": 68.0,
        "t3.micro": 7.6, "t3.small": 15.2, "t3.medium": 30.4, "t3.large": 60.7,
        "t3.xlarge": 121.5, "t3.2xlarge": 243.0,
        "m5.large": 70.0, "m5.xlarge": 140.0, "m5.2xlarge": 280.0,
        "m5.4xlarge": 560.0, "m5.8xlarge": 1120.0,
        "c5.large": 62.0, "c5.xlarge": 124.0, "c5.2xlarge": 248.0, "c5.4xlarge": 496.0,
        "r5.large": 91.0, "r5.xlarge": 182.0, "r5.2xlarge": 364.0, "r5.4xlarge": 728.0,
    }
    return pricing.get(instance_type, 150.0)


# ---------------------------------------------------------------------------
# EBS unattached volume detection
# ---------------------------------------------------------------------------


def fetch_unattached_ebs_volumes() -> list[RawVolume]:
    session = _session()
    ec2 = session.client("ec2")

    try:
        paginator = ec2.get_paginator("describe_volumes")
        pages = paginator.paginate(
            Filters=[{"Name": "status", "Values": ["available"]}]
        )
        volumes: list[RawVolume] = []

        for page in pages:
            for vol in page["Volumes"]:
                vid = vol["VolumeId"]
                size_gb = vol["Size"]
                vol_type = vol.get("VolumeType", "gp2")
                tags = {t["Key"]: t["Value"] for t in vol.get("Tags", [])}
                name = tags.get("Name", vid)

                create_time: datetime = vol.get("CreateTime", datetime.utcnow())
                if create_time.tzinfo:
                    create_time = create_time.replace(tzinfo=None)
                days_unattached = (datetime.utcnow() - create_time).days

                monthly_cost = _estimate_ebs_cost(size_gb, vol_type)

                volumes.append(
                    RawVolume(
                        provider=_PROVIDER,
                        account_id=settings.aws_account_id,
                        region=session.region_name or settings.aws_default_region,
                        resource_id=vid,
                        resource_name=name,
                        size_gb=size_gb,
                        volume_type=vol_type,
                        days_unattached=days_unattached,
                        monthly_cost=monthly_cost,
                        tags=tags,
                    )
                )
    except (BotoCoreError, ClientError) as exc:
        logger.error("AWS EBS volume fetch failed: %s", exc)
        return []

    return volumes


def _estimate_ebs_cost(size_gb: int, vol_type: str) -> float:
    rates: dict[str, float] = {
        "gp2": 0.10, "gp3": 0.08, "io1": 0.125, "io2": 0.125,
        "st1": 0.045, "sc1": 0.025,
    }
    rate = rates.get(vol_type, 0.10)
    return round(size_gb * rate, 2)


# ---------------------------------------------------------------------------
# RDS oversized detection
# ---------------------------------------------------------------------------


def fetch_rds_instances() -> list[RawDatabase]:
    session = _session()
    rds = session.client("rds")
    cw = session.client("cloudwatch")

    try:
        resp = rds.describe_db_instances()
        databases: list[RawDatabase] = []
        end = datetime.utcnow()
        start = end - timedelta(days=7)

        for db in resp.get("DBInstances", []):
            dbid = db["DBInstanceIdentifier"]
            db_class = db["DBInstanceClass"]
            engine = db["Engine"]
            tags_raw = db.get("TagList", [])
            tags = {t["Key"]: t["Value"] for t in tags_raw}

            avg_cpu = _get_cw_stat(cw, "AWS/RDS", "CPUUtilization", "Average", dbid, start, end) or 50.0
            avg_conn = _get_cw_stat(cw, "AWS/RDS", "DatabaseConnections", "Average", dbid, start, end) or 10.0
            free_storage = (_get_cw_stat(cw, "AWS/RDS", "FreeStorageSpace", "Average", dbid, start, end) or 0) / 1e9

            monthly_cost = _estimate_rds_cost(db_class)

            databases.append(
                RawDatabase(
                    provider=_PROVIDER,
                    account_id=settings.aws_account_id,
                    region=session.region_name or settings.aws_default_region,
                    resource_id=dbid,
                    resource_name=dbid,
                    instance_class=db_class,
                    engine=engine,
                    avg_cpu_percent=avg_cpu,
                    avg_connections=avg_conn,
                    free_storage_gb=free_storage,
                    monthly_cost=monthly_cost,
                    tags=tags,
                )
            )
    except (BotoCoreError, ClientError) as exc:
        logger.error("AWS RDS fetch failed: %s", exc)
        return []

    return databases


def _estimate_rds_cost(db_class: str) -> float:
    pricing: dict[str, float] = {
        "db.t3.micro": 15.0, "db.t3.small": 30.0, "db.t3.medium": 60.0,
        "db.m5.large": 140.0, "db.m5.xlarge": 280.0, "db.m5.2xlarge": 560.0,
        "db.r5.large": 190.0, "db.r5.xlarge": 380.0, "db.r5.2xlarge": 760.0,
        "db.r5.4xlarge": 1520.0, "db.r5.8xlarge": 3040.0,
    }
    return pricing.get(db_class, 300.0)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def health_check() -> bool:
    try:
        session = _session()
        session.client("sts").get_caller_identity()
        return True
    except Exception as exc:
        logger.warning("AWS health check failed: %s", exc)
        return False
