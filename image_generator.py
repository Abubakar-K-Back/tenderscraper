import os

from PIL import Image, ImageDraw, ImageFont

import facebook_poster

CANVAS_W, CANVAS_H = 1200, 630
BG_COLOR = (10, 36, 64)
ACCENT_COLOR = (212, 175, 55)
TEXT_COLOR = (255, 255, 255)
RULE_COLOR = (40, 65, 95)
FOOTER_TEXT_COLOR = (10, 36, 64)

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")

MARGIN = 60
HEADER_TEXT = "PAKISTAN TENDERS ALERTS"
FOOTER_TEXT = "New Govt Tenders Posted Daily"


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


def _fit_title(draw, text, max_width, max_height, max_lines=4, start_size=52, min_size=26):
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


def _truncate_to_width(draw, text, font, max_width):
    if _text_width(draw, text, font) <= max_width:
        return text
    while text and _text_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def generate_tender_image(tender: dict, output_path: str) -> str:
    fields = facebook_poster.extract_fields(tender)

    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Header branding
    header_font = _font(FONT_BOLD, 24)
    draw.text((MARGIN, 40), HEADER_TEXT, font=header_font, fill=ACCENT_COLOR)

    # Category pill, top-right
    category_text = (fields["category"] or "TENDER").upper()
    pill_font = _font(FONT_BOLD, 18)
    pad_x, pad_y = 16, 8
    bbox = draw.textbbox((0, 0), category_text, font=pill_font)
    pill_w = (bbox[2] - bbox[0]) + pad_x * 2
    pill_h = (bbox[3] - bbox[1]) + pad_y * 2
    pill_x1 = CANVAS_W - MARGIN
    pill_x0 = pill_x1 - pill_w
    pill_y0 = 35
    pill_y1 = pill_y0 + pill_h
    draw.rounded_rectangle(
        [pill_x0, pill_y0, pill_x1, pill_y1], radius=pill_h // 2, outline=ACCENT_COLOR, width=2
    )
    draw.text(
        (pill_x0 + pad_x, pill_y0 + pad_y - bbox[1]),
        category_text,
        font=pill_font,
        fill=ACCENT_COLOR,
    )

    draw.line([(MARGIN, 100), (CANVAS_W - MARGIN, 100)], fill=RULE_COLOR, width=1)

    # Title, auto-shrunk/wrapped to fit
    title_max_width = CANVAS_W - MARGIN * 2
    title_block_height = 260
    font, lines, line_height = _fit_title(draw, tender["title"].strip(), title_max_width, title_block_height)
    total_height = line_height * len(lines)
    y = 130 + max(0, (title_block_height - total_height) // 2)
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=TEXT_COLOR)
        y += line_height

    divider_y = 410
    draw.line([(MARGIN, divider_y), (CANVAS_W - MARGIN, divider_y)], fill=ACCENT_COLOR, width=2)

    # Info columns: Department / Closing Date / Tender No
    label_font = _font(FONT_BOLD, 14)
    value_font = _font(FONT_REGULAR, 20)
    col_width = (CANVAS_W - MARGIN * 2) // 3
    columns = [
        ("DEPARTMENT", fields["department"] or "N/A"),
        ("CLOSING DATE", fields["deadline"] or "N/A"),
        ("TENDER NO", tender["tender_no"]),
    ]
    col_y = divider_y + 25
    for i, (label, value) in enumerate(columns):
        x = MARGIN + i * col_width
        draw.text((x, col_y), label, font=label_font, fill=ACCENT_COLOR)
        value_line = _truncate_to_width(draw, value, value_font, col_width - 20)
        draw.text((x, col_y + 24), value_line, font=value_font, fill=TEXT_COLOR)

    # Footer bar
    footer_y0 = CANVAS_H - 70
    draw.rectangle([0, footer_y0, CANVAS_W, CANVAS_H], fill=ACCENT_COLOR)
    footer_font = _font(FONT_BOLD, 20)
    fbbox = draw.textbbox((0, 0), FOOTER_TEXT, font=footer_font)
    text_w = fbbox[2] - fbbox[0]
    draw.text(
        ((CANVAS_W - text_w) / 2, footer_y0 + (70 - (fbbox[3] - fbbox[1])) / 2 - fbbox[1]),
        FOOTER_TEXT,
        font=footer_font,
        fill=FOOTER_TEXT_COLOR,
    )

    img.save(output_path, "PNG")
    return output_path
