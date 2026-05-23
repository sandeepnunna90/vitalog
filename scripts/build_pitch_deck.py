"""Generate Vitalog pitch deck as a PPTX file.

Usage:
    uv run python scripts/build_pitch_deck.py
Output:
    docs/vitalog_pitch_deck.pptx
"""

from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
TEAL = RGBColor(0x0D, 0x4F, 0x5C)
CORAL = RGBColor(0xE8, 0x5D, 0x4A)
BG = RGBColor(0xF8, 0xF9, 0xFA)
TEXT = RGBColor(0x1C, 0x1C, 0x1E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_TEAL = RGBColor(0xE0, 0xF0, 0xF3)
MID_GRAY = RGBColor(0x6B, 0x7B, 0x80)

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)

FONT = "Helvetica Neue"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs: Presentation):
    blank_layout = prs.slide_layouts[6]  # completely blank
    return prs.slides.add_slide(blank_layout)


def bg_rect(slide, color: RGBColor = BG) -> None:
    left, top, width, height = 0, 0, SLIDE_W, SLIDE_H
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def teal_bar(slide, height: float = Inches(0.08)) -> None:
    """Thin teal accent bar at the very top."""
    shape = slide.shapes.add_shape(1, 0, 0, SLIDE_W, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = TEAL
    shape.line.fill.background()


def add_textbox(
    slide,
    text: str,
    left, top, width, height,
    font_size: int = 20,
    bold: bool = False,
    color: RGBColor = TEXT,
    align=PP_ALIGN.LEFT,
    wrap: bool = True,
    font_name: str = FONT,
) -> None:
    txb = slide.shapes.add_textbox(left, top, width, height)
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font_name


def add_richbox(
    slide,
    lines: list[tuple[str, int, bool, RGBColor]],  # (text, size, bold, color)
    left, top, width, height,
    align=PP_ALIGN.LEFT,
) -> None:
    """Multi-paragraph textbox."""
    txb = slide.shapes.add_textbox(left, top, width, height)
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    for i, (text, size, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(4)
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = FONT


def logo(slide, left=Inches(0.45), top=Inches(0.22)) -> None:
    """Vitalog wordmark: small trend-line icon + text."""
    # Icon: three dots connected by rising line (drawn as thin rectangles + circles)
    dot_r = Inches(0.055)
    positions = [
        (left + Inches(0.00), top + Inches(0.22)),
        (left + Inches(0.13), top + Inches(0.10)),
        (left + Inches(0.26), top + Inches(0.00)),
    ]
    # Connecting lines
    for i in range(len(positions) - 1):
        x1, y1 = positions[i]
        x2, y2 = positions[i + 1]
        line = slide.shapes.add_shape(1, x1, y1, x2 - x1, dot_r * 0.6)
        line.fill.solid()
        line.fill.fore_color.rgb = CORAL
        line.line.fill.background()
    # Dots
    for x, y in positions:
        dot = slide.shapes.add_shape(9, x - dot_r / 2, y - dot_r / 2, dot_r, dot_r)
        dot.fill.solid()
        dot.fill.fore_color.rgb = CORAL
        dot.line.fill.background()
    # Wordmark
    add_textbox(
        slide, "Vitalog",
        left + Inches(0.38), top - Inches(0.04),
        Inches(1.4), Inches(0.45),
        font_size=20, bold=True, color=TEAL,
    )


def section_label(slide, text: str, left=Inches(0.45), top=Inches(0.72)) -> None:
    add_textbox(slide, text.upper(), left, top, Inches(4), Inches(0.3),
                font_size=9, bold=True, color=CORAL)


def slide_title(slide, text: str, left=Inches(0.45), top=Inches(1.0),
                width=Inches(12.4), size=36) -> None:
    add_textbox(slide, text, left, top, width, Inches(1.2),
                font_size=size, bold=True, color=TEAL)


def bullet(slide, items: list[str], left=Inches(0.45), top=Inches(2.1),
           width=Inches(12.0), size=20, color: RGBColor = TEXT) -> None:
    lines = []
    for item in items:
        lines.append(("• " + item, size, False, color))
        lines.append(("", size - 4, False, TEXT))
    add_richbox(slide, lines, left, top, width, Inches(5))


def stat_box(slide, value: str, label: str, left, top,
             w=Inches(2.8), h=Inches(1.5)) -> None:
    # Card background
    card = slide.shapes.add_shape(1, left, top, w, h)
    card.fill.solid()
    card.fill.fore_color.rgb = LIGHT_TEAL
    card.line.color.rgb = TEAL
    card.line.width = Pt(0.5)
    # Value
    add_textbox(slide, value, left, top + Inches(0.15), w, Inches(0.7),
                font_size=32, bold=True, color=CORAL, align=PP_ALIGN.CENTER)
    # Label
    add_textbox(slide, label, left, top + Inches(0.75), w, Inches(0.6),
                font_size=13, bold=False, color=TEAL, align=PP_ALIGN.CENTER)


def week_row(slide, week: str, what: str, top) -> None:
    # Week label pill
    pill = slide.shapes.add_shape(1, Inches(0.45), top, Inches(1.4), Inches(0.42))
    pill.fill.solid()
    pill.fill.fore_color.rgb = TEAL
    pill.line.fill.background()
    add_textbox(slide, week, Inches(0.45), top + Inches(0.04), Inches(1.4), Inches(0.35),
                font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    # Content
    add_textbox(slide, what, Inches(2.1), top + Inches(0.04), Inches(10.7), Inches(0.38),
                font_size=14, bold=False, color=TEXT)


def divider(slide, top) -> None:
    line = slide.shapes.add_shape(1, Inches(0.45), top, Inches(12.4), Inches(0.012))
    line.fill.solid()
    line.fill.fore_color.rgb = LIGHT_TEAL
    line.line.fill.background()


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------

def slide_title_card(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl, TEAL)

    # Large background wordmark (decorative)
    add_textbox(sl, "Vitalog", Inches(6.5), Inches(1.5), Inches(8), Inches(3),
                font_size=120, bold=True,
                color=RGBColor(0x0A, 0x3D, 0x47), align=PP_ALIGN.LEFT)

    # Logo top-left
    logo(sl, left=Inches(0.5), top=Inches(0.3))
    # Override logo text color for dark bg
    add_textbox(sl, "Vitalog", Inches(0.9), Inches(0.26), Inches(2), Inches(0.45),
                font_size=20, bold=True, color=WHITE)

    # Main headline
    add_textbox(
        sl,
        "Your lab results.\nUnified. Intelligent.",
        Inches(0.5), Inches(2.2), Inches(9), Inches(2.5),
        font_size=52, bold=True, color=WHITE,
    )

    # Tagline
    add_textbox(
        sl,
        "Upload any lab PDF. Ask anything. Get a citation-verified summary.",
        Inches(0.5), Inches(4.5), Inches(9), Inches(0.8),
        font_size=20, bold=False, color=RGBColor(0xB2, 0xD4, 0xDB),
    )

    # Coral accent bar bottom
    bar = sl.shapes.add_shape(1, 0, Inches(6.9), SLIDE_W, Inches(0.6))
    bar.fill.solid()
    bar.fill.fore_color.rgb = CORAL
    bar.line.fill.background()

    add_textbox(sl, "100x Engineers — Applied AI Mastery  •  May 2026",
                Inches(0.5), Inches(6.95), Inches(8), Inches(0.45),
                font_size=14, bold=False, color=WHITE)


def slide_problem(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl)
    teal_bar(sl)
    logo(sl)

    section_label(sl, "The Problem")
    slide_title(sl, "Your lab results are scattered.\nYour doctor has 11 minutes.", size=34)

    bullet(sl, [
        "Patients managing chronic conditions see multiple specialists — each with their own portal and paper reports",
        "Every appointment starts with 11 minutes of piecing together history the patient already lived through",
        "The data exists. It's trapped across labs, PDFs, and memory",
        "Patients arrive unprepared. Doctors spend time on logistics instead of care",
    ], top=Inches(2.6), size=19)

    # Pull quote
    quote_box = sl.shapes.add_shape(1, Inches(0.45), Inches(5.8), Inches(12.4), Inches(1.0))
    quote_box.fill.solid()
    quote_box.fill.fore_color.rgb = LIGHT_TEAL
    quote_box.line.fill.background()
    add_textbox(sl,
                '"I have results from three different labs and I never know what to bring to my appointment."',
                Inches(0.7), Inches(5.88), Inches(12.0), Inches(0.8),
                font_size=17, bold=False, color=TEAL, align=PP_ALIGN.CENTER)


def slide_solution(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl)
    teal_bar(sl)
    logo(sl)

    section_label(sl, "The Solution")
    slide_title(sl,
                "Vitalog turns scattered lab reports into\na unified, intelligent health record.",
                size=32)

    # Four-step flow boxes
    steps = [
        ("01", "Upload", "Any lab PDF via URL, file, or link"),
        ("02", "Extract", "AWS Textract + Claude Vision OCR every biomarker"),
        ("03", "Ask", "Natural language queries grounded in your data"),
        ("04", "Summarise", "Citation-verified one-page summary for your doctor"),
    ]
    box_w = Inches(2.9)
    gap = Inches(0.25)
    start_left = Inches(0.45)
    top = Inches(2.55)

    for i, (num, title, desc) in enumerate(steps):
        left = start_left + i * (box_w + gap)
        card = sl.shapes.add_shape(1, left, top, box_w, Inches(2.5))
        card.fill.solid()
        card.fill.fore_color.rgb = LIGHT_TEAL
        card.line.color.rgb = TEAL
        card.line.width = Pt(0.75)

        add_textbox(sl, num, left, top + Inches(0.15), box_w, Inches(0.5),
                    font_size=28, bold=True, color=CORAL, align=PP_ALIGN.CENTER)
        add_textbox(sl, title, left, top + Inches(0.65), box_w, Inches(0.45),
                    font_size=16, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
        add_textbox(sl, desc, left + Inches(0.15), top + Inches(1.15), box_w - Inches(0.3), Inches(1.1),
                    font_size=13, bold=False, color=TEXT, align=PP_ALIGN.CENTER)

        # Arrow between boxes
        if i < len(steps) - 1:
            arrow_left = left + box_w + Inches(0.04)
            add_textbox(sl, "→", arrow_left, top + Inches(0.9), Inches(0.18), Inches(0.4),
                        font_size=20, bold=True, color=TEAL)

    # Safety note
    safety = sl.shapes.add_shape(1, Inches(0.45), Inches(5.5), Inches(12.4), Inches(0.55))
    safety.fill.solid()
    safety.fill.fore_color.rgb = RGBColor(0xFF, 0xF3, 0xF2)
    safety.line.color.rgb = CORAL
    safety.line.width = Pt(0.75)
    add_textbox(sl,
                "Hard constraint: Vitalog provides information, not advice. "
                "No diagnoses. No medication recommendations. No dietary prescriptions. "
                "Every number traces back to the source report.",
                Inches(0.65), Inches(5.57), Inches(12.1), Inches(0.45),
                font_size=13, bold=False, color=RGBColor(0x8B, 0x2A, 0x1F))


def slide_demo(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl)
    teal_bar(sl)
    logo(sl)

    section_label(sl, "Product Demo")

    # Big LIVE label
    add_textbox(sl, "Live Demo", Inches(0.45), Inches(0.9), Inches(8), Inches(1.0),
                font_size=42, bold=True, color=TEAL)

    # Two-column layout
    col1 = [
        "Upload 2 real lab reports via URL",
        "Pending queue: unknown biomarker resolved live",
        "Full biomarker list across both reports",
        "Trends: HbA1c, cholesterol, kidney, thyroid",
    ]
    col2 = [
        'Natural language: "How is my kidney function?"',
        "One-page summary — every number citation-verified",
        "Export as PDF",
        "Guardrails: diet / medication / appointment queries declined",
    ]

    for i, item in enumerate(col1):
        add_textbox(sl, "→  " + item,
                    Inches(0.45), Inches(2.1) + Inches(i * 0.85), Inches(6.0), Inches(0.75),
                    font_size=16, bold=False, color=TEXT)
        divider(sl, Inches(2.85) + Inches(i * 0.85))

    for i, item in enumerate(col2):
        add_textbox(sl, "→  " + item,
                    Inches(6.8), Inches(2.1) + Inches(i * 0.85), Inches(6.1), Inches(0.75),
                    font_size=16, bold=False, color=TEXT)
        divider(sl, Inches(2.85) + Inches(i * 0.85))

    # Bottom note
    add_textbox(sl, "Interface: Claude Desktop  ·  Transport: MCP over SSE  ·  Server: Render",
                Inches(0.45), Inches(6.9), Inches(12.4), Inches(0.4),
                font_size=12, bold=False, color=MID_GRAY, align=PP_ALIGN.CENTER)


def slide_traction(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl)
    teal_bar(sl)
    logo(sl)

    section_label(sl, "Traction")
    slide_title(sl, "Built, deployed, and working on real lab reports.", size=32)

    # Stat boxes row
    stats = [
        ("120", "biomarker records\nextracted from real reports"),
        ("65+", "unique biomarker types\nrecognised"),
        ("84", "biomarkers in taxonomy\nacross 9 conditions"),
        ("30 / 33", "stories shipped\nin ~3 weeks"),
    ]
    box_w = Inches(2.9)
    gap = Inches(0.26)
    for i, (val, lbl) in enumerate(stats):
        stat_box(sl, val, lbl, Inches(0.45) + i * (box_w + gap), Inches(2.25))

    # Bullet qualitative points
    qual = [
        "Live on Render with OAuth 2.0 — not a local notebook demo",
        "Two-mode citation verification (structured + parse-and-match) — hallucinated biomarker values are architecturally blocked",
        "20+ adversarial prompts tested — all clinical-advice elicitations blocked without reaching the LLM",
        "Automated PR review on every merge — 47 issues found and fixed before shipping",
    ]
    bullet(sl, qual, top=Inches(4.15), size=17)


def slide_journey(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl)
    teal_bar(sl)
    logo(sl)

    section_label(sl, "Build Journey")
    slide_title(sl, "33 stories · 144 points · ~3 weeks", size=34)

    # Week rows
    rows = [
        ("Week 1", "Data model · Supabase persistence · 84-biomarker taxonomy · AI Gateway · 3-layer guardrails"),
        ("Week 2", "AWS Textract OCR · Vision-LLM fallback · Document classifier · Confidence-band routing · Alias lookup · Unit conversion · Duplicate detection · Pending queue"),
        ("Week 3", "Trend engine · NLQ handler · Observation generator · Citation-verified summary · PDF/MD/JSON export · MCP server · Render deployment · OAuth 2.0"),
    ]
    for i, (week, what) in enumerate(rows):
        week_row(sl, week, what, top=Inches(2.15) + Inches(i * 0.72))
        if i < len(rows) - 1:
            divider(sl, Inches(2.85) + Inches(i * 0.72))

    # Hard things
    add_textbox(sl, "Hard things that got built:", Inches(0.45), Inches(4.4), Inches(12.4), Inches(0.4),
                font_size=15, bold=True, color=TEAL)

    hard = [
        "Two citation-verification modes so no hallucinated biomarker value reaches the output",
        "Pending taxonomy queue — unknown biomarker names are never silently discarded",
        "Architecture doc → acceptance criteria → code → automated review — on every story",
    ]
    bullet(sl, hard, top=Inches(4.8), size=15)


def slide_team(prs: Presentation) -> None:
    sl = blank_slide(prs)
    bg_rect(sl, TEAL)

    # Coral bar top
    bar = sl.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(0.08))
    bar.fill.solid()
    bar.fill.fore_color.rgb = CORAL
    bar.line.fill.background()

    # Logo (white wordmark)
    add_textbox(sl, "Vitalog", Inches(0.5), Inches(0.22), Inches(2), Inches(0.45),
                font_size=20, bold=True, color=WHITE)

    section_label(sl, "Team", top=Inches(0.72))
    # Override section label color on dark bg
    add_textbox(sl, "TEAM", Inches(0.45), Inches(0.72), Inches(4), Inches(0.3),
                font_size=9, bold=True, color=CORAL)

    add_textbox(sl, "[YOUR NAME]", Inches(0.5), Inches(1.4), Inches(10), Inches(1.0),
                font_size=44, bold=True, color=WHITE)
    add_textbox(sl, "[YOUR ROLE / TITLE]", Inches(0.5), Inches(2.3), Inches(10), Inches(0.5),
                font_size=22, bold=False, color=RGBColor(0xB2, 0xD4, 0xDB))
    add_textbox(sl, "[1–2 lines on relevant background / experience]",
                Inches(0.5), Inches(2.85), Inches(10), Inches(0.5),
                font_size=18, bold=False, color=RGBColor(0xB2, 0xD4, 0xDB))

    add_textbox(sl, "Built solo · 100x Engineers Applied AI Mastery cohort · May 2026",
                Inches(0.5), Inches(3.8), Inches(10), Inches(0.5),
                font_size=16, bold=False, color=RGBColor(0x80, 0xB0, 0xBB))

    # Bottom coral bar
    end_bar = sl.shapes.add_shape(1, 0, Inches(6.9), SLIDE_W, Inches(0.6))
    end_bar.fill.solid()
    end_bar.fill.fore_color.rgb = CORAL
    end_bar.line.fill.background()
    add_textbox(sl, "vitalog  ·  github.com/sandeepnunna90  ·  vitalog-9z6b.onrender.com",
                Inches(0.5), Inches(6.95), Inches(12), Inches(0.45),
                font_size=13, bold=False, color=WHITE)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    prs = new_prs()

    slide_title_card(prs)
    slide_problem(prs)
    slide_solution(prs)
    slide_demo(prs)
    slide_traction(prs)
    slide_journey(prs)
    slide_team(prs)

    out = "docs/vitalog_pitch_deck.pptx"
    prs.save(out)
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
