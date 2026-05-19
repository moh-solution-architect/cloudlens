from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.models import CloudProvider, Recommendation, RecommendationSummary, RecommendationType
from app.utils.mock_data import build_recommendations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _get_recommendations(settings: Settings) -> list[Recommendation]:
    if settings.use_mock_data:
        return build_recommendations()

    # Live path — gather from all enabled providers
    from app.services import aws_service, azure_service, gcp_service
    from app.services.recommendation_engine import aggregate_recommendations

    instances = []
    volumes = []
    databases = []

    instances.extend(aws_service.fetch_idle_ec2_instances())
    volumes.extend(aws_service.fetch_unattached_ebs_volumes())
    databases.extend(aws_service.fetch_rds_instances())
    instances.extend(azure_service.fetch_idle_azure_vms())
    instances.extend(gcp_service.fetch_idle_gce_instances())

    return aggregate_recommendations(instances, volumes, databases)


@router.get("/", response_model=RecommendationSummary)
def list_recommendations(
    settings: Annotated[Settings, Depends(get_settings)],
    provider: list[CloudProvider] | None = Query(default=None),
    rec_type: list[RecommendationType] | None = Query(default=None),
    min_savings: float = Query(default=0.0, ge=0),
) -> RecommendationSummary:
    """Return all recommendations, optionally filtered by provider, type, and minimum savings."""
    recs = _get_recommendations(settings)

    if provider:
        recs = [r for r in recs if r.provider in provider]
    if rec_type:
        recs = [r for r in recs if r.recommendation_type in rec_type]
    if min_savings > 0:
        recs = [r for r in recs if r.projected_monthly_savings >= min_savings]

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_provider: dict[str, int] = {}

    for r in recs:
        by_type[r.recommendation_type.value] = by_type.get(r.recommendation_type.value, 0) + 1
        by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        by_provider[r.provider.value] = by_provider.get(r.provider.value, 0) + 1

    return RecommendationSummary(
        total_recommendations=len(recs),
        total_projected_savings=round(sum(r.projected_monthly_savings for r in recs), 2),
        by_type=by_type,
        by_severity=by_severity,
        by_provider=by_provider,
        recommendations=recs,
    )


@router.get("/{recommendation_id}", response_model=Recommendation)
def get_recommendation(
    recommendation_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Recommendation:
    from fastapi import HTTPException

    recs = _get_recommendations(settings)
    for r in recs:
        if r.id == recommendation_id:
            return r
    raise HTTPException(status_code=404, detail=f"Recommendation {recommendation_id!r} not found")
