"""Square Facebook cards: navy header, gold accents, readable on a phone feed."""

import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import facebook_poster

CANVAS = 1080

NAVY = (12, 28, 58)
GOLD = (201, 154, 62)
GOLD_SOFT = (232, 208, 150)
CREAM = (247, 244, 238)
WHITE = (255, 255, 255)
INK = (28, 32, 40)
MUTED = (98, 104, 116)
CARD = (255, 255, 255)
CARD_LINE = (230, 224, 212)

BRAND = "PAKISTAN TENDER ALERTS"

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")


def _resolve_fonts():
    bold, regular = FONT_BOLD, FONT_REGULAR
    if os.path.isfile(bold) and os.path.isfile(regular):
        return bold, regular
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = [
        (
            os.path.join(windir, "Fonts", "segoeuib.ttf"),
            os.path.join(windir, "Fonts", "segoeui.ttf"),
        ),
        (
            os.path.join(windir, "Fonts", "arialbd.ttf"),
            os.path.join(windir, "Fonts", "arial.ttf"),
        ),
        (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ),
    ]
    for b, r in candidates:
        if os.path.isfile(b) and os.path.isfile(r):
            return b, r
    return bold, regular


FONT_BOLD, FONT_REGULAR = _resolve_fonts()


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = (text or "").split()
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
    return lines or [""]


def _fit_title(draw, text, max_width, max_height, max_lines=3, start_size=42, min_size=24):
    size = start_size
    while size >= min_size:
        font = _font(FONT_BOLD, size)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = int(size * 1.22)
        if len(lines) <= max_lines and line_height * len(lines) <= max_height:
            return font, lines, line_height
        size -= 2

    font = _font(FONT_BOLD, min_size)
    lines = _wrap_text(draw, text, font, max_width)
    line_height = int(min_size * 1.22)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(",.;- ") + "…"
    return font, lines, line_height


def _fit_value(draw, text, max_width, max_lines=2, start_size=26, min_size=16):
    size = start_size
    while size >= min_size:
        font = _font(FONT_REGULAR, size)
        lines = _wrap_text(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines, int(size * 1.22)
        size -= 2

    font = _font(FONT_REGULAR, min_size)
    lines = _wrap_text(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and _text_width(draw, last + "…", font) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return font, lines, int(min_size * 1.22)


def _draw_header(draw, width, height, right_label=""):
    draw.rectangle([0, 0, width, height], fill=NAVY)
    draw.rectangle([0, height - 6, width, height], fill=GOLD)

    brand_font = _font(FONT_BOLD, 18)
    draw.text((48, 28), BRAND, font=brand_font, fill=GOLD_SOFT)

    if right_label:
        pill_font = _font(FONT_BOLD, 16)
        pad_x, pad_y = 16, 8
        bbox = draw.textbbox((0, 0), right_label, font=pill_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pw, ph = tw + pad_x * 2, th + pad_y * 2
        x1 = width - 48
        x0 = x1 - pw
        y0 = 22
        y1 = y0 + ph
        draw.rounded_rectangle([x0, y0, x1, y1], radius=ph // 2, fill=GOLD)
        draw.text((x0 + pad_x, y0 + pad_y - bbox[1]), right_label, font=pill_font, fill=NAVY)


def _draw_footer(draw, y, width, text):
    draw.rectangle([0, y, width, CANVAS], fill=NAVY)
    font = _font(FONT_REGULAR, 18)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, y + 22), text, font=font, fill=GOLD_SOFT)


def generate_tender_image(tender: dict, output_path: str) -> str:
    fields = facebook_poster.extract_fields(tender)
    img = Image.new("RGB", (CANVAS, CANVAS), CREAM)
    draw = ImageDraw.Draw(img)

    header_h = 88
    footer_h = 68
    _draw_header(draw, CANVAS, header_h, (fields["city"] or "PAKISTAN").upper())

    margin = 48
    y = header_h + 36
    sector = (fields.get("sector") or fields.get("category") or "TENDER").upper()
    sector_font = _font(FONT_BOLD, 16)
    draw.text((margin, y), sector, font=sector_font, fill=GOLD)
    y += 28

    title_h = 168
    font, lines, line_height = _fit_title(
        draw,
        (tender.get("title") or "").strip() or "Tender notice",
        CANVAS - margin * 2,
        title_h,
        max_lines=3,
        start_size=40,
        min_size=24,
    )
    for line in lines:
        draw.text((margin, y), line, font=font, fill=NAVY)
        y += line_height
    y += 22

    draw.line([(margin, y), (CANVAS - margin, y)], fill=GOLD, width=3)
    y += 28

    cards = [
        ("DEPARTMENT", fields["department"] or "Not listed"),
        ("CLOSES", fields["deadline"] or "Not listed"),
        ("BID SECURITY", fields["bid_security"]),
        ("BID VALIDITY", fields["bid_validity"]),
    ]

    gap = 16
    card_w = (CANVAS - margin * 2 - gap) // 2
    inner = 18
    label_font = _font(FONT_BOLD, 13)

    fitted = [_fit_value(draw, value, card_w - inner * 2, max_lines=2, start_size=24) for _, value in cards]
    row_h = []
    for row in range(2):
        pair = fitted[row * 2 : row * 2 + 2]
        content = max(22 + lh * len(lines) for _, lines, lh in pair)
        row_h.append(max(118, content + 36))

    used = row_h[0] + gap + row_h[1]
    limit = CANVAS - footer_h - 36 - y
    extra = min(limit - used, 80)
    if extra > 0:
        row_h[0] += extra // 2
        row_h[1] += extra - extra // 2

    for i, (label, _value) in enumerate(cards):
        row, col = divmod(i, 2)
        x = margin + col * (card_w + gap)
        cy = y + (0 if row == 0 else row_h[0] + gap)
        h = row_h[row]
        draw.rounded_rectangle(
            [x, cy, x + card_w, cy + h],
            radius=16,
            fill=WHITE,
            outline=CARD_LINE,
            width=1,
        )
        draw.rectangle([x, cy, x + 8, cy + h], fill=GOLD)
        draw.text((x + inner + 4, cy + 22), label, font=label_font, fill=GOLD)
        vfont, vlines, vlh = fitted[i]
        vy = cy + 50
        for line in vlines:
            draw.text((x + inner + 4, vy), line, font=vfont, fill=INK)
            vy += vlh

    _draw_footer(draw, CANVAS - footer_h, CANVAS, "Full details and apply link in the caption")
    img.save(output_path, "PNG", optimize=True)
    return output_path


def generate_digest_image(
    niche_label: str,
    tenders: list,
    output_path: str,
    max_items: int | None = None,
) -> str:
    import config as app_config

    max_items = max_items if max_items is not None else min(app_config.DIGEST_MAX_ITEMS, 5)
    shown = tenders[:max_items]
    overflow = max(0, len(tenders) - len(shown))

    img = Image.new("RGB", (CANVAS, CANVAS), CREAM)
    draw = ImageDraw.Draw(img)

    header_h = 168
    footer_h = 68
    margin = 48

    draw.rectangle([0, 0, CANVAS, header_h], fill=NAVY)
    draw.rectangle([0, header_h - 6, CANVAS, header_h], fill=GOLD)
    draw.text((margin, 24), BRAND, font=_font(FONT_BOLD, 18), fill=GOLD_SOFT)
    draw.text((margin, 58), niche_label, font=_font(FONT_BOLD, 36), fill=WHITE)
    today = datetime.now().strftime("%d %b %Y")
    sub = f"{len(tenders)} new · {today} · Islamabad, Lahore, Karachi"
    draw.text((margin, 112), sub, font=_font(FONT_REGULAR, 18), fill=GOLD_SOFT)

    body_top = header_h + 24
    body_bottom = CANVAS - footer_h - 16
    available = body_bottom - body_top
    row_gap = 14
    n = max(len(shown), 1)
    row_h = (available - row_gap * (n - 1)) // n
    row_h = max(108, min(row_h, 130))
    block = len(shown) * row_h + row_gap * max(len(shown) - 1, 0)
    if block < available:
        body_top += (available - block) // 3

    title_font_row = _font(FONT_BOLD, 22)
    meta_font = _font(FONT_REGULAR, 16)
    num_font = _font(FONT_BOLD, 18)

    for i, tender in enumerate(shown):
        fields = facebook_poster.extract_fields(tender)
        y = body_top + i * (row_h + row_gap)
        draw.rounded_rectangle(
            [margin, y, CANVAS - margin, y + row_h],
            radius=14,
            fill=WHITE,
            outline=CARD_LINE,
            width=1,
        )

        cx, cy, cr = margin + 36, y + row_h // 2, 20
        draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=GOLD)
        num = str(i + 1)
        nb = draw.textbbox((0, 0), num, font=num_font)
        nw, nh = nb[2] - nb[0], nb[3] - nb[1]
        draw.text((cx - nw / 2, cy - nh / 2 - nb[1]), num, font=num_font, fill=NAVY)

        tx = margin + 68
        content_w = CANVAS - margin - tx - 20
        title_lines = _wrap_text(
            draw,
            (tender.get("title") or "").strip() or "Untitled",
            title_font_row,
            content_w,
        )[:2]
        ty = y + 18
        for line in title_lines:
            draw.text((tx, ty), line, font=title_font_row, fill=NAVY)
            ty += 26

        dept = fields.get("department") or ""
        if dept:
            dept_lines = _wrap_text(draw, dept, meta_font, content_w)[:1]
            draw.text((tx, ty + 6), dept_lines[0], font=meta_font, fill=INK)
            ty += 26 + 14  # blank line after organization

        city = fields["city"] or ""
        deadline = fields["deadline"] or ""
        security = fields.get("bid_security") or ""
        if security in ("Not listed", "N/A"):
            security = ""
        meta = " · ".join(p for p in (city, deadline, security) if p)
        if meta:
            draw.text((tx, ty + 4), meta, font=meta_font, fill=MUTED)

    if overflow:
        note_font = _font(FONT_BOLD, 16)
        draw.text(
            (margin, body_bottom - 4),
            f"+{overflow} more in the caption",
            font=note_font,
            fill=GOLD,
        )

    _draw_footer(draw, CANVAS - footer_h, CANVAS, "Tap the post for apply links")
    img.save(output_path, "PNG", optimize=True)
    return output_path
