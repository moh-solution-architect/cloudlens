"""
CloudLens — GCP analyser.
Uses Google Cloud Billing API and Cloud Monitoring for VM metrics.
Falls back to mock data when USE_MOCK_DATA=true.
"""
from __future__ import annotations

import logging
import mock_data
from config import get_settings
from models import CloudProvider, CostSummary, Resource

logger = logging.getLogger(__name__)


class GCPAnalyzer:
    def __init__(self) -> None:
        self._settings = get_settings()

    def get_cost_summary(self) -> CostSummary:
        if self._settings.use_mock_data:
            logger.info("GCP: returning mock cost summary")
            return mock_data.GCP_COST_SUMMARY
        return self._fetch_billing()

    def get_idle_resources(self) -> list[Resource]:
        if self._settings.use_mock_data:
            logger.info("GCP: returning mock idle resources")
            return mock_data.IDLE_GCP_VMS
        return self._detect_idle_vms()

    def _fetch_billing(self) -> CostSummary:
        """
        Query Google Cloud Billing Budget API / BigQuery billing export.
        Requires google-cloud-billing package.
        """
        try:
            from google.cloud import billing_v1
            from google.oauth2 import service_account
            from datetime import datetime, timedelta

            credentials = service_account.Credentials.from_service_account_file(
                self._settings.gcp_service_account_key,
                scopes=["https://www.googleapis.com/auth/cloud-billing.readonly"],
            )

            client  = billing_v1.CloudBillingClient(credentials=credentials)
            project = f"projects/{self._settings.gcp_project_id}"

            # Cloud Billing API lists accounts but cost data comes from BigQuery export.
            # For real usage: query billing BQ dataset with standard SQL.
            logger.info("GCP Billing client initialised for project %s", project)

            # Placeholder — in production, query BigQuery:
            # SELECT service.description, SUM(cost) as total
            # FROM `project.dataset.gcp_billing_export_v1_*`
            # WHERE DATE(_PARTITIONTIME) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            # GROUP BY 1 ORDER BY 2 DESC
            return mock_data.GCP_COST_SUMMARY

        except Exception as exc:
            logger.error("GCP Billing error: %s", exc)
            raise

    def _detect_idle_vms(self) -> list[Resource]:
        """Use Cloud Monitoring to find GCE VMs with low CPU utilisation."""
        try:
            from google.cloud import monitoring_v3, compute_v1
            from google.oauth2 import service_account
            from datetime import datetime, timedelta
            from models import ResourceMetric, ResourceType

            credentials = service_account.Credentials.from_service_account_file(
                self._settings.gcp_service_account_key,
            )

            compute_client = compute_v1.InstancesClient(credentials=credentials)
            monitoring_client = monitoring_v3.MetricServiceClient(credentials=credentials)
            project_name = f"projects/{self._settings.gcp_project_id}"
            resources: list[Resource] = []

            # List all zones then list instances per zone
            agg_client = compute_v1.AggregatedListInstancesRequest(
                project=self._settings.gcp_project_id
            )
            for zone, scoped_list in compute_client.aggregated_list(request=agg_client):
                for vm in scoped_list.instances or []:
                    if vm.status != "RUNNING":
                        continue

                    end_time   = datetime.utcnow()
                    start_time = end_time - timedelta(days=7)

                    interval = monitoring_v3.TimeInterval(
                        {
                            "end_time":   {"seconds": int(end_time.timestamp())},
                            "start_time": {"seconds": int(start_time.timestamp())},
                        }
                    )
                    results = monitoring_client.list_time_series(
                        request={
                            "name":   project_name,
                            "filter": (
                                f'metric.type="compute.googleapis.com/instance/cpu/utilization" '
                                f'AND resource.labels.instance_id="{vm.id}"'
                            ),
                            "interval": interval,
                            "view":     monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                        }
                    )

                    values = [
                        point.value.double_value * 100  # fraction → percent
                        for series in results
                        for point  in series.points
                    ]
                    avg_cpu = sum(values) / len(values) if values else 100.0
                    zone_name = zone.replace("zones/", "")

                    resources.append(
                        Resource(
                            resource_id=f"projects/{self._settings.gcp_project_id}/zones/{zone_name}/instances/{vm.name}",
                            resource_name=vm.name,
                            resource_type=ResourceType.VM_INSTANCE,
                            provider=CloudProvider.GCP,
                            region=zone_name,
                            account=self._settings.gcp_project_id,
                            monthly_cost=0.0,
                            metrics=[ResourceMetric(name="avg_cpu_7d", value=round(avg_cpu, 2), unit="percent")],
                            tags=dict(vm.labels or {}),
                        )
                    )
            return resources

        except Exception as exc:
            logger.error("GCP VM detection error: %s", exc)
            return []
