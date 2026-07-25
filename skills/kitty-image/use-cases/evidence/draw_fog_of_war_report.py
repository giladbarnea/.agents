#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pillow"]
# ///
"""Evidence-board use case: a night of DB fog-of-war recon, reported as a territory map.

Visual grammar: brightness encodes epistemic state (mapped / partial / known-unknown /
fog = unknown-unknowns), every claim carries a confidence value, cyan marks tonight's
delta, red marks falsified hypotheses, amber marks quirks and pending verification.
"""

import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SCALE = 1.5
CANVAS_WIDTH = 2000
CANVAS_HEIGHT = 1260
OUTPUT_PATH = pathlib.Path(__file__).parent / "fog-of-war-report.png"
FONT_PATH = "/System/Library/Fonts/SFNS.ttf"

image = Image.new("RGBA", (round(CANVAS_WIDTH * SCALE), round(CANVAS_HEIGHT * SCALE)), "#060D18")
drawing = ImageDraw.Draw(image)
font_cache: dict[tuple[int, str], ImageFont.FreeTypeFont] = {}


def scaled(value: float) -> int:
    return round(value * SCALE)


def point(coordinates: tuple[float, float]) -> tuple[int, int]:
    return scaled(coordinates[0]), scaled(coordinates[1])


def rectangle(coordinates: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    return tuple(scaled(value) for value in coordinates)  # type: ignore[return-value]


def font(size: float, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    key = round(size * 10), weight
    if key not in font_cache:
        selected = ImageFont.truetype(FONT_PATH, scaled(size))
        selected.set_variation_by_name(weight.encode())
        font_cache[key] = selected
    return font_cache[key]


def text(
    coordinates: tuple[float, float],
    content: str,
    size: float,
    color: str,
    weight: str = "Regular",
    anchor: str = "lt",
) -> None:
    drawing.text(point(coordinates), content, fill=color, font=font(size, weight), anchor=anchor)


def rounded_box(
    coordinates: tuple[float, float, float, float],
    fill: str | None,
    outline: str | None,
    radius: float,
    outline_width: float = 2,
) -> None:
    drawing.rounded_rectangle(
        rectangle(coordinates),
        radius=scaled(radius),
        fill=fill,
        outline=outline,
        width=scaled(outline_width),
    )


def glow_box(
    coordinates: tuple[float, float, float, float],
    color: tuple[int, int, int],
    radius: float,
    blur: float = 12,
    alpha: int = 170,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer_drawing = ImageDraw.Draw(layer)
    layer_drawing.rounded_rectangle(
        rectangle(coordinates), radius=scaled(radius), outline=(*color, alpha), width=scaled(5)
    )
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(scaled(blur))))


def circle(center: tuple[float, float], radius: float, fill: str) -> None:
    coordinates = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    drawing.ellipse(rectangle(coordinates), fill=fill)


def pill(
    coordinates: tuple[float, float, float, float],
    content: str,
    fill: str,
    outline: str,
    text_color: str,
    size: float = 12,
    weight: str = "Semibold",
) -> None:
    rounded_box(coordinates, fill, outline, (coordinates[3] - coordinates[1]) / 2, 1)
    center = ((coordinates[0] + coordinates[2]) / 2, (coordinates[1] + coordinates[3]) / 2)
    text(center, content, size, text_color, weight, "mm")


def line(
    start: tuple[float, float], end: tuple[float, float], color: str, width: float = 3
) -> None:
    drawing.line([point(start), point(end)], fill=color, width=scaled(width))


def arrow_head(tip: tuple[float, float], angle: float, color: str, length: float = 12) -> None:
    left = (tip[0] - length * math.cos(angle - 0.5), tip[1] - length * math.sin(angle - 0.5))
    right = (tip[0] - length * math.cos(angle + 0.5), tip[1] - length * math.sin(angle + 0.5))
    drawing.polygon([point(tip), point(left), point(right)], fill=color)


def arrow(
    start: tuple[float, float], end: tuple[float, float], color: str, width: float = 3
) -> None:
    line(start, end, color, width)
    arrow_head(end, math.atan2(end[1] - start[1], end[0] - start[0]), color)


def dash_offsets(length: float, dash: float, gap: float) -> list[tuple[float, float]]:
    """Return (start, end) offsets of dash segments covering a length.

    >>> dash_offsets(25, 8, 4)
    [(0.0, 8.0), (12.0, 20.0), (24.0, 25)]
    """
    offsets: list[tuple[float, float]] = []
    cursor = 0.0
    while cursor < length:
        offsets.append((cursor, min(cursor + dash, length)))
        cursor += dash + gap
    return offsets


def dashed_line(
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: float = 3,
    dash: float = 9,
    gap: float = 7,
) -> None:
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    if length == 0:
        return
    unit = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
    for segment_start, segment_end in dash_offsets(length, dash, gap):
        line(
            (start[0] + unit[0] * segment_start, start[1] + unit[1] * segment_start),
            (start[0] + unit[0] * segment_end, start[1] + unit[1] * segment_end),
            color,
            width,
        )


def dashed_rect(
    coordinates: tuple[float, float, float, float], color: str, width: float = 2
) -> None:
    left, top, right, bottom = coordinates
    dashed_line((left, top), (right, top), color, width)
    dashed_line((right, top), (right, bottom), color, width)
    dashed_line((right, bottom), (left, bottom), color, width)
    dashed_line((left, bottom), (left, top), color, width)


def chip(
    coordinates: tuple[float, float, float, float],
    label: str,
    fill: str = "#132C40",
    outline: str = "#38678A",
    text_color: str = "#DCEBF6",
    size: float = 15,
) -> None:
    rounded_box(coordinates, fill, outline, 10, 1.6)
    center = ((coordinates[0] + coordinates[2]) / 2, (coordinates[1] + coordinates[3]) / 2)
    text(center, label, size, text_color, "Semibold", "mm")


def ghost_chip(
    coordinates: tuple[float, float, float, float],
    label: str,
    text_color: str = "#6C87B4",
    size: float = 12,
) -> None:
    rounded_box(coordinates, "#0C1A2E", None, 9)
    dashed_rect(coordinates, "#2C4568", 1.6)
    center = ((coordinates[0] + coordinates[2]) / 2, (coordinates[1] + coordinates[3]) / 2)
    text(center, label, size, text_color, "Medium", "mm")


def confidence_bar(
    top_left: tuple[float, float], value: float, color: str, width: float = 72
) -> None:
    left, top = top_left
    rounded_box((left, top, left + width, top + 9), "#10233A", None, 4)
    rounded_box((left, top, left + width * value, top + 9), color, None, 4)
    text((left + width / 2, top + 15), f"{value:.2f}", 12, color, "Semibold", "mt")


def cross_mark(center: tuple[float, float], radius: float, color: str, width: float = 3) -> None:
    line((center[0] - radius, center[1] - radius), (center[0] + radius, center[1] + radius), color, width)
    line((center[0] - radius, center[1] + radius), (center[0] + radius, center[1] - radius), color, width)


def quirk_pin(center: tuple[float, float], radius: float = 11) -> None:
    top = (center[0], center[1] - radius)
    left = (center[0] - radius, center[1] + radius * 0.85)
    right = (center[0] + radius, center[1] + radius * 0.85)
    drawing.polygon([point(top), point(left), point(right)], fill="#F5B841")
    text((center[0], center[1] + 2.5), "!", 12, "#241B06", "Bold", "mm")


# ── Header ────────────────────────────────────────────────────────────────────
text((60, 42), "NIGHT RECON — DATABASE FOG-OF-WAR REPORT", 36, "#F2F7FC", "Bold")
text(
    (60, 100),
    "acme-erp replica · wave-6 debrief · 02:10–06:40 · 14 explorers + 9 falsifiers in pairs",
    18,
    "#93A9C2",
)
pill((1150, 52, 1340, 92), "41 hypotheses tested", "#0D1A2C", "#27384F", "#AFC2D9", 13)
pill((1360, 52, 1660, 92), "22 confirmed · 9 falsified · 10 open", "#0D1A2C", "#27384F", "#AFC2D9", 13)
pill((1680, 52, 1950, 92), "coverage 118/312 · +44 tonight", "#0A2430", "#1F5B57", "#5FE3D3", 13)

# ── Map panel ─────────────────────────────────────────────────────────────────
MAP = (50, 150, 1360, 1140)
rounded_box(MAP, "#081221", "#1C2C45", 26, 2)
text((86, 170), "TERRITORY MAP — THE SEARCH SPACE AS CURRENTLY BELIEVED", 13, "#5F7896", "Bold")

for grid_x in range(90, 1331, 62):
    for grid_y in range(215, 1126, 62):
        circle((grid_x, grid_y), 1.6, "#101F35")

# Ghost silhouettes that the fog will half-swallow (drawn before the fog layer).
for silhouette, label in [
    ((1150, 280, 1310, 320), "ARCHIVE_ORD_*"),
    ((1180, 340, 1330, 380), "ARCHIVE_INV_*"),
    ((1160, 405, 1300, 445), "ARCH_1997_*"),
    ((1150, 690, 1290, 730), "TRG_%  ?"),
    ((1180, 755, 1320, 795), "SP_%  ?"),
]:
    ghost_chip(silhouette, label, "#55688A", 12)

# ── Region: SALES CORE (known-known) ──────────────────────────────────────────
rounded_box((95, 225, 585, 555), "#0E2233", "#2E5E7E", 22, 2)
circle((121, 251), 5, "#5FC8E8")
text((135, 242), "SALES CORE", 16, "#BFE3F2", "Bold")
pill((395, 238, 567, 266), "mapped · high conf", "#0B2C33", "#1F5B57", "#7FE0D0", 12)

pill((215, 272, 465, 296), "CUSTNAME string FK · 0.97", "#0D2A3D", "#2E5E7E", "#A8D4EA", 12)
chip((125, 300, 325, 346), "ORDERS")
chip((355, 300, 555, 346), "CUSTOMERS")
line((325, 323), (355, 323), "#3E7EA6", 3)

line((225, 346), (225, 470), "#3E7EA6", 3)
pill((240, 395, 340, 421), "1–N · 0.99", "#0D2A3D", "#2E5E7E", "#A8D4EA", 12)
line((185, 346), (185, 445), "#3E7EA6", 3)
line((185, 445), (430, 445), "#3E7EA6", 3)
arrow((430, 445), (430, 470), "#3E7EA6", 3)

chip((125, 470, 325, 516), "ORDERITEMS")
glow_box((355, 470, 555, 516), (56, 225, 212), 10, 9, 150)
chip((355, 470, 555, 516), "AGENTS", "#0F3134", "#2FBFB0", "#C9F6F0")
pill((462, 452, 576, 478), "NEW · rep FK 0.95", "#0A2B2F", "#2FBFB0", "#7FE9DC", 11)

# ── Region: BILLING (cleared tonight) ─────────────────────────────────────────
glow_box((655, 225, 1075, 555), (56, 225, 212), 22, 14, 120)
rounded_box((655, 225, 1075, 555), "#0D2430", "#2FBFB0", 22, 2)
circle((681, 251), 5, "#5FE3D3")
text((695, 242), "BILLING", 16, "#C9F6F0", "Bold")
pill((860, 238, 1052, 266), "cleared tonight", "#0A2B2F", "#2FBFB0", "#7FE9DC", 12)

chip((685, 300, 885, 346), "INVOICES")
line((785, 346), (785, 470), "#3E7EA6", 3)
pill((800, 395, 905, 421), "1–N · 0.98", "#0D2A3D", "#2E5E7E", "#A8D4EA", 12)
chip((685, 470, 885, 516), "INVOICEITEMS")

line((885, 323), (980, 323), "#3E7EA6", 3)
dashed_line((980, 323), (980, 470), "#4A6C8E", 3)
pill((908, 390, 1052, 416), "0.60 · unverified", "#101E30", "#39536F", "#8FA9C4", 12)
ghost_chip((905, 470, 1055, 516), "PAYMENTS", "#8FA9C4", 14)
text((905, 524), "reconciliation path unclear", 11, "#7E93B5")

# Cross-island cause→effect (the night's most consequential finding).
arrow((585, 520), (655, 520), "#F5B841", 4)
circle((585, 520), 5, "#F5B841")
dashed_line((620, 528), (660, 566), "#8A6A2A", 2, 6, 5)
rounded_box((610, 566, 1040, 616), "#1A1408", "#8A6A2A", 12, 1.6)
text((628, 574), "CAUSE→EFFECT: DISCOUNT copied at print-time, not at close", 13, "#F5C863", "Semibold")
text((628, 594), "so late discount edits go stale · conf 0.85 · verifier pass #2 queued", 12, "#C9B075")

# Falsified wreck between the islands.
ghost_chip((150, 585, 330, 629), "ORDSTATUS", "#B98A90", 14)
line((160, 607), (320, 607), "#F4645C", 3)
cross_mark((347, 607), 8, "#F4645C", 3)
text((368, 586), "falsified tonight: not the live status lookup", 12, "#C08984", "Semibold")
text((368, 606), "0 app reads · rows stale since 2019", 12, "#8AA0BB")

# ── Region: INVENTORY (partially mapped) ──────────────────────────────────────
rounded_box((130, 640, 540, 940), "#0C1D2E", "#2E4A66", 22, 2)
circle((156, 666), 5, "#7FA8CC")
text((170, 657), "INVENTORY", 16, "#AFC9E0", "Bold")
pill((350, 652, 516, 680), "partial · 0.6–0.9", "#101E30", "#39536F", "#9FB6CE", 12)

chip((160, 712, 330, 758), "PARTS")
chip((360, 712, 520, 758), "STOCK")
quirk_pin((512, 708))

ghost_chip((160, 790, 520, 836), "SPEC1…SPEC12 — free text, meaning varies by family  ?", "#8FA9C4", 11.5)
rounded_box((160, 856, 520, 868), "#10233A", None, 6)
rounded_box((160, 856, 226, 868), "#2FBFB0", None, 6)
text((160, 878), "2 of 11 product families decoded tonight", 12, "#8AA0BB")
text((160, 902), "quirk: negative ONHAND = backorder marker · 0.88", 12, "#D9B26A")

# ── Region: T4xx cluster (known-unknown) ──────────────────────────────────────
rounded_box((680, 640, 1040, 900), "#0A1526", "#33507F", 22, 2)
text((960, 770), "?", 110, "#1B3355", "Bold", "mm")
circle((706, 666), 5, "#7C97C6")
text((720, 657), "T4xx CLUSTER", 16, "#AFC4E4", "Bold")
pill((868, 652, 1016, 680), "KNOWN-UNKNOWN", "#101C33", "#33507F", "#9DB4DA", 11)

ghost_chip((710, 716, 790, 752), "T431")
ghost_chip((800, 716, 880, 752), "T438")
ghost_chip((890, 716, 970, 752), "T44x")
text((978, 728), "+44", 12, "#5E76A0", "Medium")
text((710, 772), "T431–T447 · 47 tables · 1.2M rows", 13, "#9DB4DA")
text((710, 794), "opaque numeric codes · written nightly ~02:00", 13, "#9DB4DA")
text((710, 816), "zero app reads observed over 7 nights · 0.92", 13, "#9DB4DA")
text((710, 840), "› 6 hypotheses queued · expedition tomorrow 22:00", 13, "#5FE3D3", "Semibold")
text((710, 862), "top hypothesis: BI export staging (0.40, untested)", 12, "#6E85A3")

# ── Fog of war (unknown-unknowns) ─────────────────────────────────────────────
fog_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
fog_drawing = ImageDraw.Draw(fog_layer)
fog_blobs: list[tuple[float, float, float, float, tuple[int, int, int], int]] = [
    (1280, 300, 260, 220, (26, 37, 56), 205),
    (1300, 650, 280, 260, (26, 37, 56), 215),
    (1270, 980, 300, 240, (26, 37, 56), 205),
    (1180, 170, 200, 140, (26, 37, 56), 185),
    (1120, 480, 170, 300, (30, 42, 62), 150),
    (1150, 850, 190, 220, (30, 42, 62), 160),
    (1260, 560, 220, 160, (26, 37, 56), 205),
    (1230, 1060, 240, 170, (26, 37, 56), 200),
    (1060, 300, 160, 120, (38, 52, 76), 85),
    (1050, 720, 150, 140, (38, 52, 76), 85),
    (980, 1050, 220, 120, (38, 52, 76), 80),
    (860, 1135, 220, 70, (38, 52, 76), 75),
]
for center_x, center_y, radius_x, radius_y, fog_color, alpha in fog_blobs:
    fog_drawing.ellipse(
        rectangle((center_x - radius_x, center_y - radius_y, center_x + radius_x, center_y + radius_y)),
        fill=(*fog_color, alpha),
    )
fog_layer = fog_layer.filter(ImageFilter.GaussianBlur(scaled(34)))

fog_mask = Image.new("L", image.size, 0)
ImageDraw.Draw(fog_mask).rounded_rectangle(
    rectangle((MAP[0] + 4, MAP[1] + 4, MAP[2] - 4, MAP[3] - 4)), radius=scaled(24), fill=255
)
fog_alpha = fog_layer.split()[3].point(lambda value: value)
fog_layer.putalpha(Image.composite(fog_alpha, Image.new("L", image.size, 0), fog_mask))
image.alpha_composite(fog_layer)

# Frontier line and post-fog captions.
frontier_points = [(1102, 175), (1125, 350), (1085, 600), (1108, 860), (1065, 1135)]
for segment_start, segment_end in zip(frontier_points, frontier_points[1:]):
    dashed_line(segment_start, segment_end, "#6FA3C8", 3, 10, 8)
for vertex in frontier_points[1:-1]:
    circle(vertex, 4, "#6FA3C8")
pill((960, 186, 1215, 212), "FRONTIER @ 06:40 · +44 tables tonight", "#0A2430", "#2FBFB0", "#7FE9DC", 12)

for start, end in [((1080, 295), (1175, 285)), ((1080, 335), (1185, 330)), ((1080, 375), (1170, 378))]:
    arrow(start, end, "#E8A25B", 3)
text((1090, 400), "7 FK-like refs resolve into fog —", 12, "#B9C6DA", "Semibold")
text((1090, 420), "unknown-unknowns cast shadows", 12, "#93A9C4")

text((1120, 505), "ARCHIVE_* — 200+ tables, untouched", 12, "#6F84A6")
text((1130, 995), "UNKNOWN-UNKNOWNS", 15, "#7E93B5", "Bold")
text((1130, 1022), "cannot be listed — only shrunk", 12, "#5E7494")
text((1130, 1042), "by advancing the frontier", 12, "#5E7494")

ghost_chip((760, 955, 900, 995), "LOG_*", "#7E93B5", 13)
text((912, 968), "skimmed · low signal · 0.70", 12, "#6E85A3")

quirk_pin((105, 984))
text((124, 976), "cross-cutting quirk: dates are INT yyyymmdd in 61 tables, DATETIME in 40, one Excel-serial · 0.90", 13, "#D9B26A")
text((100, 1096), "this map is a belief-state, not ground truth — every edge carries confidence, not proof", 11, "#4A5F80")

# ── Sidebar ───────────────────────────────────────────────────────────────────
rounded_box((1390, 150, 1950, 1140), "#081221", "#1C2C45", 26, 2)

text((1418, 172), "CONFIRMED TONIGHT", 15, "#7FE0D0", "Bold")
text((1418, 196), "only claims that survived the falsifier gauntlet", 11, "#6E85A3")
confirmed: list[tuple[float, str, str, str]] = [
    (0.97, "#2FBFB0", "ORDERS.CUSTNAME = CUSTOMERS.CUSTNAME (string FK)", "triple-verified · 3 exceptions explained (merged customers)"),
    (0.93, "#2FBFB0", "soft-delete is STATUS = -9 · DELETED column is dead", "counterexample sweep over 48k rows found none"),
    (0.88, "#2FBFB0", "negative STOCK.ONHAND encodes backorders", "cross-checked against open purchase orders"),
    (0.85, "#F5B841", "invoice DISCOUNT copied at print-time (stale source)", "explains drift · verifier pass #2 queued"),
]
row_y = 228.0
for value, color, headline, detail in confirmed:
    text((1418, row_y), headline, 14, "#DFE9F5", "Semibold")
    text((1418, row_y + 22), detail, 12, "#8AA0BB")
    confidence_bar((1836, row_y + 2), value, color)
    row_y += 60

line((1418, 478), (1922, 478), "#16283E", 2)
text((1418, 496), "FALSIFIED TONIGHT", 15, "#F4938C", "Bold")
falsified: list[tuple[str, str]] = [
    ("ORDSTATUS is the live status lookup", "dead since 2019 · statuses are hardcoded in the app"),
    ("invoices are immutable after print", "312 post-print mutations found in 90-day window"),
]
row_y = 528.0
for headline, detail in falsified:
    text((1418, row_y), headline, 14, "#C9D4E4", "Semibold")
    headline_width = drawing.textlength(headline, font=font(14, "Semibold")) / SCALE
    line((1418, row_y + 9), (1418 + headline_width, row_y + 9), "#F4645C", 2)
    cross_mark((1880, row_y + 8), 8, "#F4645C", 3)
    text((1418, row_y + 22), detail, 12, "#8AA0BB")
    row_y += 56

line((1418, 648), (1922, 648), "#16283E", 2)
text((1418, 666), "OPEN QUESTIONS — KNOWN-UNKNOWNS", 15, "#9DB4DA", "Bold")
open_questions: list[tuple[str, str]] = [
    ("T4xx cluster purpose", "expedition tomorrow 22:00 · 6 hypotheses staged"),
    ("SPEC column semantics", "9 of 11 product families still undecoded"),
    ("PAYMENTS reconciliation path", "current belief 0.60 · needs a falsifier pair"),
]
row_y = 698.0
for headline, detail in open_questions:
    text((1424, row_y - 1), "?", 16, "#9DB4DA", "Bold")
    text((1450, row_y), headline, 14, "#DFE9F5", "Semibold")
    text((1450, row_y + 22), detail, 12, "#8AA0BB")
    row_y += 54

line((1418, 866), (1922, 866), "#16283E", 2)
text((1418, 884), "REPORTING POSTURE", 15, "#93A9C2", "Bold")
rounded_box((1418, 912, 1922, 1108), "#0B1830", "#1E3450", 14, 1.6)
for offset, posture_line in enumerate([
    "precision-first: assert only 0.85+ or triple-verified claims",
    "recall debt: 10 live hypotheses parked in the open queue",
    "coverage: 118 of 312 tables (38%) · frontier +44 tonight",
    "unknown-unknowns: acknowledged via fog · never enumerated",
    "next wave: 6 explorer-falsifier pairs into T4xx · 22:00",
]):
    text((1440, 934 + offset * 32), posture_line, 13, "#A9BCD4")

# ── Legend ────────────────────────────────────────────────────────────────────
rounded_box((50, 1160, 1950, 1238), "#081221", "#1C2C45", 20, 2)
legend_y = 1186.0
cursor_x = 92.0


def legend_label(content: str) -> None:
    global cursor_x
    text((cursor_x, legend_y + 2), content, 13, "#93A9C2")
    cursor_x += drawing.textlength(content, font=font(13)) / SCALE + 38


rounded_box((cursor_x, legend_y, cursor_x + 26, legend_y + 16), "#132C40", "#38678A", 5, 1.4)
cursor_x += 36
legend_label("mapped · known-known")
dashed_rect((cursor_x, legend_y, cursor_x + 26, legend_y + 16), "#2C4568", 1.4)
cursor_x += 36
legend_label("partial")
text((cursor_x + 6, legend_y + 1), "?", 15, "#9DB4DA", "Bold")
cursor_x += 24
legend_label("known-unknown")
rounded_box((cursor_x, legend_y - 1, cursor_x + 26, legend_y + 17), "#26344E", None, 8)
cursor_x += 36
legend_label("fog · unknown-unknowns")
rounded_box((cursor_x, legend_y, cursor_x + 26, legend_y + 16), "#0F3134", "#2FBFB0", 5, 1.6)
cursor_x += 36
legend_label("cleared tonight")
cross_mark((cursor_x + 9, legend_y + 8), 7, "#F4645C", 3)
cursor_x += 28
legend_label("falsified")
quirk_pin((cursor_x + 10, legend_y + 8), 9)
cursor_x += 30
legend_label("quirk")
rounded_box((cursor_x, legend_y + 4, cursor_x + 40, legend_y + 12), "#10233A", None, 4)
rounded_box((cursor_x, legend_y + 4, cursor_x + 30, legend_y + 12), "#2FBFB0", None, 4)
cursor_x += 50
legend_label("confidence 0–1")

image.convert("RGB").save(OUTPUT_PATH, quality=95)
print(OUTPUT_PATH)
