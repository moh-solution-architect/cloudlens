"""PDF report generation using ReportLab."""
from __future__ import annotations

import io
from datetime import datetime
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from app.models import CostSummary, Recommendation

# Brand colours
PRIMARY = colors.HexColor("#1E40AF")   # blue-800
ACCENT = colors.HexColor("#059669")    # emerald-600
DANGER = colors.HexColor("#DC2626")    # red-600
WARNING = colors.HexColor("#D97706")   # amber-600
LIGHT_BG = colors.HexColor("#F1F5F9")  # slate-100
HEADER_BG = colors.HexColor("#1E3A5F")


def _severity_color(severity: str) -> colors.Color:
    return {
        "critical": DANGER,
        "high": colors.HexColor("#F97316"),
        "medium": WARNING,
        "low": ACCENT,
    }.get(severity.lower(), colors.grey)


def generate_report(
    recommendations: list[Recommendation],
    summary: CostSummary,
) -> bytes:
    """Return PDF bytes for the CloudLens cost report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CloudLensTitle",
        parent=styles["Title"],
        textColor=PRIMARY,
        fontSize=24,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        textColor=colors.grey,
        fontSize=10,
        spaceAfter=12,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        textColor=PRIMARY,
        fontSize=14,
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
    )

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    story.append(Paragraph("CloudLens", title_style))
    story.append(Paragraph("Multi-Cloud Cost Optimization Report", subtitle_style))
    story.append(
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY))
    story.append(Spacer(1, 0.4 * cm))

    # ── Executive Summary ────────────────────────────────────────────────────
    story.append(Paragraph("Executive Summary", h2_style))

    summary_data = [
        ["Metric", "Value"],
        ["Total Monthly Spend", f"${summary.total_monthly_spend:,.2f}"],
        ["Projected Monthly Savings", f"${summary.total_projected_savings:,.2f}"],
        ["Savings Opportunity", f"{summary.savings_percentage:.1f}%"],
        ["Total Recommendations", str(summary.recommendation_count)],
    ]

    summary_table = Table(summary_data, colWidths=[9 * cm, 7 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTNAME", (0, 2), (0, 2), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, 2), (1, 2), ACCENT),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Spend by provider ────────────────────────────────────────────────────
    story.append(Paragraph("Spend by Provider", h2_style))
    provider_data = [["Provider", "Monthly Spend", "Share"]]
    total = summary.total_monthly_spend or 1
    for provider, amount in summary.by_provider.items():
        provider_data.append(
            [
                provider.upper(),
                f"${amount:,.2f}",
                f"{(amount / total) * 100:.1f}%",
            ]
        )
    provider_table = Table(provider_data, colWidths=[6 * cm, 5 * cm, 5 * cm])
    provider_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(provider_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Recommendations ──────────────────────────────────────────────────────
    story.append(Paragraph("Optimization Recommendations", h2_style))
    story.append(
        Paragraph(
            f"The following {len(recommendations)} recommendations were identified. "
            "Implementing all of them would save an estimated "
            f"<b>${sum(r.projected_monthly_savings for r in recommendations):,.2f}/month</b>.",
            body_style,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    rec_data = [
        ["Resource", "Type", "Provider / Region", "Monthly Cost", "Savings", "Severity"],
    ]
    for r in sorted(recommendations, key=lambda x: -x.projected_monthly_savings):
        rec_data.append(
            [
                Paragraph(r.resource_name, body_style),
                r.recommendation_type.value.replace("_", " ").title(),
                f"{r.provider.value.upper()}\n{r.region}",
                f"${r.current_monthly_cost:,.2f}",
                f"${r.projected_monthly_savings:,.2f}",
                r.severity.value.upper(),
            ]
        )

    col_w = [4.5 * cm, 3.5 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 2 * cm]
    rec_table = Table(rec_data, colWidths=col_w, repeatRows=1)

    row_styles: list[tuple] = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    # Colour severity cells
    for row_idx, r in enumerate(recommendations, start=1):
        sev_col = _severity_color(r.severity.value)
        row_styles.append(("TEXTCOLOR", (5, row_idx), (5, row_idx), sev_col))
        row_styles.append(("FONTNAME", (5, row_idx), (5, row_idx), "Helvetica-Bold"))

    rec_table.setStyle(TableStyle(row_styles))
    story.append(rec_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Actions detail ───────────────────────────────────────────────────────
    story.append(Paragraph("Recommended Actions", h2_style))
    for r in sorted(recommendations, key=lambda x: -x.projected_monthly_savings):
        story.append(
            Paragraph(
                f"<b>{r.resource_name}</b> &nbsp;|&nbsp; {r.provider.value.upper()} "
                f"&nbsp;{r.region} &nbsp;|&nbsp; Save <font color='#059669'>"
                f"${r.projected_monthly_savings:,.2f}/mo</font>",
                body_style,
            )
        )
        story.append(Paragraph(r.description, body_style))
        story.append(Paragraph(f"<i>Action: {r.action}</i>", body_style))
        story.append(Spacer(1, 0.25 * cm))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(
        Paragraph(
            "CloudLens — Multi-Cloud Cost Optimizer | Confidential",
            ParagraphStyle("footer", parent=styles["Normal"], fontSize=7, textColor=colors.grey, alignment=TA_CENTER),
        )
    )

    doc.build(story)
    return buffer.getvalue()
