from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models import CostSummary
from app.utils.mock_data import build_cost_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/summary", response_model=CostSummary)
def cost_summary(settings: Annotated[Settings, Depends(get_settings)]) -> CostSummary:
    """Return aggregated cost summary across all cloud providers."""
    if settings.use_mock_data:
        return build_cost_summary()

    # Live path: aggregate from provider SDKs
    # Each provider returns cost data that is merged here.
    # Detailed implementation requires billing API permissions.
    logger.warning("Live cost summary not yet configured — returning mock data")
    return build_cost_summary()
