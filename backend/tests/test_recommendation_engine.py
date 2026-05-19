"""
Unit tests for the CloudLens recommendation engine.

All tests operate on in-memory data — no cloud credentials required.
"""
from __future__ import annotations

import pytest

from app.models import CloudProvider, RecommendationType, Severity
from app.services.recommendation_engine import (
    RawDatabase,
    RawInstance,
    RawVolume,
    _stable_id,
    aggregate_recommendations,
    detect_idle_instances,
    detect_oversized_rds,
    detect_unattached_volumes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_instance(
    *,
    avg_cpu: float = 3.0,
    max_cpu: float = 4.5,
    monthly_cost: float = 200.0,
    state: str = "running",
    provider: CloudProvider = CloudProvider.AWS,
) -> RawInstance:
    return RawInstance(
        provider=provider,
        account_id="acct-001",
        region="us-east-1",
        resource_id="i-abc123",
        resource_name="test-server",
        instance_type="m5.2xlarge",
        state=state,
        monthly_cost=monthly_cost,
        avg_cpu_percent=avg_cpu,
        max_cpu_percent=max_cpu,
        avg_network_mbps=0.5,
        lookback_days=7,
        tags={"env": "test"},
    )


def _make_volume(
    *,
    days_unattached: int = 45,
    monthly_cost: float = 50.0,
    size_gb: int = 500,
) -> RawVolume:
    return RawVolume(
        provider=CloudProvider.AWS,
        account_id="acct-001",
        region="us-east-1",
        resource_id="vol-abc123",
        resource_name="test-volume",
        size_gb=size_gb,
        volume_type="gp3",
        days_unattached=days_unattached,
        monthly_cost=monthly_cost,
        tags={},
    )


def _make_database(
    *,
    avg_cpu: float = 10.0,
    avg_connections: float = 2.0,
    monthly_cost: float = 500.0,
) -> RawDatabase:
    return RawDatabase(
        provider=CloudProvider.AWS,
        account_id="acct-001",
        region="us-east-1",
        resource_id="db-test",
        resource_name="test-db",
        instance_class="db.r5.4xlarge",
        engine="postgres",
        avg_cpu_percent=avg_cpu,
        avg_connections=avg_connections,
        free_storage_gb=200.0,
        monthly_cost=monthly_cost,
        tags={},
    )


# ---------------------------------------------------------------------------
# detect_idle_instances
# ---------------------------------------------------------------------------


class TestDetectIdleInstances:
    def test_flags_low_cpu_instance(self):
        inst = _make_instance(avg_cpu=2.0)
        recs = detect_idle_instances([inst], cpu_threshold=5.0)
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecommendationType.IDLE_INSTANCE

    def test_ignores_instance_above_threshold(self):
        inst = _make_instance(avg_cpu=10.0)
        recs = detect_idle_instances([inst], cpu_threshold=5.0)
        assert recs == []

    def test_ignores_stopped_instance(self):
        inst = _make_instance(avg_cpu=1.0, state="stopped")
        recs = detect_idle_instances([inst], cpu_threshold=5.0)
        assert recs == []

    def test_savings_is_95_percent(self):
        inst = _make_instance(avg_cpu=1.0, monthly_cost=200.0)
        recs = detect_idle_instances([inst])
        assert recs[0].projected_monthly_savings == pytest.approx(190.0, rel=1e-3)

    def test_severity_critical_for_high_cost_very_low_cpu(self):
        inst = _make_instance(avg_cpu=0.5, monthly_cost=600.0)
        recs = detect_idle_instances([inst])
        assert recs[0].severity == Severity.CRITICAL

    def test_severity_high_for_expensive_instance(self):
        inst = _make_instance(avg_cpu=3.0, monthly_cost=250.0)
        recs = detect_idle_instances([inst])
        assert recs[0].severity == Severity.HIGH

    def test_severity_medium_for_moderate_cost(self):
        inst = _make_instance(avg_cpu=3.0, monthly_cost=100.0)
        recs = detect_idle_instances([inst])
        assert recs[0].severity == Severity.MEDIUM

    def test_metrics_attached(self):
        inst = _make_instance(avg_cpu=2.5, max_cpu=4.0)
        recs = detect_idle_instances([inst])
        metric_names = {m.name for m in recs[0].metrics}
        assert "avg_cpu_utilization" in metric_names
        assert "max_cpu_utilization" in metric_names

    def test_provider_preserved(self):
        inst = _make_instance(provider=CloudProvider.AZURE, avg_cpu=1.0)
        recs = detect_idle_instances([inst])
        assert recs[0].provider == CloudProvider.AZURE

    def test_empty_input(self):
        assert detect_idle_instances([]) == []

    def test_custom_cpu_threshold(self):
        inst = _make_instance(avg_cpu=8.0)
        recs_default = detect_idle_instances([inst], cpu_threshold=5.0)
        recs_high = detect_idle_instances([inst], cpu_threshold=10.0)
        assert recs_default == []
        assert len(recs_high) == 1

    def test_recommendation_id_is_deterministic(self):
        inst = _make_instance(avg_cpu=2.0)
        recs1 = detect_idle_instances([inst])
        recs2 = detect_idle_instances([inst])
        assert recs1[0].id == recs2[0].id

    def test_savings_percentage_correct(self):
        inst = _make_instance(avg_cpu=1.0, monthly_cost=100.0)
        recs = detect_idle_instances([inst])
        assert recs[0].savings_percentage == pytest.approx(95.0, rel=1e-2)


# ---------------------------------------------------------------------------
# detect_unattached_volumes
# ---------------------------------------------------------------------------


class TestDetectUnattachedVolumes:
    def test_flags_long_unattached_volume(self):
        vol = _make_volume(days_unattached=45)
        recs = detect_unattached_volumes([vol])
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecommendationType.UNATTACHED_VOLUME

    def test_ignores_recently_unattached(self):
        vol = _make_volume(days_unattached=10)
        recs = detect_unattached_volumes([vol])
        assert recs == []

    def test_exactly_at_threshold_is_flagged(self):
        vol = _make_volume(days_unattached=30)
        recs = detect_unattached_volumes([vol], min_days_unattached=30)
        assert len(recs) == 1

    def test_savings_is_full_monthly_cost(self):
        vol = _make_volume(days_unattached=45, monthly_cost=75.0)
        recs = detect_unattached_volumes([vol])
        assert recs[0].projected_monthly_savings == pytest.approx(75.0)
        assert recs[0].savings_percentage == 100.0

    def test_high_severity_for_expensive_old_volume(self):
        vol = _make_volume(days_unattached=90, monthly_cost=150.0)
        recs = detect_unattached_volumes([vol])
        assert recs[0].severity == Severity.HIGH

    def test_empty_input(self):
        assert detect_unattached_volumes([]) == []

    def test_custom_threshold(self):
        vol = _make_volume(days_unattached=20)
        recs = detect_unattached_volumes([vol], min_days_unattached=15)
        assert len(recs) == 1

    def test_days_unattached_in_metrics(self):
        vol = _make_volume(days_unattached=60)
        recs = detect_unattached_volumes([vol])
        days_metric = next((m for m in recs[0].metrics if m.name == "days_unattached"), None)
        assert days_metric is not None
        assert days_metric.value == 60


# ---------------------------------------------------------------------------
# detect_oversized_rds
# ---------------------------------------------------------------------------


class TestDetectOversizedRDS:
    def test_flags_low_cpu_low_connections(self):
        db = _make_database(avg_cpu=5.0, avg_connections=2.0)
        recs = detect_oversized_rds([db])
        assert len(recs) == 1
        assert recs[0].recommendation_type == RecommendationType.OVERSIZED_RDS

    def test_ignores_well_utilised_db(self):
        db = _make_database(avg_cpu=50.0, avg_connections=100.0)
        recs = detect_oversized_rds([db])
        assert recs == []

    def test_flags_low_cpu_even_with_high_connections(self):
        # CPU alone can trigger the recommendation
        db = _make_database(avg_cpu=5.0, avg_connections=50.0)
        recs = detect_oversized_rds([db], cpu_threshold=20.0, connection_threshold=5)
        assert len(recs) == 1

    def test_savings_is_50_percent(self):
        db = _make_database(avg_cpu=5.0, avg_connections=2.0, monthly_cost=1000.0)
        recs = detect_oversized_rds([db])
        assert recs[0].projected_monthly_savings == pytest.approx(500.0)
        assert recs[0].savings_percentage == pytest.approx(50.0)

    def test_critical_severity_for_expensive_underused(self):
        db = _make_database(avg_cpu=5.0, avg_connections=1.0, monthly_cost=900.0)
        recs = detect_oversized_rds([db])
        assert recs[0].severity == Severity.CRITICAL

    def test_empty_input(self):
        assert detect_oversized_rds([]) == []

    def test_metrics_present(self):
        db = _make_database(avg_cpu=5.0, avg_connections=2.0)
        recs = detect_oversized_rds([db])
        metric_names = {m.name for m in recs[0].metrics}
        assert "avg_cpu_utilization" in metric_names
        assert "avg_connections" in metric_names


# ---------------------------------------------------------------------------
# aggregate_recommendations
# ---------------------------------------------------------------------------


class TestAggregateRecommendations:
    def test_combines_all_detectors(self):
        instances = [_make_instance(avg_cpu=1.0)]
        volumes = [_make_volume(days_unattached=60)]
        databases = [_make_database(avg_cpu=5.0, avg_connections=1.0)]

        recs = aggregate_recommendations(instances, volumes, databases)
        types = {r.recommendation_type for r in recs}
        assert RecommendationType.IDLE_INSTANCE in types
        assert RecommendationType.UNATTACHED_VOLUME in types
        assert RecommendationType.OVERSIZED_RDS in types

    def test_deduplication(self):
        # Same instance passed twice should yield one recommendation
        inst = _make_instance(avg_cpu=1.0)
        recs = aggregate_recommendations([inst, inst], [], [])
        assert len(recs) == 1

    def test_sorted_by_savings_descending(self):
        i1 = _make_instance(avg_cpu=1.0, monthly_cost=100.0)
        i2 = RawInstance(
            **{**i1.__dict__, "resource_id": "i-other", "monthly_cost": 500.0}
        )
        recs = aggregate_recommendations([i1, i2], [], [])
        savings = [r.projected_monthly_savings for r in recs]
        assert savings == sorted(savings, reverse=True)

    def test_empty_inputs(self):
        assert aggregate_recommendations([], [], []) == []


# ---------------------------------------------------------------------------
# Stable ID helper
# ---------------------------------------------------------------------------


class TestStableId:
    def test_same_inputs_produce_same_id(self):
        id1 = _stable_id(CloudProvider.AWS, "i-abc", RecommendationType.IDLE_INSTANCE)
        id2 = _stable_id(CloudProvider.AWS, "i-abc", RecommendationType.IDLE_INSTANCE)
        assert id1 == id2

    def test_different_providers_produce_different_ids(self):
        id_aws = _stable_id(CloudProvider.AWS, "res-1", RecommendationType.IDLE_INSTANCE)
        id_azure = _stable_id(CloudProvider.AZURE, "res-1", RecommendationType.IDLE_INSTANCE)
        assert id_aws != id_azure

    def test_different_resource_ids_produce_different_ids(self):
        id1 = _stable_id(CloudProvider.AWS, "res-1", RecommendationType.IDLE_INSTANCE)
        id2 = _stable_id(CloudProvider.AWS, "res-2", RecommendationType.IDLE_INSTANCE)
        assert id1 != id2

    def test_id_is_32_chars(self):
        sid = _stable_id(CloudProvider.AWS, "res-1", RecommendationType.IDLE_INSTANCE)
        assert len(sid) == 32
