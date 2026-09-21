"""Square Facebook digest cards with rotating themes."""

import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

import facebook_poster

CANVAS = 1080
WHITE = (255, 255, 255)
INK = (28, 32, 40)
BRAND = "PAKISTAN TENDER ALERTS"

# Rotating palettes — picked by niche + day so posts are not always the same navy.
THEMES = [
    {
        "name": "navy_gold",
        "primary": (12, 28, 58),
        "accent": (201, 154, 62),
        "accent_soft": (232, 208, 150),
        "bg": (247, 244, 238),
        "card_line": (230, 224, 212),
        "muted": (98, 104, 116),
    },
    {
        "name": "teal_sand",
        "primary": (15, 61, 62),
        "accent": (212, 163, 115),
        "accent_soft": (235, 210, 180),
        "bg": (245, 242, 236),
        "card_line": (222, 216, 205),
        "muted": (95, 105, 105),
    },
    {
        "name": "forest_amber",
        "primary": (28, 48, 36),
        "accent": (196, 149, 58),
        "accent_soft": (230, 208, 150),
        "bg": (246, 245, 240),
        "card_line": (220, 222, 210),
        "muted": (100, 108, 100),
    },
    {
        "name": "wine_rose",
        "primary": (64, 28, 40),
        "accent": (196, 120, 110),
        "accent_soft": (232, 190, 182),
        "bg": (248, 243, 241),
        "card_line": (230, 218, 214),
        "muted": (110, 95, 98),
    },
    {
        "name": "slate_sky",
        "primary": (30, 41, 59),
        "accent": (96, 165, 250),
        "accent_soft": (186, 214, 250),
        "bg": (241, 245, 249),
        "card_line": (210, 220, 230),
        "muted": (100, 110, 125),
    },
    {
        "name": "charcoal_lime",
        "primary": (24, 24, 27),
        "accent": (163, 230, 53),
        "accent_soft": (210, 240, 150),
        "bg": (250, 250, 249),
        "card_line": (228, 228, 231),
        "muted": (113, 113, 122),
    },
]

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


def _ellipsis(draw, text, font, max_width):
    text = (text or "").strip()
    if _text_width(draw, text, font) <= max_width:
        return text
    while text and _text_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text.rstrip(",.;- ") + "…"


def pick_theme(niche_id: str = "", rotate_key: int = 0) -> dict:
    """Rotate palette by niche index + day so posts differ across sectors."""
    day = datetime.now().timetuple().tm_yday
    niche_order = ("civil_works", "health", "ict", "works", "goods", "services")
    try:
        niche_i = niche_order.index(niche_id)
    except ValueError:
        niche_i = sum(ord(c) for c in (niche_id or "x"))
    return THEMES[(niche_i + day + rotate_key) % len(THEMES)]


def generate_digest_image(
    niche_label: str,
    tenders: list,
    output_path: str,
    max_items: int | None = None,
    niche_id: str = "",
) -> str:
    """Digest card showing only the tenders passed in (already capped by caller)."""
    import config as app_config

    max_items = max_items if max_items is not None else app_config.DIGEST_MAX_ITEMS
    shown = tenders[:max_items]
    theme = pick_theme(niche_id)
    primary = theme["primary"]
    accent = theme["accent"]
    accent_soft = theme["accent_soft"]
    bg = theme["bg"]
    card_line = theme["card_line"]
    muted = theme["muted"]

    img = Image.new("RGB", (CANVAS, CANVAS), bg)
    draw = ImageDraw.Draw(img)

    header_h = 150
    footer_h = 64
    margin = 40

    draw.rectangle([0, 0, CANVAS, header_h], fill=primary)
    draw.rectangle([0, header_h - 5, CANVAS, header_h], fill=accent)
    draw.text((margin, 22), BRAND, font=_font(FONT_BOLD, 17), fill=accent_soft)
    draw.text((margin, 54), niche_label, font=_font(FONT_BOLD, 34), fill=WHITE)
    today = datetime.now().strftime("%d %b %Y")
    sub = f"{len(shown)} tender{'s' if len(shown) != 1 else ''} · {today}"
    draw.text((margin, 104), sub, font=_font(FONT_REGULAR, 18), fill=accent_soft)

    body_top = header_h + 20
    body_bottom = CANVAS - footer_h - 12
    available = body_bottom - body_top
    n = max(len(shown), 1)
    row_gap = 10
    row_h = (available - row_gap * (n - 1)) // n
    row_h = max(118, min(row_h, 155))
    block = n * row_h + row_gap * (n - 1)
    if block < available:
        body_top += (available - block) // 2

    title_font = _font(FONT_BOLD, 20)
    meta_font = _font(FONT_REGULAR, 15)
    num_font = _font(FONT_BOLD, 17)

    for i, tender in enumerate(shown):
        fields = facebook_poster.extract_fields(tender)
        y = body_top + i * (row_h + row_gap)
        draw.rounded_rectangle(
            [margin, y, CANVAS - margin, y + row_h],
            radius=12,
            fill=WHITE,
            outline=card_line,
            width=1,
        )
        draw.rectangle([margin, y, margin + 6, y + row_h], fill=accent)

        cx, cy, cr = margin + 34, y + row_h // 2, 18
        draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=accent)
        num = str(i + 1)
        nb = draw.textbbox((0, 0), num, font=num_font)
        nw, nh = nb[2] - nb[0], nb[3] - nb[1]
        draw.text((cx - nw / 2, cy - nh / 2 - nb[1]), num, font=num_font, fill=primary)

        tx = margin + 62
        content_w = CANVAS - margin - tx - 18

        title = _ellipsis(
            draw,
            (tender.get("title") or "").strip() or "Untitled",
            title_font,
            content_w,
        )
        ty = y + 16
        draw.text((tx, ty), title, font=title_font, fill=primary)
        ty += 28

        dept = fields.get("department") or ""
        if dept:
            draw.text(
                (tx, ty),
                _ellipsis(draw, dept, meta_font, content_w),
                font=meta_font,
                fill=INK,
            )
            ty += 22 + 16  # blank line after organization

        city = fields["city"] or ""
        closes = facebook_poster._short_deadline(fields["deadline"] or "")
        security = fields.get("bid_security") or ""
        if security in ("Not listed", "N/A"):
            security = ""
        meta = " · ".join(p for p in (city, closes, security) if p)
        if meta:
            draw.text(
                (tx, ty),
                _ellipsis(draw, meta, meta_font, content_w),
                font=meta_font,
                fill=muted,
            )

    draw.rectangle([0, CANVAS - footer_h, CANVAS, CANVAS], fill=primary)
    foot = "Apply links in the post caption"
    fb = draw.textbbox((0, 0), foot, font=_font(FONT_REGULAR, 17))
    fw = fb[2] - fb[0]
    draw.text(
        ((CANVAS - fw) // 2, CANVAS - footer_h + 20),
        foot,
        font=_font(FONT_REGULAR, 17),
        fill=accent_soft,
    )

    img.save(output_path, "PNG", optimize=True)
    return output_path
