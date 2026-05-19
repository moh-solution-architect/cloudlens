"""GCP data retrieval: Cloud Billing, Cloud Monitoring, Compute Engine."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.models import CloudProvider
from app.services.recommendation_engine import RawInstance

logger = logging.getLogger(__name__)
settings = get_settings()

_PROVIDER = CloudProvider.GCP


def fetch_idle_gce_instances(
    lookback_days: int = 7,
    cpu_threshold: float = 5.0,
) -> list[RawInstance]:
    try:
        from google.cloud import compute_v1, monitoring_v3

        compute = compute_v1.InstancesClient()
        monitoring = monitoring_v3.MetricServiceClient()

        project = settings.gcp_project_id
        instances: list[RawInstance] = []

        agg_req = compute_v1.AggregatedListInstancesRequest(project=project)
        for zone, scoped_list in compute.aggregated_list(request=agg_req):
            if not scoped_list.instances:
                continue
            for inst in scoped_list.instances:
                if inst.status != "RUNNING":
                    continue

                name = inst.name
                zone_name = zone.split("/")[-1]
                region = "-".join(zone_name.split("-")[:-1])
                machine_type = inst.machine_type.split("/")[-1]
                tags = dict(inst.labels or {})

                avg_cpu = _get_gce_cpu(monitoring, project, name, zone_name, lookback_days)
                if avg_cpu is None:
                    continue

                monthly_cost = _estimate_gce_cost(machine_type)

                instances.append(
                    RawInstance(
                        provider=_PROVIDER,
                        account_id=project,
                        region=region,
                        resource_id=inst.self_link or name,
                        resource_name=name,
                        instance_type=machine_type,
                        state="running",
                        monthly_cost=monthly_cost,
                        avg_cpu_percent=avg_cpu,
                        max_cpu_percent=avg_cpu * 1.6,
                        avg_network_mbps=0.0,
                        lookback_days=lookback_days,
                        tags=tags,
                    )
                )

    except Exception as exc:
        logger.error("GCP GCE fetch failed: %s", exc)
        return []

    return [i for i in instances if i.avg_cpu_percent < cpu_threshold]


def _get_gce_cpu(
    monitoring: Any,  # type: ignore[name-defined]
    project: str,
    instance_name: str,
    zone: str,
    lookback_days: int,
) -> float | None:
    from google.cloud import monitoring_v3
    from google.protobuf import timestamp_pb2

    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=lookback_days)

        interval = monitoring_v3.TimeInterval(
            end_time=timestamp_pb2.Timestamp(seconds=int(end_time.timestamp())),
            start_time=timestamp_pb2.Timestamp(seconds=int(start_time.timestamp())),
        )

        results = monitoring.list_time_series(
            request={
                "name": f"projects/{project}",
                "filter": (
                    f'metric.type="compute.googleapis.com/instance/cpu/utilization" '
                    f'AND resource.labels.instance_name="{instance_name}" '
                    f'AND resource.labels.zone="{zone}"'
                ),
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            }
        )
        values = [
            point.value.double_value * 100
            for ts in results
            for point in ts.points
        ]
        return sum(values) / len(values) if values else None
    except Exception as exc:
        logger.warning("GCP monitoring fetch for %s failed: %s", instance_name, exc)
        return None


def _estimate_gce_cost(machine_type: str) -> float:
    pricing: dict[str, float] = {
        "e2-micro": 6.0, "e2-small": 12.0, "e2-medium": 24.0,
        "e2-standard-2": 48.0, "e2-standard-4": 96.0, "e2-standard-8": 192.0,
        "n1-standard-1": 34.0, "n1-standard-2": 68.0, "n1-standard-4": 136.0,
        "n1-standard-8": 272.0, "n1-standard-16": 544.0,
        "n2-standard-2": 58.0, "n2-standard-4": 116.0, "n2-standard-8": 232.0,
    }
    return pricing.get(machine_type, 120.0)


def health_check() -> bool:
    try:
        from google.cloud import billing_v1

        client = billing_v1.CloudBillingClient()
        next(iter(client.list_billing_accounts()), None)
        return True
    except Exception as exc:
        logger.warning("GCP health check failed: %s", exc)
        return False


from typing import Any  # noqa: E402
