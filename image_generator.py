import os

from PIL import Image, ImageDraw, ImageFont

import facebook_poster

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANNER_PATH = os.path.join(BASE_DIR, "assets", "banner.png")

CANVAS_W = 1200

# Brand colors sampled from assets/banner.png so the generated section below
# the banner matches it seamlessly.
NAVY = (11, 27, 58)
GREEN = (6, 74, 34)
GOLD = (191, 145, 50)
TEXT_COLOR = (255, 255, 255)
FOOTER_TEXT_COLOR = NAVY

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")

MARGIN = 60
FOOTER_TEXT = "New Govt Tenders Posted Daily"

PAD_AFTER_BANNER = 36
TITLE_BLOCK_H = 220
GAP_AFTER_TITLE = 26
DIVIDER_H = 2
GAP_AFTER_DIVIDER = 22
ROW_H = 62
FOOTER_H = 70
GAP_BEFORE_FOOTER = 30


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


def _truncate_to_width(draw, text, font, max_width):
    if _text_width(draw, text, font) <= max_width:
        return text
    while text and _text_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _load_banner():
    banner = Image.open(BANNER_PATH).convert("RGB")
    scale = CANVAS_W / banner.width
    return banner.resize((CANVAS_W, int(banner.height * scale)))


def generate_tender_image(tender: dict, output_path: str) -> str:
    fields = facebook_poster.extract_fields(tender)

    banner = _load_banner()
    banner_h = banner.height

    title_y0 = banner_h + PAD_AFTER_BANNER
    divider_y = title_y0 + TITLE_BLOCK_H + GAP_AFTER_TITLE
    rows_y0 = divider_y + DIVIDER_H + GAP_AFTER_DIVIDER
    rows_h = ROW_H * 2
    footer_y0 = rows_y0 + rows_h + GAP_BEFORE_FOOTER
    canvas_h = footer_y0 + FOOTER_H

    img = Image.new("RGB", (CANVAS_W, canvas_h), NAVY)
    img.paste(banner, (0, 0))
    draw = ImageDraw.Draw(img)

    # Category pill, top-right of the info section
    category_text = (fields["category"] or "TENDER").upper()
    pill_font = _font(FONT_BOLD, 18)
    pad_x, pad_y = 16, 8
    bbox = draw.textbbox((0, 0), category_text, font=pill_font)
    pill_w = (bbox[2] - bbox[0]) + pad_x * 2
    pill_h = (bbox[3] - bbox[1]) + pad_y * 2
    pill_x1 = CANVAS_W - MARGIN
    pill_x0 = pill_x1 - pill_w
    pill_y0 = title_y0 - pill_h - 10
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
        draw.text((MARGIN, y), line, font=font, fill=TEXT_COLOR)
        y += line_height

    draw.line([(MARGIN, divider_y), (CANVAS_W - MARGIN, divider_y)], fill=GOLD, width=2)

    # Key info, 2 rows x 3 columns: the "major information" at a glance
    label_font = _font(FONT_BOLD, 14)
    value_font = _font(FONT_REGULAR, 19)
    col_width = (CANVAS_W - MARGIN * 2) // 3
    grid = [
        ("DEPARTMENT", fields["department"] or "N/A"),
        ("CLOSING DATE", fields["deadline"] or "N/A"),
        ("TENDER NO", tender["tender_no"]),
        ("BID SECURITY", fields["bid_security"]),
        ("BID VALIDITY", fields["bid_validity"]),
        ("STATUS", fields["status_label"]),
    ]
    for i, (label, value) in enumerate(grid):
        row, col = divmod(i, 3)
        x = MARGIN + col * col_width
        y = rows_y0 + row * ROW_H
        draw.text((x, y), label, font=label_font, fill=GOLD)
        value_line = _truncate_to_width(draw, value, value_font, col_width - 20)
        draw.text((x, y + 22), value_line, font=value_font, fill=TEXT_COLOR)

    # Footer bar
    draw.rectangle([0, footer_y0, CANVAS_W, canvas_h], fill=GOLD)
    footer_font = _font(FONT_BOLD, 20)
    fbbox = draw.textbbox((0, 0), FOOTER_TEXT, font=footer_font)
    text_w = fbbox[2] - fbbox[0]
    draw.text(
        ((CANVAS_W - text_w) / 2, footer_y0 + (FOOTER_H - (fbbox[3] - fbbox[1])) / 2 - fbbox[1]),
        FOOTER_TEXT,
        font=footer_font,
        fill=FOOTER_TEXT_COLOR,
    )

    img.save(output_path, "PNG")
    return output_path
