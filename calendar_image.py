from __future__ import annotations
from typing import List, Tuple
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # Railway (linux)da default font bo‘lmasligi mumkin, shuning uchun fallback bilan
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def render_ramadan_calendar_png(
    title: str,
    rows: List[Tuple[str, str, str]],  # (date, imsak, maghrib)
) -> BytesIO:
    """
    rows: list of (dd-mm-yyyy, HH:MM, HH:MM)
    return: BytesIO PNG
    """
    # Layout
    padding = 24
    line_h = 30
    header_h = 110
    col_w = [70, 170, 120, 140]  # Kun | Sana | Imsak | Maghrib
    table_w = sum(col_w)
    table_h = line_h * (len(rows) + 1)  # + header row
    w = table_w + padding * 2
    h = header_h + table_h + padding

    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)

    font_title = _get_font(28)
    font_small = _get_font(18)
    font_cell = _get_font(18)
    font_head = _get_font(18)

    # Title
    draw.text((padding, 20), title, font=font_title, fill="black")
    draw.text((padding, 60), "Ramazon taqvimi (Imsak / Maghrib)", font=font_small, fill="black")

    # Table position
    x0 = padding
    y0 = header_h

    # Header row background
    draw.rectangle([x0, y0, x0 + table_w, y0 + line_h], outline="black", fill="#f2f2f2")

    headers = ["Kun", "Sana", "Imsak", "Maghrib"]
    x = x0
    for i, text in enumerate(headers):
        draw.text((x + 10, y0 + 6), text, font=font_head, fill="black")
        x += col_w[i]

    # Rows
    for idx, (date_str, imsak, magh) in enumerate(rows, start=1):
        y = y0 + line_h * idx
        # zebra
        if idx % 2 == 0:
            draw.rectangle([x0, y, x0 + table_w, y + line_h], fill="#fbfbfb")

        values = [f"{idx:02d}", date_str, imsak, magh]

        x = x0
        for i, val in enumerate(values):
            draw.text((x + 10, y + 6), val, font=font_cell, fill="black")
            x += col_w[i]

        # row line
        draw.line([x0, y, x0 + table_w, y], fill="black")

    # Borders + vertical lines
    draw.rectangle([x0, y0, x0 + table_w, y0 + table_h], outline="black")
    x = x0
    for wcol in col_w[:-1]:
        x += wcol
        draw.line([x, y0, x, y0 + table_h], fill="black")

    # Output
    bio = BytesIO()
    bio.name = "ramazon_taqvim.png"
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio
