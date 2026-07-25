#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pillow"]
# ///

import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SCALE = 1.5
CANVAS_WIDTH = 2000
CANVAS_HEIGHT = 1150
OUTPUT_PATH = pathlib.Path(__file__).parent / "memory-maintenance.png"
FONT_PATH = "/System/Library/Fonts/SFNS.ttf"

image = Image.new(
    "RGBA",
    (round(CANVAS_WIDTH * SCALE), round(CANVAS_HEIGHT * SCALE)),
    "#07101D",
)
drawing = ImageDraw.Draw(image)
font_cache: dict[tuple[int, str], ImageFont.FreeTypeFont] = {}


def scaled(value: float) -> int:
    return round(value * SCALE)


def point(coordinates: tuple[float, float]) -> tuple[int, int]:
    return scaled(coordinates[0]), scaled(coordinates[1])


def rectangle(
    coordinates: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    return tuple(scaled(value) for value in coordinates)  # type: ignore[return-value]


def font(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    key = size, weight
    if key not in font_cache:
        selected_font = ImageFont.truetype(FONT_PATH, scaled(size))
        selected_font.set_variation_by_name(weight.encode())
        font_cache[key] = selected_font
    return font_cache[key]


def text_width(content: str, size: int, weight: str) -> float:
    return drawing.textlength(content, font=font(size, weight)) / SCALE


def text(
    coordinates: tuple[float, float],
    content: str,
    size: int,
    color: str | tuple[int, int, int, int],
    weight: str = "Regular",
    anchor: str = "lt",
) -> None:
    drawing.text(
        point(coordinates),
        content,
        fill=color,
        font=font(size, weight),
        anchor=anchor,
    )


def rounded_box(
    coordinates: tuple[float, float, float, float],
    fill: str | tuple[int, int, int, int] | None,
    outline: str | None,
    radius: int,
    outline_width: int = 2,
    shadow: bool = False,
) -> None:
    if shadow:
        shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_drawing = ImageDraw.Draw(shadow_layer)
        shadow_coordinates = (
            coordinates[0],
            coordinates[1] + 8,
            coordinates[2],
            coordinates[3] + 8,
        )
        shadow_drawing.rounded_rectangle(
            rectangle(shadow_coordinates),
            radius=scaled(radius),
            fill=(0, 0, 0, 90),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(scaled(12)))
        image.alpha_composite(shadow_layer)

    drawing.rounded_rectangle(
        rectangle(coordinates),
        radius=scaled(radius),
        fill=fill,
        outline=outline,
        width=scaled(outline_width),
    )


def circle(
    center: tuple[float, float],
    radius: float,
    fill: str,
    outline: str | None = None,
    outline_width: int = 1,
) -> None:
    coordinates = (
        center[0] - radius,
        center[1] - radius,
        center[0] + radius,
        center[1] + radius,
    )
    drawing.ellipse(
        rectangle(coordinates),
        fill=fill,
        outline=outline,
        width=scaled(outline_width),
    )


def pill(
    coordinates: tuple[float, float, float, float],
    content: str,
    fill: str,
    outline: str,
    text_color: str,
    size: int = 14,
) -> None:
    rounded_box(coordinates, fill, outline, 18, 1)
    text(
        ((coordinates[0] + coordinates[2]) / 2, (coordinates[1] + coordinates[3]) / 2),
        content,
        size,
        text_color,
        "Semibold",
        "mm",
    )


def arrow(
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: int = 4,
    head_length: int = 12,
) -> None:
    drawing.line([point(start), point(end)], fill=color, width=scaled(width))
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    left = (
        end[0] - head_length * math.cos(angle - 0.55),
        end[1] - head_length * math.sin(angle - 0.55),
    )
    right = (
        end[0] - head_length * math.cos(angle + 0.55),
        end[1] - head_length * math.sin(angle + 0.55),
    )
    drawing.polygon([point(end), point(left), point(right)], fill=color)


def dashed_line(
    start: tuple[float, float],
    end: tuple[float, float],
    color: str | tuple[int, int, int, int],
    width: int = 2,
    dash: float = 7,
    gap: float = 5,
) -> None:
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    if length == 0:
        return
    unit = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
    travelled = 0.0
    while travelled < length:
        segment_end = min(travelled + dash, length)
        drawing.line(
            [
                point((start[0] + unit[0] * travelled, start[1] + unit[1] * travelled)),
                point(
                    (start[0] + unit[0] * segment_end, start[1] + unit[1] * segment_end)
                ),
            ],
            fill=color,
            width=scaled(width),
        )
        travelled = segment_end + gap


def dashed_rectangle(
    coordinates: tuple[float, float, float, float],
    color: str | tuple[int, int, int, int],
    width: int = 2,
) -> None:
    left, top, right, bottom = coordinates
    dashed_line((left, top), (right, top), color, width)
    dashed_line((right, top), (right, bottom), color, width)
    dashed_line((right, bottom), (left, bottom), color, width)
    dashed_line((left, bottom), (left, top), color, width)


def zigzag(
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: int = 3,
    segments: int = 4,
    amplitude: float = 7,
) -> None:
    length = math.hypot(end[0] - start[0], end[1] - start[1])
    unit = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
    normal = (-unit[1], unit[0])
    points = [start]
    for index in range(1, segments):
        along = index / segments
        side = amplitude if index % 2 else -amplitude
        points.append(
            (
                start[0] + unit[0] * length * along + normal[0] * side,
                start[1] + unit[1] * length * along + normal[1] * side,
            )
        )
    points.append(end)
    drawing.line([point(p) for p in points], fill=color, width=scaled(width))


def leader(
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int, int],
) -> None:
    drawing.line([point(start), point(end)], fill=color, width=scaled(2))
    circle(end, 3, color)  # type: ignore[arg-type]


def strike(bbox: tuple[float, float, float, float], color: str) -> None:
    middle = (bbox[1] + bbox[3]) / 2
    drawing.line(
        [point((bbox[0] + 8, middle)), point((bbox[2] - 8, middle))],
        fill=color,
        width=scaled(2),
    )


def swap_badge(center: tuple[float, float], color: str, vertical: bool) -> None:
    if vertical:
        arrow((center[0] - 4, center[1] + 8), (center[0] - 4, center[1] - 8), color, 2, 6)
        arrow((center[0] + 4, center[1] - 8), (center[0] + 4, center[1] + 8), color, 2, 6)
    else:
        arrow((center[0] - 8, center[1] - 4), (center[0] + 8, center[1] - 4), color, 2, 6)
        arrow((center[0] + 8, center[1] + 4), (center[0] - 8, center[1] + 4), color, 2, 6)


def double_headed_line(
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: int = 2,
) -> None:
    arrow(start, end, color, width, 9)
    arrow(end, start, color, width, 9)


def vertical_text(
    left: float,
    center_y: float,
    content: str,
    size: int,
    color: str,
    weight: str = "Medium",
) -> None:
    used_font = font(size, weight)
    bbox = drawing.textbbox((0, 0), content, font=used_font)
    temp = Image.new("RGBA", (bbox[2] + 4, bbox[3] + 4), (0, 0, 0, 0))
    ImageDraw.Draw(temp).text((0, 0), content, fill=color, font=used_font)
    rotated = temp.transpose(Image.Transpose.ROTATE_90)
    image.alpha_composite(
        rotated,
        (scaled(left), scaled(center_y) - rotated.height // 2),
    )


CHIP_STYLES: dict[str, tuple[str, str, str]] = {
    "slate": ("#24334D", "#3A4D6E", "#93A5C2"),
    "teal": ("#123F44", "#2DD4BF", "#7DE8DC"),
    "red": ("#42191F", "#F87171", "#FCA5A5"),
    "rose": ("#3A1220", "#FB7185", "#FDA4AF"),
    "green": ("#12351F", "#34D399", "#6EE7B7"),
    "purple": ("#2A1F49", "#8B5CF6", "#C4B5FD"),
    "gold": ("#3A2E10", "#F59E0B", "#FCD34D"),
    "sky": ("#0F2C42", "#38BDF8", "#7DD3FC"),
}


def chip(
    x: float,
    y: float,
    label: str,
    style: str,
    *,
    width: float | None = None,
    height: float = 34,
    size: int = 13,
    ghost: bool = False,
    struck: bool = False,
    dashed_style: bool = False,
    loud: bool = False,
) -> tuple[float, float, float, float]:
    weight = "Bold" if loud else "Semibold"
    chip_width = width if width is not None else text_width(label, size, weight) + 26
    bbox = (x, y, x + chip_width, y + height)

    if loud:
        rounded_box(bbox, "#F43F5E", "#FB7185", 12, 2)
        text(((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2), label, size, "#FFF1F2", "Bold", "mm")
        return bbox

    fill, outline, text_color = CHIP_STYLES[style]
    if ghost:
        rounded_box(bbox, (36, 48, 70, 70), "#44546F", 10, 1)
        text_color = "#7C8CA6"
    elif dashed_style:
        drawing.rounded_rectangle(rectangle(bbox), radius=scaled(10), fill="#2B2410")
        dashed_rectangle(bbox, outline, 2)
    else:
        rounded_box(bbox, fill, outline, 10, 1)

    text(((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2), label, size, text_color, weight, "mm")
    if struck:
        strike(bbox, "#93A5C2" if ghost else "#E2E8F0")
    return bbox


def doc_card(
    coordinates: tuple[float, float, float, float],
    name: str,
    kind: str,
    ad_hoc: bool = False,
) -> None:
    kind_colors = {"ledger": "#2DD4BF", "readme": "#60A5FA", "agents": "#F59E0B", "adhoc": "#8B97AB"}
    if ad_hoc:
        rounded_box(coordinates, "#0E1626", None, 10, 0, True)
        dashed_rectangle(coordinates, "#5B6B85", 2)
        circle((coordinates[0] + 30, coordinates[1] + 26), 6, "#0E1626", kind_colors["adhoc"], 2)
    else:
        rounded_box(coordinates, "#101B2E", "#2A3951", 12, 2, True)
        circle((coordinates[0] + 30, coordinates[1] + 26), 6, kind_colors[kind])
    text(
        (coordinates[0] + 46, coordinates[1] + 18),
        name,
        15,
        "#D7E1EF" if not ad_hoc else "#9DA9BC",
        "Semibold",
    )


# ------------------------------------------------------------------ title zone
circle((112, 95), 29, "#2DD4BF")
text((112, 95), "2", 24, "#062229", "Bold", "mm")
text((165, 67), "SEMANTIC EVOLUTION — A MEMORY-MAINTENANCE PASS", 40, "#F8FAFC", "Bold")
text(
    (165, 124),
    "Two weeks of docs decomposed into information vectors — repaired, decayed, and re-homed on the two-axis MECE grid.",
    21,
    "#A9B8CC",
)
pill((1560, 73, 1930, 116), "PROJECT MEMORY · INFORMATION VECTORS", "#101B2C", "#2A3951", "#9FB0C8", 13)

# ------------------------------------------------------------------ panels
rounded_box((60, 190, 870, 1000), "#0B1525", "#503449", 28, 2, True)
circle((102, 232), 7, "#F87171")
text((122, 222), "AS ACCUMULATED · WEEKS 1–2", 18, "#FCA5A5", "Bold")
text((122, 250), "seven organically-grown docs — every one a mixed bag", 14, "#8FA0B8")

rounded_box((1130, 190, 1940, 1000), "#0B1525", "#2C5445", 28, 2, True)
circle((1172, 232), 7, "#34D399")
text((1192, 222), "AFTER THE PASS · MECE RESTORED", 18, "#6EE7B7", "Bold")
text((1192, 250), "every vector in exactly one (level × lens) cell", 14, "#8FA0B8")

# ------------------------------------------------------------------ BEFORE docs
doc_card((85, 290, 435, 408), "AGENTS.md · root", "agents")
chip(105, 340, "rules: style", "slate")
chip(240, 340, "uv-only", "slate")

doc_card((475, 282, 835, 420), "README.md · root", "readme")
chip(495, 332, "stack map", "slate")
chip(610, 332, "setup", "slate")
readme_leak = chip(495, 376, "why B > A", "teal")
text((readme_leak[2] + 10, 383), "→ LEDGER", 12, "#7DD3FC", "Semibold")

doc_card((80, 445, 460, 613), "LEDGER.md · root", "ledger")
contra_a = chip(100, 495, "IAP: open", "red", width=98)
dup_one = chip(208, 495, "sync → 02:00", "teal", width=125)
contra_b = chip(100, 543, "IAP: closed", "red", width=112)
leak_vertical = chip(222, 543, "mapping fix", "slate", width=112)
swap_badge((leak_vertical[2] - 2, leak_vertical[1] + 2), "#38BDF8", True)
text((leak_vertical[0], 581), "→ meta/", 12, "#7DD3FC", "Semibold")
text((100, 583), "contradiction", 12, "#F87171", "Semibold")
zigzag((contra_a[0] + 44, contra_a[3]), (contra_b[0] + 56, contra_b[1]), "#F87171", 3)

doc_card((500, 470, 830, 588), "meta/LEDGER.md", "ledger")
chip(520, 520, "runs log", "slate")
chip(618, 520, "tools", "slate")

doc_card((80, 650, 460, 818), "outreach/LEDGER.md", "ledger")
hypothesis = chip(100, 700, "H? pos-basket", "gold", width=130, dashed_style=True)
dup_two = chip(240, 700, "sync → 02:00", "teal", width=125)
reversal_old = chip(100, 748, "Sheets", "purple", width=80)
reversal_new = chip(190, 748, "→ DB", "purple", width=70)
chip(270, 748, "iter2", "slate", width=70)

doc_card((488, 645, 838, 795), "26-07-12-HANDOFF.md", "ledger", ad_hoc=True)
dup_three = chip(508, 695, "sync → 02:00", "teal", width=125)
chip(643, 695, "next steps", "slate")
chip(508, 739, "!!! DON'T TOUCH PROD !!!", "rose", width=220, height=44, size=14, loud=True)

doc_card((170, 850, 570, 990), "26-07-19-plan.md", "ledger", ad_hoc=True)
false_claim = chip(190, 896, "✗ v2 shipped", "rose", width=120)
chip(320, 896, "phases", "slate")
chip(190, 940, "!!! DON'T TOUCH PROD !!!", "rose", width=220, height=44, size=14, loud=True)

# duplicate rail
TEAL_SOFT = (45, 212, 191, 150)
drawing.line([point((420, 512)), point((420, 717))], fill=TEAL_SOFT, width=scaled(2))
drawing.line([point((dup_one[2], 512)), point((420, 512))], fill=TEAL_SOFT, width=scaled(2))
drawing.line([point((dup_two[2], 717)), point((420, 717))], fill=TEAL_SOFT, width=scaled(2))
drawing.line(
    [point((420, 632)), point((570, 632)), point((570, dup_three[1]))],
    fill=TEAL_SOFT,
    width=scaled(2),
)
circle((dup_one[2], 512), 3, "#2DD4BF")
circle((dup_two[2], 717), 3, "#2DD4BF")
circle((570, dup_three[1]), 3, "#2DD4BF")
text((470, 606), "same fact · three homes", 12, "#2DD4BF", "Semibold")

# annotations
PURPLE_SOFT = (167, 139, 250, 160)
ROSE_SOFT = (251, 113, 133, 160)
text((100, 824), "both still asserted", 12, "#A78BFA", "Semibold")
leader((175, 822), ((reversal_old[2] + reversal_new[0]) / 2, reversal_old[3] + 2), PURPLE_SOFT)
text((360, 824), "false claim", 12, "#FB7185", "Semibold")
leader((395, 842), (false_claim[2] - 6, false_claim[1] - 2), ROSE_SOFT)
text((590, 808), "yelling — same warning, twice, loud", 12, "#FB7185", "Semibold")
leader((620, 806), (618, 785), ROSE_SOFT)

# ------------------------------------------------------------------ middle: the pass
arrow((874, 480), (906, 480), "#55677F", 3)
arrow((1094, 480), (1126, 480), "#55677F", 3)

rounded_box((908, 330, 1092, 750), "#101B2C", "#27364E", 20, 2, True)
text((1000, 356), "MAINTENANCE", 16, "#E6EDF7", "Bold", "mm")
text((1000, 382), "PASS · 26-07-24", 12, "#8FA0B8", "Medium", "mm")
operations = [
    ("decompose", "#93A5C2"),
    ("dedupe", "#2DD4BF"),
    ("resolve", "#F87171"),
    ("prune", "#FB7185"),
    ("promote", "#34D399"),
    ("supersede", "#A78BFA"),
    ("relocate", "#38BDF8"),
    ("calm", "#F9A8D4"),
]
for index, (operation, color) in enumerate(operations):
    row_y = 424 + index * 39
    circle((944, row_y + 8), 5, color)
    text((962, row_y), operation, 15, "#C6D2E2", "Medium")

arrow((1000, 752), (1000, 788), "#55677F", 3)
dashed_rectangle((908, 792, 1092, 962), "#55677F", 2)
text((1000, 808), "PRUNED", 13, "#FB7185", "Bold", "mm")
pruned_one = chip(935, 826, "✗ v2 shipped", "rose", width=130, ghost=True, struck=True)
pruned_two = chip(925, 872, "stale dead-end", "slate", width=150, ghost=True, struck=True)
text((1000, 922), "falsehood decay ·", 11, "#71849E", "Regular", "mm")
text((1000, 938), "third-phase removal", 11, "#71849E", "Regular", "mm")

# ------------------------------------------------------------------ AFTER grid
text((1605, 272), "HORIZONTAL — one lens per doc type", 12, "#93A5C2", "Medium", "mm")
double_headed_line((1290, 292), (1920, 292), "#55677F", 2)
vertical_text(1136, 657, "VERTICAL — one owner level", 12, "#93A5C2")
double_headed_line((1254, 362), (1254, 952), "#55677F", 2)

column_lefts = [1268, 1490, 1712]
column_names = [
    ("LEDGER", "events · why · time", "#2DD4BF"),
    ("README", "present · what-is", "#60A5FA"),
    ("AGENTS", "durable rules", "#F59E0B"),
]
for column_left, (column_name, column_lens, column_color) in zip(column_lefts, column_names):
    circle((column_left + 10, 322), 6, column_color)
    text((column_left + 26, 314), column_name, 15, "#D7E1EF", "Bold")
    text((column_left + 26, 336), column_lens, 11, "#7F91AA")

row_tops = [362, 562, 762]
row_names = ["root /", "outreach /", "meta /"]
for row_top, row_name in zip(row_tops, row_names):
    text((1240, row_top + 88), row_name, 15, "#B9C6DA", "Semibold", "rm")

for row_top in row_tops:
    for column_left in column_lefts:
        rounded_box((column_left, row_top, column_left + 210, row_top + 190), "#0D1930", "#22314A", 14, 2)

for empty_cell in [(1712, 562), (1490, 762), (1712, 762)]:
    text((empty_cell[0] + 105, empty_cell[1] + 95), "·", 26, "#33435E", "Regular", "mm")

# (root, LEDGER)
relocated_why = chip(1284, 378, "why B > A", "teal", width=110)
swap_badge((relocated_why[2] - 2, relocated_why[1] + 2), "#38BDF8", False)
text((1284, 416), "from README /", 11, "#7DD3FC", "Semibold")
ghost_iap = chip(1284, 440, "IAP: open", "red", width=100, ghost=True, struck=True)
text((ghost_iap[2] + 8, 448), "superseded", 11, "#A78BFA", "Semibold")
chip(1284, 484, "schema", "slate", width=85)

# (root, README)
chip(1506, 378, "stack map", "slate")
chip(1506, 420, "setup", "slate")

# (root, AGENTS)
chip(1728, 378, "✓ IAP fails closed", "gold", width=178)
text((1728, 416), "phase-out::never", 11, "#FCD34D", "Semibold")
chip(1728, 440, "prod: read-only", "slate", width=148)
text((1728, 478), "calmed — was !!! ×2", 11, "#F9A8D4", "Semibold")

# (outreach, LEDGER)
chip(1284, 578, "sync → 02:00", "teal", width=130)
text((1284, 616), "merged ×3 → 1", 11, "#7DE8DC", "Semibold")
chip(1284, 640, "✓ pos-basket", "green", width=128)
text((1284, 678), "was H?", 11, "#FCD34D", "Semibold")
after_sheets = chip(1284, 702, "Sheets", "purple", width=80, ghost=True, struck=True)
arrow((after_sheets[2] + 4, 719), (after_sheets[2] + 26, 719), "#A78BFA", 2, 8)
chip(after_sheets[2] + 30, 702, "DB", "purple", width=58)

# (outreach, README)
chip(1506, 578, "brick2 how-to", "slate", width=138)

# (meta, LEDGER)
relocated_mapping = chip(1284, 778, "mapping fix", "slate", width=118)
swap_badge((relocated_mapping[2] - 2, relocated_mapping[1] + 2), "#38BDF8", True)
text((1284, 816), "from root /", 11, "#7DD3FC", "Semibold")
chip(1284, 840, "runs log", "slate", width=100)
chip(1284, 884, "tools", "slate", width=75)

# absorbed ad-hoc docs
absorbed_one = (1268, 958, 1368, 984)
absorbed_two = (1380, 958, 1452, 984)
dashed_rectangle(absorbed_one, "#4A5B78", 1)
dashed_rectangle(absorbed_two, "#4A5B78", 1)
text((1318, 971), "HANDOFF", 11, "#7C8CA6", "Medium", "mm")
text((1416, 971), "plan", 11, "#7C8CA6", "Medium", "mm")
strike(absorbed_one, "#7C8CA6")
strike(absorbed_two, "#7C8CA6")
text((1466, 964), "absorbed — no doc outside the axes", 13, "#71849E")

# ------------------------------------------------------------------ footer key
text((70, 1032), "KEY", 13, "#6F829D", "Bold")
key_chip = chip(70, 1056, "vector", "slate", width=78)
text((key_chip[2] + 10, 1064), "steady", 13, "#7F91AA")
key_hypothesis = chip(240, 1056, "H?", "gold", width=52, dashed_style=True)
text((key_hypothesis[2] + 10, 1064), "hypothesis", 13, "#7F91AA")
key_evidence = chip(430, 1056, "✓", "green", width=48)
text((key_evidence[2] + 10, 1064), "evidence", 13, "#7F91AA")
key_ghost = chip(610, 1056, "ghost", "slate", width=76, ghost=True, struck=True)
text((key_ghost[2] + 10, 1064), "superseded — kept, decayed", 13, "#7F91AA")
key_loud = chip(950, 1052, "!!!", "rose", width=64, height=42, loud=True)
text((key_loud[2] + 10, 1064), "over-weighted", 13, "#7F91AA")
text(
    (1940, 1064),
    "one pass · dups 3→1 · pruned 2 · promoted 1 · superseded 2 · relocated 2 · calmed 1",
    13,
    "#71849E",
    "Medium",
    "rt",
)

image.convert("RGB").save(OUTPUT_PATH, quality=95)
print(OUTPUT_PATH)
