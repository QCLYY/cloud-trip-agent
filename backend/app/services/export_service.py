from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from app.models.schemas import Itinerary, TripDetailResponse


TECHNICAL_EXPORT_KEYWORDS = (
    "LLM",
    "RAG",
    "LangChain",
    "Chroma",
    "演示",
    "测试",
    "规则",
    "模型",
    "源码",
    "trip_service",
)

SOURCE_TYPE_LABELS = {
    "demo": "本地演示数据",
    "estimate": "规则估算",
    "user_input": "用户录入",
    "tavily": "Tavily 外部检索",
    "official_api": "正式 API",
}

NON_REALTIME_SOURCE_TYPES = {"demo", "estimate", "tavily"}


def _safe_text(value: object) -> str:
    """Escape text for ReportLab Paragraph content."""
    return escape(str(value or ""))


def _clean_export_tips(tips: list[str]) -> list[str]:
    """Remove backend-only implementation notes from exported user files."""
    cleaned_tips: list[str] = []
    for tip in tips:
        normalized_tip = tip.strip()
        if not normalized_tip:
            continue
        if any(keyword in normalized_tip for keyword in TECHNICAL_EXPORT_KEYWORDS):
            continue
        if normalized_tip not in cleaned_tips:
            cleaned_tips.append(normalized_tip)
    return cleaned_tips


def _public_source_notes(source_notes: list[str]) -> list[str]:
    """Keep user-readable guide citations and omit internal implementation notes."""
    public_notes: list[str] = []
    for note in source_notes:
        normalized_note = note.strip()
        if not normalized_note:
            continue
        if any(keyword in normalized_note for keyword in TECHNICAL_EXPORT_KEYWORDS):
            continue
        if normalized_note.startswith("[来源:"):
            public_notes.append(normalized_note)
    return public_notes


def _source_type_label(source_type: object) -> str:
    value = getattr(source_type, "value", source_type)
    return SOURCE_TYPE_LABELS.get(str(value), str(value))


def _render_source_record_lines(itinerary: Itinerary) -> list[str]:
    lines: list[str] = []
    for record in itinerary.source_records:
        label = _source_type_label(record.source_type)
        category = f" / {record.category}" if record.category else ""
        url_text = f" / URL: {record.url}" if record.url else ""
        lines.append(
            f"- {record.title}（{label}{category}{url_text}）：{record.summary}"
        )

    has_non_realtime = any(
        str(getattr(record.source_type, "value", record.source_type))
        in NON_REALTIME_SOURCE_TYPES
        for record in itinerary.source_records
    )
    if has_non_realtime:
        lines.append(
            "- 说明：本地演示数据、规则估算和 Tavily 外部检索不代表实时价格、"
            "实时库存或可预订结果。"
        )
    return lines


def _render_budget_lines(itinerary: Itinerary) -> list[str]:
    budget = itinerary.budget_breakdown
    return [
        f"- 交通：{budget.transport:.2f} 元",
        f"- 住宿：{budget.hotel:.2f} 元",
        f"- 餐饮：{budget.meals:.2f} 元",
        f"- 门票：{budget.tickets:.2f} 元",
        f"- 其他：{budget.other:.2f} 元",
        f"- 总计：{budget.total:.2f} 元",
    ]


def itinerary_to_markdown(trip_detail: TripDetailResponse) -> str:
    """Render a saved itinerary as shareable Markdown."""
    itinerary = trip_detail.itinerary

    lines: list[str] = [
        f"# {itinerary.destination} 行程单",
        "",
        f"- 行程 ID：{trip_detail.trip_id}",
        f"- 目的地：{itinerary.destination}",
        f"- 预计预算：{itinerary.estimated_budget:.2f} 元",
        "",
        "## 行程概览",
        itinerary.summary,
        "",
        "## 每日安排",
    ]

    for day in itinerary.days:
        lines.extend(
            [
                "",
                f"### Day {day.day_index} {day.theme or ''}".rstrip(),
                f"- 日期：{day.date.isoformat()}" if day.date else "- 日期：待定",
            ]
        )

        for spot in day.spots:
            lines.extend(
                [
                    f"- 主要景点：{spot.name}",
                    f"  - 时间：{spot.start_time or '待定'} - {spot.end_time or '待定'}",
                    f"  - 说明：{spot.description or '无'}",
                    f"  - 来源：{_source_type_label(spot.source_type)}",
                ]
            )

        for meal in day.meals:
            lines.extend(
                [
                    f"- 餐饮建议：{meal.name}（{meal.meal_type}）",
                    f"  - 说明：{meal.notes or '无'}",
                    f"  - 来源：{_source_type_label(meal.source_type)}",
                ]
            )

        if day.hotel is not None:
            lines.extend(
                [
                    f"- 住宿安排：{day.hotel.name}（{day.hotel.level or '未标注档次'}）",
                    f"  - 来源：{_source_type_label(day.hotel.source_type)}",
                ]
            )

        for note in day.notes:
            lines.append(f"- 备注：{note}")

    lines.extend(["", "## 预算拆分", *_render_budget_lines(itinerary)])

    export_tips = _clean_export_tips(itinerary.tips)
    if export_tips:
        lines.extend(["", "## 旅行提示"])
        lines.extend(f"- {tip}" for tip in export_tips)

    public_notes = _public_source_notes(itinerary.source_notes)
    if public_notes:
        lines.extend(["", "## 攻略参考"])
        lines.extend(f"- {note}" for note in public_notes)

    source_record_lines = _render_source_record_lines(itinerary)
    if source_record_lines:
        lines.extend(["", "## 数据来源说明"])
        lines.extend(source_record_lines)

    return "\n".join(lines).strip() + "\n"


def _register_pdf_font() -> str:
    """Register a CJK-capable font for PDF rendering."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    font_name = "STSong-Light"
    try:
        pdfmetrics.getFont(font_name)
    except KeyError:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    return font_name


def _draw_pdf_footer(canvas, doc, trip_detail: TripDetailResponse, font_name: str) -> None:
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    page_width, _ = doc.pagesize
    footer_y = 10 * mm
    line_y = 14 * mm

    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd2d9"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, line_y, page_width - doc.rightMargin, line_y)

    canvas.setFont(font_name, 9)
    canvas.setFillColor(colors.HexColor("#52606d"))
    canvas.drawString(doc.leftMargin, footer_y, f"云程智绘图 | {trip_detail.trip_id}")
    canvas.drawRightString(page_width - doc.rightMargin, footer_y, f"第 {canvas.getPageNumber()} 页")
    canvas.restoreState()


def itinerary_to_pdf_bytes(trip_detail: TripDetailResponse) -> bytes:
    """Render a saved itinerary as a PDF byte stream."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PDF 导出依赖 reportlab，请先安装：pip install reportlab"
        ) from exc

    font_name = _register_pdf_font()
    itinerary = trip_detail.itinerary

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"{trip_detail.trip_id}.pdf",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TripTitle",
        parent=base_styles["Title"],
        fontName=font_name,
        fontSize=22,
        leading=28,
        textColor=colors.HexColor("#16324f"),
        spaceAfter=8,
        wordWrap="CJK",
    )
    subtitle_style = ParagraphStyle(
        "TripSubtitle",
        parent=base_styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#4b5d73"),
        spaceAfter=10,
        wordWrap="CJK",
    )
    section_style = ParagraphStyle(
        "TripSection",
        parent=base_styles["Heading2"],
        fontName=font_name,
        fontSize=13.5,
        leading=19,
        textColor=colors.HexColor("#0f4c5c"),
        spaceBefore=10,
        spaceAfter=6,
        wordWrap="CJK",
    )
    day_style = ParagraphStyle(
        "TripDay",
        parent=base_styles["Heading3"],
        fontName=font_name,
        fontSize=12,
        leading=17,
        textColor=colors.HexColor("#1b4332"),
        spaceBefore=6,
        spaceAfter=4,
        wordWrap="CJK",
    )
    body_style = ParagraphStyle(
        "TripBody",
        parent=base_styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#222222"),
        spaceAfter=4,
        wordWrap="CJK",
    )
    note_style = ParagraphStyle(
        "TripNote",
        parent=body_style,
        leftIndent=8,
        bulletIndent=0,
        spaceAfter=3,
    )

    story = [
        Paragraph(f"{_safe_text(itinerary.destination)} 行程单", title_style),
        Paragraph(
            f"行程 ID：{_safe_text(trip_detail.trip_id)}<br/>"
            f"目的地：{_safe_text(itinerary.destination)}<br/>"
            f"预计预算：{itinerary.estimated_budget:.2f} 元",
            subtitle_style,
        ),
    ]

    meta_table = Table(
        [
            ["行程天数", str(len(itinerary.days))],
            ["创建时间", trip_detail.created_at.isoformat() if trip_detail.created_at else "未记录"],
            ["更新时间", trip_detail.updated_at.isoformat() if trip_detail.updated_at else "未记录"],
        ],
        colWidths=[28 * mm, 120 * mm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#243b53")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf4f4")),
                ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#f8fbff")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cdd7e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 8)])

    story.append(Paragraph("行程概览", section_style))
    story.append(Paragraph(_safe_text(itinerary.summary), body_style))

    story.append(Paragraph("每日安排", section_style))
    for day in itinerary.days:
        title = f"Day {day.day_index}"
        if day.theme:
            title += f" · {day.theme}"
        story.append(Paragraph(_safe_text(title), day_style))

        if day.date:
            story.append(Paragraph(f"日期：{day.date.isoformat()}", body_style))

        for spot in day.spots:
            story.append(Paragraph(f"主要景点：{_safe_text(spot.name)}", body_style))
            story.append(
                Paragraph(
                    f"时间：{_safe_text(spot.start_time or '待定')} - "
                    f"{_safe_text(spot.end_time or '待定')}",
                    note_style,
                )
            )
            if spot.address or spot.location:
                story.append(
                    Paragraph(
                        f"地址：{_safe_text(spot.address or spot.location)}",
                        note_style,
                    )
                )
            story.append(Paragraph(f"说明：{_safe_text(spot.description or '无')}", note_style))
            story.append(
                Paragraph(
                    f"来源：{_safe_text(_source_type_label(spot.source_type))}",
                    note_style,
                )
            )

        for meal in day.meals:
            story.append(
                Paragraph(
                    f"餐饮建议：{_safe_text(meal.name)}（{_safe_text(meal.meal_type)}）",
                    body_style,
                )
            )
            story.append(Paragraph(f"说明：{_safe_text(meal.notes or '无')}", note_style))
            story.append(
                Paragraph(
                    f"来源：{_safe_text(_source_type_label(meal.source_type))}",
                    note_style,
                )
            )

        if day.hotel is not None:
            story.append(
                Paragraph(
                    f"住宿安排：{_safe_text(day.hotel.name)}"
                    f"（{_safe_text(day.hotel.level or '未标注档次')}）",
                    body_style,
                )
            )
            story.append(
                Paragraph(
                    f"来源：{_safe_text(_source_type_label(day.hotel.source_type))}",
                    note_style,
                )
            )

        for note in day.notes:
            story.append(Paragraph(f"备注：{_safe_text(note)}", note_style))

        story.append(Spacer(1, 4))

    story.append(Paragraph("预算拆分", section_style))
    budget = itinerary.budget_breakdown
    budget_table = Table(
        [
            ["项目", "金额（元）"],
            ["交通", f"{budget.transport:.2f}"],
            ["住宿", f"{budget.hotel:.2f}"],
            ["餐饮", f"{budget.meals:.2f}"],
            ["门票", f"{budget.tickets:.2f}"],
            ["其他", f"{budget.other:.2f}"],
            ["总计", f"{budget.total:.2f}"],
        ],
        colWidths=[48 * mm, 48 * mm],
    )
    budget_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9edf7")),
                ("BACKGROUND", (0, 1), (-1, -2), colors.white),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eef6f2")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1f2933")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd2d9")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([budget_table, Spacer(1, 6)])

    export_tips = _clean_export_tips(itinerary.tips)
    if export_tips:
        story.append(Paragraph("旅行提示", section_style))
        for tip in export_tips:
            story.append(Paragraph(f"- {_safe_text(tip)}", body_style))

    public_notes = _public_source_notes(itinerary.source_notes)
    if public_notes:
        story.append(Paragraph("攻略参考", section_style))
        for note in public_notes:
            story.append(Paragraph(f"- {_safe_text(note)}", body_style))

    source_record_lines = _render_source_record_lines(itinerary)
    if source_record_lines:
        story.append(Paragraph("数据来源说明", section_style))
        for line in source_record_lines:
            story.append(Paragraph(_safe_text(line), body_style))

    def draw_footer(canvas, document) -> None:
        _draw_pdf_footer(canvas, document, trip_detail, font_name)

    doc.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer,
    )
    return buffer.getvalue()
