from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.config import Settings, get_settings
from app.models import ExportRequest
from app.routers.recommendations import _get_recommendations
from app.utils.mock_data import build_cost_summary
from app.utils.pdf_generator import generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/pdf")
def export_pdf(
    body: ExportRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Generate and return a PDF cost optimization report."""
    recs = _get_recommendations(settings)

    # Apply export filters
    if body.include_providers:
        recs = [r for r in recs if r.provider in body.include_providers]
    if body.include_types:
        recs = [r for r in recs if r.recommendation_type in body.include_types]
    if body.min_savings > 0:
        recs = [r for r in recs if r.projected_monthly_savings >= body.min_savings]

    summary = build_cost_summary() if settings.use_mock_data else build_cost_summary()

    logger.info("Generating PDF report for %d recommendations", len(recs))
    pdf_bytes = generate_report(recs, summary)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="cloudlens-report.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
