"""Reports API routes."""

from datetime import datetime, timedelta
from io import BytesIO
import os
import platform
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable, Paragraph, PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle
)
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from hips_service.database.models import Alert, ActivityLog, BlockedAction, get_session
from hips_service.utils.time import get_local_time

# Asset paths
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FSKTM_LOGO = os.path.join(_HERE, "assets", "fsktm_logo.png")

router = APIRouter()


class ReportFilters(BaseModel):
    """Applied report filters."""

    start_date: datetime
    end_date: datetime
    platform: Optional[str] = None
    severity: Optional[str] = None


class ReportTotals(BaseModel):
    """Report aggregate values."""

    total_alerts: int
    critical_alerts: int
    blocked_actions: int
    activity_events: int


class ReportDeviceStatus(BaseModel):
    """High-level device security status."""

    device_name: str
    platform: str
    status: str
    last_seen: Optional[datetime] = None


class ReportAlertItem(BaseModel):
    """Alert row for report preview."""

    id: int
    timestamp: datetime
    rule_name: str
    severity: str
    category: str
    message: str
    status: str

    class Config:
        from_attributes = True


class ReportLogItem(BaseModel):
    """Log row for report preview."""

    id: int
    timestamp: datetime
    event_type: str
    severity: Optional[str] = None
    process_name: Optional[str] = None
    file_path: Optional[str] = None

    class Config:
        from_attributes = True


class ReportSummaryResponse(BaseModel):
    """Report summary response."""

    generated_at: datetime
    filters: ReportFilters
    totals: ReportTotals
    device_status: ReportDeviceStatus
    top_alerts: List[ReportAlertItem]
    recent_logs: List[ReportLogItem]


def _parse_datetime(value: Optional[str], fallback: datetime) -> datetime:
    """Parse an ISO datetime query value safely."""
    if not value:
        return fallback
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return fallback


def _build_summary(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    platform_filter: Optional[str],
    severity_filter: Optional[str],
) -> ReportSummaryResponse:
    """Build report summary payload used by both JSON and PDF endpoints."""
    alert_query = db.query(Alert).filter(Alert.timestamp >= start_date, Alert.timestamp <= end_date)
    log_query = db.query(ActivityLog).filter(
        ActivityLog.timestamp >= start_date, ActivityLog.timestamp <= end_date
    )
    blocked_query = db.query(BlockedAction).filter(
        BlockedAction.timestamp >= start_date, BlockedAction.timestamp <= end_date
    )

    if platform_filter:
        alert_query = alert_query.filter(Alert.platform == platform_filter)
        log_query = log_query.filter(ActivityLog.platform == platform_filter)
        blocked_query = blocked_query.filter(BlockedAction.platform == platform_filter)

    if severity_filter:
        alert_query = alert_query.filter(Alert.severity == severity_filter)
        log_query = log_query.filter(ActivityLog.severity == severity_filter)

    total_alerts = alert_query.count()
    critical_alerts = alert_query.filter(Alert.severity == "critical").count()
    blocked_actions = blocked_query.count()
    activity_events = log_query.count()

    recent_alerts = (
        alert_query.order_by(Alert.timestamp.desc()).limit(10).all()
    )
    recent_logs = (
        log_query.order_by(ActivityLog.timestamp.desc()).limit(20).all()
    )

    latest_alert_time = (
        db.query(Alert.timestamp)
        .filter(Alert.timestamp >= start_date, Alert.timestamp <= end_date)
        .order_by(Alert.timestamp.desc())
        .first()
    )
    latest_log_time = (
        db.query(ActivityLog.timestamp)
        .filter(ActivityLog.timestamp >= start_date, ActivityLog.timestamp <= end_date)
        .order_by(ActivityLog.timestamp.desc())
        .first()
    )
    last_seen_values = [value[0] for value in [latest_alert_time, latest_log_time] if value]
    last_seen = max(last_seen_values) if last_seen_values else None

    if critical_alerts > 0:
        current_status = "critical"
    elif total_alerts > 0:
        current_status = "warning"
    else:
        current_status = "healthy"

    return ReportSummaryResponse(
        generated_at=get_local_time(),
        filters=ReportFilters(
            start_date=start_date,
            end_date=end_date,
            platform=platform_filter,
            severity=severity_filter,
        ),
        totals=ReportTotals(
            total_alerts=total_alerts,
            critical_alerts=critical_alerts,
            blocked_actions=blocked_actions,
            activity_events=activity_events,
        ),
        device_status=ReportDeviceStatus(
            device_name=platform.node() or "Unknown Device",
            platform=platform_filter or platform.system().lower(),
            status=current_status,
            last_seen=last_seen,
        ),
        top_alerts=recent_alerts,
        recent_logs=recent_logs,
    )


def _draw_line(pdf: canvas.Canvas, y_pos: int, text: str, font: str = "Helvetica", size: int = 10) -> int:
    """Write one line and return the next y position."""
    if y_pos < 60:
        pdf.showPage()
        y_pos = 750
    pdf.setFont(font, size)
    pdf.drawString(40, y_pos, text)
    return y_pos - 16


def _status_color(status: str) -> colors.Color:
    if status == "critical":
        return colors.HexColor("#DC2626")
    if status == "warning":
        return colors.HexColor("#D97706")
    return colors.HexColor("#16A34A")


def _severity_bg(severity: str) -> colors.Color:
    s = severity.lower()
    if s == "critical":
        return colors.HexColor("#FEE2E2")
    if s == "high":
        return colors.HexColor("#FEF3C7")
    if s == "medium":
        return colors.HexColor("#FFF7ED")
    return colors.white


def _severity_text(severity: str) -> colors.Color:
    s = severity.lower()
    if s == "critical":
        return colors.HexColor("#B91C1C")
    if s == "high":
        return colors.HexColor("#92400E")
    if s == "medium":
        return colors.HexColor("#C2410C")
    return colors.HexColor("#374151")


def _draw_page_footer(pdf: canvas.Canvas, doc) -> None:
    pdf.saveState()
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#9CA3AF"))
    pdf.drawString(36, 20, "CHIPS – Intrusion Prevention System for FSKTM Data Centre  |  CONFIDENTIAL")
    pdf.drawRightString(letter[0] - 36, 20, f"Page {pdf.getPageNumber()}")
    # thin separator line
    pdf.setStrokeColor(colors.HexColor("#E5E7EB"))
    pdf.setLineWidth(0.5)
    pdf.line(36, 32, letter[0] - 36, 32)
    pdf.restoreState()


def _draw_page_header(pdf: canvas.Canvas, doc) -> None:
    pdf.saveState()

    bar_height = 72
    bar_y = letter[1] - bar_height

    # Navy background
    pdf.setFillColor(colors.HexColor("#0B2A4A"))
    pdf.rect(0, bar_y, letter[0], bar_height, stroke=0, fill=1)
    # Blue accent bottom line
    pdf.setFillColor(colors.HexColor("#3B82F6"))
    pdf.rect(0, bar_y, letter[0], 3, stroke=0, fill=1)

    # FSKTM logo (right side)
    if os.path.exists(FSKTM_LOGO):
        logo_w = 1.25 * inch
        logo_h = 0.5 * inch
        logo_x = letter[0] - logo_w - 36
        logo_y = bar_y + (bar_height - logo_h) / 2
        pdf.drawImage(FSKTM_LOGO, logo_x, logo_y, width=logo_w, height=logo_h,
                      preserveAspectRatio=True, mask="auto")

    # Shield icon — matches the lucide Shield used in the app header
    hw, hh, r = 14, 17, 4          # half-width, half-height, corner radius
    cx = 36 + hw                    # horizontal center of shield
    cy = bar_y + 36                 # vertical centre of header bar

    pdf.setFillColor(colors.HexColor("#3B82F6"))
    p = pdf.beginPath()
    p.moveTo(cx - hw + r, cy + hh)
    p.lineTo(cx + hw - r, cy + hh)
    p.curveTo(cx + hw, cy + hh, cx + hw, cy + hh, cx + hw, cy + hh - r)
    p.lineTo(cx + hw, cy)
    p.curveTo(cx + hw, cy - hh * 0.45, cx + hw * 0.5, cy - hh, cx, cy - hh)
    p.curveTo(cx - hw * 0.5, cy - hh, cx - hw, cy - hh * 0.45, cx - hw, cy)
    p.lineTo(cx - hw, cy + hh - r)
    p.curveTo(cx - hw, cy + hh, cx - hw, cy + hh, cx - hw + r, cy + hh)
    p.close()
    pdf.drawPath(p, fill=1, stroke=0)

    # Title hierarchy
    title_x = cx + hw + 12
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(title_x, bar_y + 44, "CHIPS")
    pdf.setFont("Helvetica", 9.5)
    pdf.setFillColor(colors.HexColor("#93C5FD"))
    pdf.drawString(title_x, bar_y + 28, "Intrusion Prevention System  |  FSKTM Data Centre")

    # Timestamp below logo
    generated = get_local_time().strftime("Generated %Y-%m-%d %H:%M MYT")
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(colors.HexColor("#D1D5DB"))
    pdf.drawRightString(letter[0] - 36, bar_y + 10, generated)

    pdf.restoreState()


def _build_cover_page(story: list, summary: ReportSummaryResponse, styles) -> None:
    """Append a professional cover page then a page break."""
    story.append(Spacer(1, 1.2 * inch))

    # FSKTM logo centred on cover
    if os.path.exists(FSKTM_LOGO):
        from reportlab.platypus import Image as RLImage
        img = RLImage(FSKTM_LOGO, width=1.8 * inch, height=0.75 * inch)
        story.append(Table([[img]], colWidths=[6.1 * inch],
                           style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])))
        story.append(Spacer(1, 0.25 * inch))

    # Faculty name — unique style name avoids ReportLab style registry conflicts
    story.append(Paragraph(
        "Fakulti Sains Komputer dan Teknologi Maklumat",
        ParagraphStyle("CvFaculty", parent=styles["Normal"], fontName="Helvetica-Bold",
                       fontSize=12, textColor=colors.HexColor("#1E3A5F"), alignment=1)))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Universiti Malaya, Kuala Lumpur",
        ParagraphStyle("CvUni", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=10, textColor=colors.HexColor("#6B7280"), alignment=1)))
    story.append(Spacer(1, 0.25 * inch))

    # HRFlowable spacing can visually "collide" with adjacent text depending on
    # PDF viewer/font metrics; keep rules tightly controlled and give extra air.
    story.append(
        HRFlowable(
            width="75%",
            thickness=2,
            color=colors.HexColor("#1D4ED8"),
            hAlign="CENTER",
            vAlign="BOTTOM",
            spaceBefore=0,
            spaceAfter=0,
        )
    )
    story.append(Spacer(1, 0.32 * inch))

    story.append(Paragraph(
        "CHIPS Security Report",
        ParagraphStyle("CvTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
                       fontSize=26, textColor=colors.HexColor("#0B2A4A"), alignment=1,
                       leading=30, spaceAfter=0)))
    # Extra gap between title and subtitle (prevents cramped look in some viewers)
    story.append(Spacer(1, 0.28 * inch))
    story.append(Paragraph(
        "Intrusion Prevention System for FSKTM Data Centre",
        ParagraphStyle("CvSub", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=12, textColor=colors.HexColor("#374151"), alignment=1,
                       leading=16, spaceBefore=0, spaceAfter=0)))
    story.append(Spacer(1, 0.32 * inch))

    story.append(
        HRFlowable(
            width="75%",
            thickness=0.5,
            color=colors.HexColor("#D1D5DB"),
            hAlign="CENTER",
            vAlign="BOTTOM",
            spaceBefore=0,
            spaceAfter=0,
        )
    )
    story.append(Spacer(1, 0.3 * inch))

    start = summary.filters.start_date.strftime("%Y-%m-%d %H:%M")
    end = summary.filters.end_date.strftime("%Y-%m-%d %H:%M")
    generated = summary.generated_at.strftime("%Y-%m-%d %H:%M MYT")
    meta = ParagraphStyle("CoverMeta", parent=styles["Normal"], fontName="Helvetica",
                          fontSize=10, textColor=colors.HexColor("#1F2937"),
                          alignment=1, leading=18)
    story.append(Paragraph(f"<b>Device:</b> {summary.device_status.device_name}", meta))
    story.append(Paragraph(f"<b>Platform:</b> {summary.device_status.platform.capitalize()}", meta))
    story.append(Paragraph(f"<b>Report Period:</b> {start}  →  {end}", meta))
    story.append(Paragraph(f"<b>Generated:</b> {generated}", meta))

    story.append(Spacer(1, 0.3 * inch))
    sc = _status_color(summary.device_status.status)
    badge = Table([[summary.device_status.status.upper()]], colWidths=[1.4 * inch])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), sc),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("FONT", (0, 0), (-1, -1), "Helvetica-Bold", 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(Table([[badge]], colWidths=[6.1 * inch],
                       style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])))

    story.append(Spacer(1, 0.8 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB"), hAlign="CENTER"))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "CONFIDENTIAL – For internal use only. Generated automatically by CHIPS.",
        ParagraphStyle("CvNotice", parent=styles["Normal"], fontName="Helvetica",
                       fontSize=8, textColor=colors.HexColor("#9CA3AF"), alignment=1)))
    story.append(PageBreak())


def _build_pdf(summary: ReportSummaryResponse) -> BytesIO:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.HexColor("#111827"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#374151"),
            leading=12,
        )
    )

    story = []

    # ── Cover page ───────────────────────────────────────────────────────────
    _build_cover_page(story, summary, styles)

    # ── Report header meta ───────────────────────────────────────────────────
    story.append(Spacer(1, 0.15 * inch))
    start = summary.filters.start_date.strftime("%Y-%m-%d %H:%M:%S")
    end = summary.filters.end_date.strftime("%Y-%m-%d %H:%M:%S")
    generated = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S MYT")
    story.append(Paragraph(f"<b>Generated:</b> {generated}", styles["Meta"]))
    story.append(Paragraph(f"<b>Date range:</b> {start} → {end}", styles["Meta"]))
    story.append(Paragraph(
        f"<b>Filters:</b> platform={summary.filters.platform or 'all'}, "
        f"severity={summary.filters.severity or 'all'}",
        styles["Meta"]))
    story.append(Spacer(1, 0.18 * inch))

    # ── Executive summary banner ─────────────────────────────────────────────
    _st = summary.device_status.status
    if _st == "critical":
        _bg, _border = colors.HexColor("#FEE2E2"), colors.HexColor("#DC2626")
        _msg = (f"<b>CRITICAL – {summary.totals.critical_alerts} critical alert(s) detected!</b> "
                f"Immediate investigation required on {summary.device_status.device_name}.")
    elif _st == "warning":
        _bg, _border = colors.HexColor("#FEF3C7"), colors.HexColor("#D97706")
        _msg = (f"<b>WARNING – {summary.totals.total_alerts} alert(s) detected.</b> "
                f"Review flagged activity on {summary.device_status.device_name}.")
    else:
        _bg, _border = colors.HexColor("#D1FAE5"), colors.HexColor("#16A34A")
        _msg = (f"<b>HEALTHY – No critical threats detected.</b> "
                f"{summary.device_status.device_name} is operating normally.")
    _exec = Table([[Paragraph(_msg, ParagraphStyle("EM", parent=styles["Normal"],
                  fontName="Helvetica", fontSize=9.5,
                  textColor=colors.HexColor("#1F2937"), leading=14))]],
                  colWidths=[6.1 * inch])
    _exec.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _bg),
        ("BOX", (0, 0), (-1, -1), 2, _border),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(_exec)
    story.append(Spacer(1, 0.22 * inch))

    # Device status
    story.append(Paragraph("Device Status", styles["SectionTitle"]))
    status_color = _status_color(summary.device_status.status)
    device_rows = [
        ["Device", summary.device_status.device_name],
        ["Platform", summary.device_status.platform],
        ["Status", summary.device_status.status.upper()],
        [
            "Last seen",
            summary.device_status.last_seen.strftime("%Y-%m-%d %H:%M:%S")
            if summary.device_status.last_seen
            else "N/A",
        ],
    ]
    device_table = Table(device_rows, colWidths=[1.2 * inch, 4.9 * inch])
    device_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("TEXTCOLOR", (1, 2), (1, 2), status_color),
                ("FONT", (1, 2), (1, 2), "Helvetica-Bold", 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.whitesmoke, colors.white]),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(device_table)
    story.append(Spacer(1, 0.2 * inch))

    # Summary totals
    story.append(Paragraph("Summary totals", styles["SectionTitle"]))
    totals_data = [
        ["Total alerts", str(summary.totals.total_alerts)],
        ["Critical alerts", str(summary.totals.critical_alerts)],
        ["Blocked actions", str(summary.totals.blocked_actions)],
        ["Activity events", str(summary.totals.activity_events)],
    ]
    totals_table = Table(totals_data, colWidths=[2.3 * inch, 3.8 * inch])
    totals_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("FONT", (1, 1), (1, 1), "Helvetica-Bold", 9),
                ("TEXTCOLOR", (1, 1), (1, 1), colors.HexColor("#DC2626")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.whitesmoke]),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(totals_table)
    story.append(Spacer(1, 0.25 * inch))

    # Top alerts table
    story.append(Paragraph("Top alerts (latest 10)", styles["SectionTitle"]))
    if summary.top_alerts:
        alerts_header = ["Time", "Severity", "Rule", "Status"]
        _alert_cell_style = ParagraphStyle("AlertCellWrap", parent=styles["Normal"],
                                           fontName="Helvetica", fontSize=8.5, leading=11)
        alerts_rows = [
            [
                a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                a.severity.upper(),
                Paragraph(a.rule_name, _alert_cell_style),
                a.status,
            ]
            for a in summary.top_alerts
        ]
        col_w = [1.55 * inch, 0.85 * inch, 2.95 * inch, 0.75 * inch]
        alerts_table = Table([alerts_header, *alerts_rows], colWidths=col_w)
        _astyle = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2A4A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        # Per-row severity colour coding on the Severity column (col 1)
        for i, alert in enumerate(summary.top_alerts):
            row = i + 1
            _astyle.append(("BACKGROUND", (1, row), (1, row), _severity_bg(alert.severity)))
            _astyle.append(("TEXTCOLOR", (1, row), (1, row), _severity_text(alert.severity)))
            _astyle.append(("FONT", (1, row), (1, row), "Helvetica-Bold", 8.5))
        alerts_table.setStyle(TableStyle(_astyle))
        story.append(alerts_table)
    else:
        story.append(Paragraph("No alerts found for selected filters.", styles["Meta"]))
    story.append(Spacer(1, 0.25 * inch))

    # Recent logs table
    story.append(Paragraph("Recent activity logs (latest 20)", styles["SectionTitle"]))
    if summary.recent_logs:
        logs_header = ["Time", "Event", "Severity", "Details"]
        _cell_style = ParagraphStyle("CellWrap", parent=styles["Normal"],
                                     fontName="Helvetica", fontSize=8.5, leading=11)
        logs_rows = []
        for log in summary.recent_logs:
            details = log.process_name or log.file_path or "System event"
            logs_rows.append(
                [
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.event_type,
                    (log.severity or "N/A").upper(),
                    Paragraph(details, _cell_style),
                ]
            )
        logs_table = Table([logs_header, *logs_rows], colWidths=[1.55 * inch, 1.35 * inch, 0.85 * inch, 2.35 * inch])
        logs_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(logs_table)
    else:
        story.append(Paragraph("No activity logs found for selected filters.", styles["Meta"]))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=90,
        bottomMargin=50,
        title="CHIPS Security Report",
        author="CHIPS – FSKTM Data Centre",
        subject="Automated Security Incident Report",
    )

    def _on_page(pdf_canvas: canvas.Canvas, doc_obj) -> None:
        _draw_page_header(pdf_canvas, doc_obj)
        _draw_page_footer(pdf_canvas, doc_obj)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buffer.seek(0)
    return buffer


@router.get("/summary", response_model=ReportSummaryResponse)
async def get_report_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    platform_filter: Optional[str] = Query(None, alias="platform"),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """Get summary data for the security report preview."""
    now = get_local_time()
    parsed_end = _parse_datetime(end_date, now)
    parsed_start = _parse_datetime(start_date, parsed_end - timedelta(days=1))

    return _build_summary(db, parsed_start, parsed_end, platform_filter, severity)


@router.get("/export.pdf")
async def export_report_pdf(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    platform_filter: Optional[str] = Query(None, alias="platform"),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """Generate and download a PDF security report."""
    now = get_local_time()
    parsed_end = _parse_datetime(end_date, now)
    parsed_start = _parse_datetime(start_date, parsed_end - timedelta(days=1))

    summary = _build_summary(db, parsed_start, parsed_end, platform_filter, severity)
    buffer = _build_pdf(summary)
    filename = f"chips_security_report_{get_local_time().strftime('%Y%m%d_%H%M%S')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)
