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
CANVAS_HEIGHT = 1120
OUTPUT_PATH = pathlib.Path(__file__).parent / "order-journey.png"
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


def text(
    coordinates: tuple[float, float],
    content: str,
    size: int,
    color: str,
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
    fill: str,
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
            coordinates[1] + 9,
            coordinates[2],
            coordinates[3] + 9,
        )
        shadow_drawing.rounded_rectangle(
            rectangle(shadow_coordinates),
            radius=scaled(radius),
            fill=(0, 0, 0, 95),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(scaled(14)))
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
    head_length: int = 13,
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


def check_mark(center: tuple[float, float], size: float, color: str, width: int = 3) -> None:
    points = [
        (center[0] - size * 0.55, center[1] + size * 0.05),
        (center[0] - size * 0.12, center[1] + size * 0.5),
        (center[0] + size * 0.6, center[1] - size * 0.5),
    ]
    drawing.line([point(p) for p in points], fill=color, width=scaled(width), joint="curve")


def chat_bubble(
    left: float,
    top: float,
    right: float,
    lines: list[str],
    outgoing: bool,
) -> float:
    height = 26 + len(lines) * 22
    fill = "#005C4B" if outgoing else "#1F2C34"
    text_color = "#E7FFDB" if outgoing else "#E9EDEF"
    rounded_box((left, top, right, top + height), fill, None, 12, 0)
    for index, line in enumerate(lines):
        text((left + 15, top + 13 + index * 22), line, 14, text_color)
    return top + height


FRAME_WIDTH = 560
FRAME_TOP = 190
FRAME_BOTTOM = 990
frame_lefts = [70, 720, 1370]

text((70, 52), "ORDER JOURNEY — A PROTOTYPE", 40, "#F8FAFC", "Bold")
text(
    (70, 114),
    "One WhatsApp order, end to end, through the proposed flow. Deliberately concrete — correct what's wrong.",
    21,
    "#A9B8CC",
)
pill((1660, 60, 1930, 104), "PROTOTYPE · FUTURE STATE", "#101B2C", "#2A3951", "#9FB0C8", 14)

for frame_left in frame_lefts:
    rounded_box(
        (frame_left, FRAME_TOP, frame_left + FRAME_WIDTH, FRAME_BOTTOM),
        "#0B1525",
        "#27364E",
        28,
        2,
        True,
    )

frame_chips = [
    ("FRAME 1", "#0E2B1E", "#2E9E64", "#7CE3A9"),
    ("FRAME 2", "#0B252C", "#2DD4BF", "#5EEAD4"),
    ("FRAME 3", "#0E2334", "#3392C8", "#7CCBF2"),
]
frame_times = ["THU 08:52", "THU 08:53", "SUN 07:10"]
frame_places = [
    "CUSTOMER'S PHONE · WHATSAPP",
    "BACK OFFICE · ORDER SCREEN",
    "SUNDAY ROUTE · DRIVER'S PHONE",
]
for index, frame_left in enumerate(frame_lefts):
    chip_text, chip_fill, chip_outline, chip_color = frame_chips[index]
    pill((frame_left + 40, 218, frame_left + 150, 254), chip_text, chip_fill, chip_outline, chip_color, 13)
    text((frame_left + 168, 216), frame_times[index], 21, "#E6EDF7", "Semibold")
    text((frame_left + 168, 248), frame_places[index], 13, chip_color, "Medium")


frame_one_left = frame_lefts[0]
phone_left = frame_one_left + 100
phone_right = frame_one_left + 460
rounded_box((phone_left, 300, phone_right, 870), "#0B141A", "#233138", 24, 2, True)
rounded_box((phone_left + 3, 303, phone_right - 3, 372), "#1F2C34", None, 22, 0)
drawing.rectangle(rectangle((phone_left + 3, 340, phone_right - 3, 372)), fill="#1F2C34")
circle((phone_left + 38, 336), 18, "#5A6B75")
text((phone_left + 38, 336), "B", 16, "#E9EDEF", "Bold", "mm")
text((phone_left + 66, 316), "Ben-Ami Orders", 16, "#E9EDEF", "Semibold")
text((phone_left + 66, 342), "WhatsApp Business · online", 12, "#8696A0")

bubble_bottom = chat_bubble(
    phone_left + 84,
    400,
    phone_right - 16,
    [
        "Boker tov! For Sunday:",
        "24 × Osem pasta 500g",
        "60 × Tara milk 3% 1L",
        "12 × Elite coffee 200g",
        "2 cases Sugat rice 1kg",
    ],
    True,
)
bubble_bottom = chat_bubble(
    phone_left + 16,
    bubble_bottom + 16,
    phone_left + 290,
    [
        "Got it. Order ORD-7241:",
        "4 lines · total ₪2,346",
        "Delivery Sun 07:00–07:30",
        "Reply 1 to confirm",
    ],
    False,
)
bubble_bottom = chat_bubble(phone_right - 72, bubble_bottom + 16, phone_right - 16, ["1"], True)
bubble_bottom = chat_bubble(
    phone_left + 16,
    bubble_bottom + 16,
    phone_left + 268,
    ["Confirmed. See you Sunday"],
    False,
)
check_mark((phone_left + 234, bubble_bottom - 23), 7, "#53BDEB", 2)
check_mark((phone_left + 243, bubble_bottom - 23), 7, "#53BDEB", 2)

text((frame_one_left + 40, 903), "A normal message. No app, no form.", 15, "#D1DCEB", "Semibold")
circle((frame_one_left + 46, 947), 4, "#2DD4BF")
text((frame_one_left + 62, 938), "the bot parses it as it arrives", 13, "#7F91AA")


frame_two_left = frame_lefts[1]
card_left = frame_two_left + 40
card_right = frame_two_left + 520
rounded_box((card_left, 300, card_right, 800), "#F4F8FD", "#C9D6E4", 18, 2, True)
text((card_left + 30, 328), "ORD-7241 · Makolet HaTzafon", 20, "#0B2537", "Bold")
text((card_left + 30, 362), "WhatsApp Thu 08:52 · parsed automatically 08:53", 13, "#5B7186")
drawing.line([point((card_left + 30, 396)), point((card_right - 30, 396))], fill="#D8E2EC", width=scaled(2))

order_rows = [
    ("Osem pasta 500g", "× 24", "132 in stock"),
    ("Tara milk 3% 1L", "× 60", "in stock"),
]
for index, (item_name, quantity, status) in enumerate(order_rows):
    row_top = 418 + index * 58
    text((card_left + 30, row_top), item_name, 16, "#17344A", "Semibold")
    text((card_left + 262, row_top + 1), quantity, 15, "#33566E")
    check_mark((card_left + 336, row_top + 10), 9, "#0F766E")
    text((card_left + 354, row_top + 1), status, 13, "#2C7A6B")

rounded_box((card_left + 18, 532, card_right - 18, 610), "#FCEFC7", "#E9B94B", 12, 2)
text((card_left + 30, 546), "Elite coffee 200g", 16, "#6B4E0D", "Semibold")
text((card_left + 262, 547), "× 12", 15, "#7A5A12")
circle((card_left + 344, 556), 10, "#D97706")
text((card_left + 344, 556), "!", 13, "#FFFFFF", "Bold", "mm")
text((card_left + 362, 547), "only 8", 13, "#92610E", "Semibold")
text((card_left + 30, 578), "suggested swap: Jacobs 200g × 12", 13, "#7A5A12")

text((card_left + 30, 630), "Sugat rice 1kg", 16, "#17344A", "Semibold")
text((card_left + 262, 631), "× 2 cases", 15, "#33566E")
check_mark((card_left + 336, 640), 9, "#0F766E")
text((card_left + 354, 631), "in stock", 13, "#2C7A6B")

drawing.line([point((card_left + 30, 692)), point((card_right - 30, 692))], fill="#D8E2EC", width=scaled(2))
text((card_left + 30, 708), "Draft invoice #30412 · Priority ERP · 08:53:07", 14, "#33566E", "Semibold")
text((card_left + 30, 736), "stock reserved · nothing retyped", 13, "#5B7186")

pill(
    (frame_two_left + 70, 830, frame_two_left + 490, 872),
    "RAMI'S ONLY TOUCH: approve the swap · one tap",
    "#332B18",
    "#D6A52D",
    "#FCD97D",
    13,
)
text((frame_two_left + 40, 903), "The system does the retyping.", 15, "#D1DCEB", "Semibold")
circle((frame_two_left + 46, 947), 4, "#FBBF24")
text((frame_two_left + 62, 938), "a human touches only the exception", 13, "#7F91AA")


frame_three_left = frame_lefts[2]
manifest_left = frame_three_left + 40
manifest_right = frame_three_left + 520
rounded_box((manifest_left, 300, manifest_right, 760), "#F4F8FD", "#C9D6E4", 18, 2, True)
text((manifest_left + 30, 328), "Route 2 · Sunday · Moti", 20, "#0B2537", "Bold")
text((manifest_left + 30, 362), "stop 4 of 11 · planned automatically overnight", 13, "#5B7186")
drawing.line(
    [point((manifest_left + 30, 396)), point((manifest_right - 30, 396))],
    fill="#D8E2EC",
    width=scaled(2),
)
text((manifest_left + 30, 418), "Makolet HaTzafon", 17, "#17344A", "Bold")
text((manifest_left + 30, 448), "HaGalil 12, Kiryat Shmona", 14, "#5B7186")
pill((manifest_left + 30, 490, manifest_left + 150, 526), "7 boxes", "#E8F0F8", "#B9CBDC", "#33566E", 13)
pill((manifest_left + 165, 490, manifest_left + 330, 526), "1 cooler crate", "#E8F0F8", "#B9CBDC", "#33566E", 13)

manifest_checklist = [
    "Arrived 07:10 (window 07:00–07:30)",
    "Signed + photo captured",
    "Invoice #30412 auto-marked delivered",
]
for index, line in enumerate(manifest_checklist):
    row_top = 558 + index * 44
    check_mark((manifest_left + 40, row_top + 9), 10, "#0F766E")
    text((manifest_left + 62, row_top), line, 15, "#17344A", "Semibold")

rounded_box((frame_three_left + 70, 795, frame_three_left + 470, 872), "#1F2C34", None, 12, 0)
text((frame_three_left + 85, 808), "Your delivery: tomorrow 07:00–07:30", 14, "#E9EDEF")
text((frame_three_left + 85, 836), "sent to the customer automatically · Sat 18:00", 11, "#8696A0")

text((frame_three_left + 40, 903), "Proof flows back by itself.", 15, "#D1DCEB", "Semibold")
circle((frame_three_left + 46, 947), 4, "#2DD4BF")
text((frame_three_left + 62, 938), "invoice, photo, status — all synced", 13, "#7F91AA")


arrow((638, 560), (712, 560), "#2DD4BF", 4)
text((675, 528), "2 sec", 13, "#73E7DC", "Semibold", "mm")
arrow((1288, 560), (1362, 560), "#2DD4BF", 4)
text((1325, 528), "overnight", 13, "#73E7DC", "Semibold", "mm")

circle((82, 1051), 5, "#2DD4BF")
text((100, 1040), "Automatic", 15, "#D1DCEB", "Semibold")
text((205, 1042), "— nobody does anything", 14, "#7F91AA")
circle((455, 1051), 5, "#FBBF24")
text((473, 1040), "Human moment", 15, "#D1DCEB", "Semibold")
text((620, 1042), "— one tap, thirty seconds", 14, "#7F91AA")
text(
    (1930, 1040),
    "Every detail is a deliberate guess: times, items, prices, who approves. Correct it.",
    14,
    "#71849E",
    "Medium",
    "rt",
)

image.convert("RGB").save(OUTPUT_PATH, quality=95)
print(OUTPUT_PATH)
