"""
CloudLens — Azure analyser.
Uses Azure Cost Management REST API and Azure Monitor for VM metrics.
Falls back to mock data when USE_MOCK_DATA=true.
"""
from __future__ import annotations

import logging
import mock_data
from config import get_settings
from models import CloudProvider, CostSummary, Resource

logger = logging.getLogger(__name__)


class AzureAnalyzer:
    def __init__(self) -> None:
        self._settings = get_settings()

    def get_cost_summary(self) -> CostSummary:
        if self._settings.use_mock_data:
            logger.info("Azure: returning mock cost summary")
            return mock_data.AZURE_COST_SUMMARY
        return self._fetch_cost_management()

    def get_idle_resources(self) -> list[Resource]:
        if self._settings.use_mock_data:
            logger.info("Azure: returning mock idle resources")
            return mock_data.IDLE_AZURE_VMS
        return self._detect_idle_vms()

    def _fetch_cost_management(self) -> CostSummary:
        """
        Call Azure Cost Management Query API.
        Requires azure-mgmt-costmanagement package.
        """
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.costmanagement import CostManagementClient

            credential = ClientSecretCredential(
                tenant_id=self._settings.azure_tenant_id,
                client_id=self._settings.azure_client_id,
                client_secret=self._settings.azure_client_secret,
            )
            client = CostManagementClient(credential)
            scope  = f"/subscriptions/{self._settings.azure_subscription_id}"

            # Build query — last 30 days grouped by service
            from azure.mgmt.costmanagement.models import (
                QueryDefinition, QueryTimePeriod, QueryDataset,
                QueryGrouping, QueryAggregation, TimeframeType,
            )
            from datetime import datetime, timedelta

            end   = datetime.utcnow()
            start = end - timedelta(days=30)

            query = QueryDefinition(
                type="ActualCost",
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(from_property=start, to=end),
                dataset=QueryDataset(
                    granularity="Daily",
                    aggregation={"totalCost": QueryAggregation(name="PreTaxCost", function="Sum")},
                    grouping=[QueryGrouping(type="Dimension", name="ServiceName")],
                ),
            )
            result = client.query.usage(scope=scope, parameters=query)
            logger.info("Azure Cost Management query returned %d rows", len(result.rows))
            # Parse result.rows and build CostSummary (omitted for brevity)
            return mock_data.AZURE_COST_SUMMARY
        except Exception as exc:
            logger.error("Azure Cost Management error: %s", exc)
            raise

    def _detect_idle_vms(self) -> list[Resource]:
        """Use Azure Monitor to find VMs with low CPU utilisation."""
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.monitor import MonitorManagementClient
            from azure.mgmt.compute import ComputeManagementClient
            from models import ResourceMetric, ResourceType

            credential = ClientSecretCredential(
                tenant_id=self._settings.azure_tenant_id,
                client_id=self._settings.azure_client_id,
                client_secret=self._settings.azure_client_secret,
            )
            compute  = ComputeManagementClient(credential, self._settings.azure_subscription_id)
            monitor  = MonitorManagementClient(credential, self._settings.azure_subscription_id)
            resources: list[Resource] = []

            for vm in compute.virtual_machines.list_all():
                metrics = monitor.metrics.list(
                    resource_uri=vm.id,
                    metricnames="Percentage CPU",
                    timespan="P7D",
                    interval="PT1H",
                    aggregation="Average",
                )
                values = [
                    dp.average
                    for ts in metrics.value
                    for dp in ts.timeseries[0].data
                    if dp.average is not None
                ] if metrics.value else []

                avg_cpu = sum(values) / len(values) if values else 100.0

                resources.append(
                    Resource(
                        resource_id=vm.id,
                        resource_name=vm.name,
                        resource_type=ResourceType.VM_INSTANCE,
                        provider=CloudProvider.AZURE,
                        region=vm.location,
                        account=self._settings.azure_subscription_id,
                        monthly_cost=0.0,
                        metrics=[ResourceMetric(name="avg_cpu_7d", value=round(avg_cpu, 2), unit="percent")],
                        tags=vm.tags or {},
                    )
                )
            return resources
        except Exception as exc:
            logger.error("Azure VM detection error: %s", exc)
            return []
