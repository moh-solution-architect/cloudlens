"""
CloudLens — AWS analyser.
Fetches cost data from Cost Explorer and resource metrics from CloudWatch.
Falls back to mock data when USE_MOCK_DATA=true.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import get_settings
from models import CloudProvider, CostSummary, DailySpend, Resource, ServiceCost
import mock_data

logger = logging.getLogger(__name__)


class AWSAnalyzer:
    def __init__(self) -> None:
        self._settings = get_settings()

    # ── Public interface ──────────────────────────────────────────────────────

    def get_cost_summary(self) -> CostSummary:
        if self._settings.use_mock_data:
            logger.info("AWS: returning mock cost summary")
            return mock_data.AWS_COST_SUMMARY
        return self._fetch_cost_explorer()

    def get_idle_resources(self) -> list[Resource]:
        if self._settings.use_mock_data:
            logger.info("AWS: returning mock idle resources")
            return (
                mock_data.IDLE_EC2_INSTANCES
                + mock_data.UNATTACHED_EBS_VOLUMES
                + mock_data.OVERSIZED_RDS_INSTANCES
            )
        return self._detect_idle_resources()

    # ── Real AWS calls ────────────────────────────────────────────────────────

    def _fetch_cost_explorer(self) -> CostSummary:
        """Call AWS Cost Explorer for last 30 days of spend, grouped by service."""
        try:
            client = boto3.client(
                "ce",
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
                region_name="us-east-1",
            )
            end   = datetime.utcnow().date()
            start = end - timedelta(days=self._settings.lookback_days)

            response = client.get_cost_and_usage(
                TimePeriod={"Start": str(start), "End": str(end)},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            by_service: list[ServiceCost] = []
            daily_trend: list[DailySpend] = []

            for result_by_time in response["ResultsByTime"]:
                day_total = 0.0
                for group in result_by_time["Groups"]:
                    service = group["Keys"][0]
                    amount  = float(group["Metrics"]["UnblendedCost"]["Amount"])
                    day_total += amount
                    by_service.append(
                        ServiceCost(
                            service=service,
                            cost=round(amount * self._settings.lookback_days, 2),
                            region=self._settings.aws_region,
                            account=self._settings.aws_account_id,
                            provider=CloudProvider.AWS,
                        )
                    )
                daily_trend.append(
                    DailySpend(
                        date=result_by_time["TimePeriod"]["Start"],
                        spend=round(day_total, 2),
                    )
                )

            return CostSummary(
                provider=CloudProvider.AWS,
                total_spend=sum(s.cost for s in by_service),
                period_days=self._settings.lookback_days,
                by_service=by_service,
                daily_trend=daily_trend,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error("AWS Cost Explorer error: %s", exc)
            raise

    def _detect_idle_resources(self) -> list[Resource]:
        """
        Use CloudWatch GetMetricStatistics to find EC2 instances with
        avg CPU < threshold over the observation window.
        """
        resources: list[Resource] = []
        try:
            ec2 = boto3.client(
                "ec2",
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
                region_name=self._settings.aws_region,
            )
            cw = boto3.client(
                "cloudwatch",
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
                region_name=self._settings.aws_region,
            )
            instances = ec2.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )
            end   = datetime.utcnow()
            start = end - timedelta(days=self._settings.idle_observation_days)

            for reservation in instances["Reservations"]:
                for inst in reservation["Instances"]:
                    iid  = inst["InstanceId"]
                    name = next(
                        (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                        iid,
                    )
                    metrics = cw.get_metric_statistics(
                        Namespace="AWS/EC2",
                        MetricName="CPUUtilization",
                        Dimensions=[{"Name": "InstanceId", "Value": iid}],
                        StartTime=start,
                        EndTime=end,
                        Period=86400,
                        Statistics=["Average"],
                    )
                    datapoints = metrics["Datapoints"]
                    if not datapoints:
                        continue
                    avg_cpu = sum(d["Average"] for d in datapoints) / len(datapoints)

                    from models import ResourceMetric, ResourceType
                    resources.append(
                        Resource(
                            resource_id=iid,
                            resource_name=name,
                            resource_type=ResourceType.EC2_INSTANCE,
                            provider=CloudProvider.AWS,
                            region=self._settings.aws_region,
                            account=self._settings.aws_account_id,
                            monthly_cost=0.0,  # enriched separately
                            metrics=[ResourceMetric(name="avg_cpu_7d", value=round(avg_cpu, 2), unit="percent")],
                            tags={t["Key"]: t["Value"] for t in inst.get("Tags", [])},
                            created_at=inst.get("LaunchTime", "").isoformat() if inst.get("LaunchTime") else None,
                        )
                    )
        except (BotoCoreError, ClientError) as exc:
            logger.error("AWS EC2/CloudWatch error: %s", exc)
        return resources
