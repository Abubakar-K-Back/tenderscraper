import os

from PIL import Image, ImageDraw, ImageFont

import facebook_poster

CANVAS_W = 1200

BG_COLOR = (250, 249, 246)
NAVY = (11, 27, 58)
GOLD = (170, 125, 40)
VALUE_COLOR = (40, 40, 45)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")

MARGIN = 60

TOP_PAD = 26
TITLE_BLOCK_H = 220
BOTTOM_PAD = 50

WATERMARK_TEXT = "PAKISTAN TENDER ALERTS"
WATERMARK_COLOR = (160, 160, 162)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if _text_width(draw, candidate, font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_title(draw, text, max_width, max_height, max_lines=3, start_size=44, min_size=22):
    size = start_size
    while size >= min_size:
        font = _font(FONT_BOLD, size)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = int(size * 1.3)
        if len(lines) <= max_lines and line_height * len(lines) <= max_height:
            return font, lines, line_height
        size -= 2

    font = _font(FONT_BOLD, min_size)
    lines = _wrap_text(draw, text, font, max_width)
    line_height = int(min_size * 1.3)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(",.;- ") + "…"
    return font, lines, line_height


def _fit_value(draw, text, max_width, max_lines=2, start_size=32, min_size=18):
    """Wraps a value onto up to `max_lines`, shrinking the font first rather
    than truncating, so long department names etc. still read in full."""
    size = start_size
    while size >= min_size:
        font = _font(FONT_REGULAR, size)
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines, int(size * 1.25)
        size -= 2

    font = _font(FONT_REGULAR, min_size)
    lines = _wrap_text(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and _text_width(draw, last + "…", font) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return font, lines, int(min_size * 1.25)


def generate_tender_image(tender: dict, output_path: str) -> str:
    fields = facebook_poster.extract_fields(tender)

    # First pass on a throwaway canvas to measure the watermark height.
    probe = Image.new("RGB", (CANVAS_W, 10), BG_COLOR)
    probe_draw = ImageDraw.Draw(probe)
    watermark_font = _font(FONT_BOLD, 16)
    watermark_bbox = probe_draw.textbbox((MARGIN, TOP_PAD), WATERMARK_TEXT, font=watermark_font)

    title_y0 = watermark_bbox[3] + 26
    rule_y = title_y0 + TITLE_BLOCK_H + 26
    rows_y0 = rule_y + 2 + 26

    col_width = (CANVAS_W - MARGIN * 2) // 2
    label_font = _font(FONT_BOLD, 20)
    grid = [
        ("DEPARTMENT", fields["department"] or "N/A"),
        ("SUBMISSION DEADLINE", fields["deadline"] or "N/A"),
        ("BID SECURITY", fields["bid_security"]),
        ("BID VALIDITY", fields["bid_validity"]),
    ]

    # Pre-compute each field's fitted font/lines so row heights can flex to
    # fit whichever of the two columns in that row needs more room.
    fitted = [
        _fit_value(probe_draw, value, col_width - 30) for _, value in grid
    ]

    row_gap = 30
    row_positions = []
    y_cursor = rows_y0
    for row_idx in range(0, len(grid), 2):
        row_fields = fitted[row_idx:row_idx + 2]
        row_content_h = max(32 + line_height * len(lines) for _, lines, line_height in row_fields)
        row_positions.append(y_cursor)
        y_cursor += row_content_h + row_gap
    rows_bottom = y_cursor - row_gap

    canvas_h = rows_bottom + BOTTOM_PAD

    img = Image.new("RGB", (CANVAS_W, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Subtle brand watermark, top-left
    draw.text((MARGIN, TOP_PAD), WATERMARK_TEXT, font=watermark_font, fill=WATERMARK_COLOR)

    # Category pill, top-right
    category_text = (fields["category"] or "TENDER").upper()
    pill_font = _font(FONT_BOLD, 18)
    pad_x, pad_y = 16, 8
    bbox = draw.textbbox((0, 0), category_text, font=pill_font)
    pill_w = (bbox[2] - bbox[0]) + pad_x * 2
    pill_h = (bbox[3] - bbox[1]) + pad_y * 2
    pill_x1 = CANVAS_W - MARGIN
    pill_x0 = pill_x1 - pill_w
    pill_y0 = TOP_PAD - 4
    pill_y1 = pill_y0 + pill_h
    draw.rounded_rectangle(
        [pill_x0, pill_y0, pill_x1, pill_y1], radius=pill_h // 2, outline=GOLD, width=2
    )
    draw.text(
        (pill_x0 + pad_x, pill_y0 + pad_y - bbox[1]),
        category_text,
        font=pill_font,
        fill=GOLD,
    )

    # Title, auto-shrunk/wrapped to fit
    title_max_width = CANVAS_W - MARGIN * 2
    font, lines, line_height = _fit_title(draw, tender["title"].strip(), title_max_width, TITLE_BLOCK_H)
    total_height = line_height * len(lines)
    y = title_y0 + max(0, (TITLE_BLOCK_H - total_height) // 2)
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=NAVY)
        y += line_height

    draw.line([(MARGIN, rule_y), (CANVAS_W - MARGIN, rule_y)], fill=GOLD, width=2)

    # Key info, 2 columns x 2 rows, each value auto-wrapped/shrunk to fit
    for i, (label, value) in enumerate(grid):
        row, col = divmod(i, 2)
        x = MARGIN + col * col_width
        yy = row_positions[row]
        draw.text((x, yy), label, font=label_font, fill=GOLD)
        value_font, value_lines, value_line_height = fitted[i]
        vy = yy + 32
        for line in value_lines:
            draw.text((x, vy), line, font=value_font, fill=VALUE_COLOR)
            vy += value_line_height

    img.save(output_path, "PNG")
    return output_path
