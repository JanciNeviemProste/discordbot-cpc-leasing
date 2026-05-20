"""PDF generátor mesačných reportov cez ReportLab.

Vstup: MonthlyStats (z report_stats.py). Výstup: bytes PDF, ktoré ReportsCog
pošle ako Discord attachment. Žiadny IO, žiadne sieťové volania — čistá funkcia.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.services.report_stats import (
    STATUS_LABELS_SK,
    STATUS_ORDER,
    MonthlyStats,
    format_period_sk,
)


def build_monthly_report_pdf(stats: MonthlyStats) -> bytes:
    """Vygeneruje 1-stranový PDF report so súhrnom stats. Vracia raw bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Mesačný report — {stats.flipper_name}",
        author="Synapse Drive Bot",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "H1Custom",
        parent=styles["Heading1"],
        fontSize=20,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#555555"),
        spaceAfter=16,
    )
    body = styles["BodyText"]
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#888888"),
    )

    period = format_period_sk(stats.period_start, stats.period_end)

    elements = [
        Paragraph("Mesačný report leadov", h1),
        Paragraph(f"{stats.flipper_name} · {period}", subtitle_style),
        Paragraph(f"<b>Celkový počet leadov:</b> {stats.total}", body),
        Spacer(1, 12),
    ]

    if stats.total == 0:
        elements.append(
            Paragraph(
                "V tomto mesiaci si nepridal žiadne leady. Skús viac flipovať 🚗",
                body,
            )
        )
    else:
        table_data = [["Status", "Počet"]]
        for status in STATUS_ORDER:
            table_data.append([STATUS_LABELS_SK[status], str(stats.by_status[status])])
        table_data.append(["SPOLU", str(stats.total)])
        commission_str = f"{stats.total_commission:,.2f} €".replace(",", " ").replace(".", ",")
        table_data.append(["Provízia za mesiac", commission_str])

        table = Table(table_data, colWidths=[8 * cm, 4 * cm], hAlign="LEFT")
        table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                # Posledné dva riadky (SPOLU + Provízia za mesiac) — bold + tinted bg
                ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -2), (-1, -1), colors.HexColor("#ecf0f1")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(table)

    elements.append(Spacer(1, 24))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    elements.append(
        Paragraph(
            f"Vygenerované {generated} · Synapse Drive Bot · drive.sk",
            footer_style,
        )
    )

    doc.build(elements)
    return buf.getvalue()
