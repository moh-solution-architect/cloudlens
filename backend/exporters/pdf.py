"""
CloudLens — PDF Report Exporter.

Generates a professionally formatted PDF summarising:
  • Multi-cloud cost breakdown
  • Top savings recommendations
  • Severity distribution

Uses ReportLab (reportlab package). Falls back gracefully if not installed.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import DashboardResponse

logger = logging.getLogger(__name__)

# ── Colour palette ─────────────────────────────────────────────────────────────
BRAND_BLUE   = (0.11, 0.31, 0.62)   # #1C4F9E
BRAND_TEAL   = (0.05, 0.68, 0.62)   # #0DAD9E
SEVERITY_COLORS = {
    "high":   (0.86, 0.20, 0.18),   # red
    "medium": (0.95, 0.61, 0.07),   # amber
    "low":    (0.18, 0.62, 0.29),   # green
}
LIGHT_GRAY   = (0.95, 0.95, 0.96)
DARK_GRAY    = (0.25, 0.25, 0.30)


def generate_pdf_report(data: "DashboardResponse") -> bytes:
    """
    Produce a PDF report from a DashboardResponse and return raw bytes.
    Raises ImportError if reportlab is not installed.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, KeepTogether,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError as exc:
        raise ImportError(
            "reportlab is required for PDF export. Install it with: pip install reportlab"
        ) from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="CloudLens Cost Optimisation Report",
        author="CloudLens",
    )

    rl_brand_blue = colors.Color(*BRAND_BLUE)
    rl_brand_teal = colors.Color(*BRAND_TEAL)
    rl_light_gray = colors.Color(*LIGHT_GRAY)
    rl_dark_gray  = colors.Color(*DARK_GRAY)

    styles = getSampleStyleSheet()
    style_h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"],
        fontSize=22, textColor=rl_brand_blue, spaceAfter=4,
    )
    style_h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=13, textColor=rl_brand_blue, spaceAfter=3, spaceBefore=8,
    )
    style_normal = ParagraphStyle(
        "Normal2", parent=styles["Normal"],
        fontSize=9, textColor=rl_dark_gray, leading=14,
    )
    style_small = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=7.5, textColor=rl_dark_gray,
    )
    style_center = ParagraphStyle(
        "Center", parent=styles["Normal"],
        fontSize=9, alignment=TA_CENTER,
    )
    style_bold = ParagraphStyle(
        "Bold", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica-Bold",
    )

    story = []
    W = A4[0] - 40 * mm   # usable width

    # ── Cover header ──────────────────────────────────────────────────────────
    story.append(Paragraph("☁ CloudLens", style_h1))
    story.append(Paragraph(
        "Multi-Cloud Cost Optimisation Report",
        ParagraphStyle("Sub", parent=styles["Normal"], fontSize=12,
                       textColor=rl_brand_teal, spaceAfter=2),
    ))
    story.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        style_small,
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=rl_brand_teal, spaceAfter=6))

    # ── Executive summary cards ───────────────────────────────────────────────
    savings = data.savings_summary
    card_data = [
        ["Total Monthly Spend",   f"${data.total_spend:,.0f}"],
        ["Potential Monthly Save", f"${savings.total_monthly_savings:,.0f}"],
        ["Annual Savings",         f"${savings.total_annual_savings:,.0f}"],
        ["Recommendations",        str(savings.recommendations_count)],
    ]
    card_table = Table(
        [card_data],
        colWidths=[W / 4] * 4,
    )
    card_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), rl_brand_blue),
        ("TEXTCOLOR",   (0, 0), (-1, -1), colors.white),
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [rl_brand_blue]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 6 * mm))

    # ── Cost by provider ──────────────────────────────────────────────────────
    story.append(Paragraph("Cost by Cloud Provider", style_h2))
    provider_rows = [["Provider", "Monthly Spend", "% of Total"]]
    for cs in data.cost_summaries:
        pct = (cs.total_spend / data.total_spend * 100) if data.total_spend else 0
        provider_rows.append([
            cs.provider.value.upper(),
            f"${cs.total_spend:,.2f}",
            f"{pct:.1f}%",
        ])
    prov_table = Table(provider_rows, colWidths=[W * 0.4, W * 0.3, W * 0.3])
    prov_table.setStyle(_default_table_style(rl_brand_blue, rl_light_gray))
    story.append(prov_table)
    story.append(Spacer(1, 6 * mm))

    # ── Savings by type ───────────────────────────────────────────────────────
    if savings.by_type:
        story.append(Paragraph("Savings by Recommendation Type", style_h2))
        type_rows = [["Type", "Monthly Savings"]]
        for rtype, amt in sorted(savings.by_type.items(), key=lambda x: -x[1]):
            type_rows.append([rtype.replace("_", " ").title(), f"${amt:,.2f}"])
        type_table = Table(type_rows, colWidths=[W * 0.6, W * 0.4])
        type_table.setStyle(_default_table_style(rl_brand_blue, rl_light_gray))
        story.append(type_table)
        story.append(Spacer(1, 6 * mm))

    # ── Top recommendations ───────────────────────────────────────────────────
    story.append(Paragraph("Top Recommendations", style_h2))
    top = sorted(data.recommendations, key=lambda r: r.monthly_savings, reverse=True)[:15]

    for i, rec in enumerate(top, 1):
        sev_color = colors.Color(*SEVERITY_COLORS.get(rec.severity.value, DARK_GRAY))
        block = [
            [
                Paragraph(f"#{i}  {rec.title}", style_bold),
                Paragraph(
                    f"<font color='#{_hex(sev_color)}'>{rec.severity.value.upper()}</font>",
                    ParagraphStyle("Sev", parent=styles["Normal"],
                                   fontSize=8, alignment=TA_RIGHT),
                ),
            ],
            [
                Paragraph(rec.description, style_normal),
                Paragraph(
                    f"<b>${rec.monthly_savings:,.0f}/mo</b><br/>confidence: {rec.confidence:.0%}",
                    ParagraphStyle("Save", parent=styles["Normal"],
                                   fontSize=8, alignment=TA_RIGHT),
                ),
            ],
        ]
        rec_tbl = Table(block, colWidths=[W * 0.75, W * 0.25])
        rec_tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), rl_light_gray),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW",    (0, -1), (-1, -1), 0.5, rl_brand_teal),
        ]))
        story.append(KeepTogether(rec_tbl))
        story.append(Spacer(1, 2 * mm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=rl_dark_gray))
    story.append(Paragraph(
        "CloudLens  •  Automated Cloud Cost Optimisation  •  Report is informational only.",
        ParagraphStyle("Footer", parent=styles["Normal"],
                       fontSize=7, textColor=rl_dark_gray, alignment=TA_CENTER),
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    logger.info("PDF report generated: %d bytes, %d recommendations", len(pdf_bytes), len(top))
    return pdf_bytes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_table_style(header_color, row_color):
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  header_color),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, row_color]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ])


def _hex(color) -> str:
    """Convert ReportLab Color to 6-char hex string."""
    r = int(color.red   * 255)
    g = int(color.green * 255)
    b = int(color.blue  * 255)
    return f"{r:02x}{g:02x}{b:02x}"
