"""Azure data retrieval: Cost Management, Monitor, Compute."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.models import CloudProvider
from app.services.recommendation_engine import RawDatabase, RawInstance, RawVolume

logger = logging.getLogger(__name__)
settings = get_settings()

_PROVIDER = CloudProvider.AZURE


def _credential():
    from azure.identity import ClientSecretCredential

    return ClientSecretCredential(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret,
    )


def fetch_idle_azure_vms(
    lookback_days: int = 7,
    cpu_threshold: float = 5.0,
) -> list[RawInstance]:
    try:
        from azure.mgmt.compute import ComputeManagementClient
        from azure.mgmt.monitor import MonitorManagementClient

        cred = _credential()
        sub = settings.azure_subscription_id
        compute = ComputeManagementClient(cred, sub)
        monitor = MonitorManagementClient(cred, sub)

        instances: list[RawInstance] = []
        end = datetime.utcnow()
        start = end - timedelta(days=lookback_days)

        for vm in compute.virtual_machines.list_all():
            rid = vm.id or ""
            name = vm.name or rid
            location = vm.location or "unknown"
            vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else "unknown"
            tags = dict(vm.tags or {})

            # Azure Monitor CPU metric
            avg_cpu = _get_azure_metric(monitor, rid, "Percentage CPU", start, end)
            if avg_cpu is None:
                continue

            monthly_cost = _estimate_azure_vm_cost(vm_size)

            instances.append(
                RawInstance(
                    provider=_PROVIDER,
                    account_id=sub,
                    region=location,
                    resource_id=rid,
                    resource_name=name,
                    instance_type=vm_size,
                    state="running",
                    monthly_cost=monthly_cost,
                    avg_cpu_percent=avg_cpu,
                    max_cpu_percent=avg_cpu * 1.5,
                    avg_network_mbps=0.0,
                    lookback_days=lookback_days,
                    tags=tags,
                )
            )

    except Exception as exc:
        logger.error("Azure VM fetch failed: %s", exc)
        return []

    return [i for i in instances if i.avg_cpu_percent < cpu_threshold]


def _get_azure_metric(
    monitor: Any,  # type: ignore[name-defined]
    resource_id: str,
    metric_name: str,
    start: datetime,
    end: datetime,
) -> float | None:
    try:
        result = monitor.metrics.list(
            resource_id,
            timespan=f"{start.isoformat()}/{end.isoformat()}",
            interval="PT1H",
            metricnames=metric_name,
            aggregation="Average",
        )
        values = [
            dp.average
            for ts in result.value
            for data in ts.timeseries
            for dp in data.data
            if dp.average is not None
        ]
        return sum(values) / len(values) if values else None
    except Exception as exc:
        logger.warning("Azure metric fetch for %s failed: %s", resource_id, exc)
        return None


def _estimate_azure_vm_cost(vm_size: str) -> float:
    pricing: dict[str, float] = {
        "Standard_B1s": 8.0, "Standard_B2s": 34.0,
        "Standard_D2s_v3": 70.0, "Standard_D4s_v3": 140.0,
        "Standard_D8s_v3": 280.0, "Standard_D16s_v3": 560.0,
        "Standard_E4s_v3": 220.0, "Standard_E8s_v3": 440.0,
    }
    return pricing.get(vm_size, 150.0)


def health_check() -> bool:
    try:
        from azure.identity import ClientSecretCredential
        from azure.mgmt.resource import ResourceManagementClient

        cred = _credential()
        client = ResourceManagementClient(cred, settings.azure_subscription_id)
        next(iter(client.resource_groups.list()), None)
        return True
    except Exception as exc:
        logger.warning("Azure health check failed: %s", exc)
        return False


# Needed for type hint in _get_azure_metric
from typing import Any  # noqa: E402
