#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pillow"]
# ///

import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SCALE = 1.5
CANVAS_WIDTH = 1800
CANVAS_HEIGHT = 1120
OUTPUT_PATH = pathlib.Path(__file__).parent / "where-an-issue-lives.png"
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
    outline: str,
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
    size: int = 15,
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


def cubic_point(
    start: tuple[float, float],
    control_one: tuple[float, float],
    control_two: tuple[float, float],
    end: tuple[float, float],
    progress: float,
) -> tuple[float, float]:
    """Return one point on a cubic Bézier curve.

    >>> cubic_point((0, 0), (0, 0), (1, 1), (1, 1), 0)
    (0, 0)
    """
    inverse = 1 - progress
    return (
        inverse**3 * start[0]
        + 3 * inverse**2 * progress * control_one[0]
        + 3 * inverse * progress**2 * control_two[0]
        + progress**3 * end[0],
        inverse**3 * start[1]
        + 3 * inverse**2 * progress * control_one[1]
        + 3 * inverse * progress**2 * control_two[1]
        + progress**3 * end[1],
    )


def dashed_curve(
    start: tuple[float, float],
    control_one: tuple[float, float],
    control_two: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: int = 4,
) -> None:
    curve_points = [
        cubic_point(start, control_one, control_two, end, index / 96)
        for index in range(97)
    ]
    for index in range(1, len(curve_points)):
        if (index // 4) % 2 == 0:
            drawing.line(
                [point(curve_points[index - 1]), point(curve_points[index])],
                fill=color,
                width=scaled(width),
            )

    previous = curve_points[-3]
    angle = math.atan2(end[1] - previous[1], end[0] - previous[0])
    head_length = 14
    left = (
        end[0] - head_length * math.cos(angle - 0.55),
        end[1] - head_length * math.sin(angle - 0.55),
    )
    right = (
        end[0] - head_length * math.cos(angle + 0.55),
        end[1] - head_length * math.sin(angle + 0.55),
    )
    drawing.polygon([point(end), point(left), point(right)], fill=color)


circle((112, 95), 29, "#2DD4BF")
text((112, 95), "1", 24, "#062229", "Bold", "mm")
text((165, 67), "WHERE AN ISSUE LIVES", 42, "#F8FAFC", "Bold")
text(
    (165, 124),
    "One required operational home. One independent, optional planning membership.",
    23,
    "#A9B8CC",
)
pill(
    (1455, 73, 1695, 116),
    "LINEAR · TWO AXES",
    "#101B2C",
    "#2A3951",
    "#9FB0C8",
    14,
)

rounded_box((70, 210, 1730, 1045), "#0B1525", "#27364E", 34, 2, True)
text((112, 240), "WORKSPACE", 15, "#6F829D", "Bold")
text((112, 267), "Your business", 22, "#E6EDF7", "Semibold")

rounded_box((110, 310, 860, 950), "#0C2028", "#225463", 28, 2)
rounded_box((940, 310, 1690, 950), "#201A33", "#523F78", 28, 2)

circle((153, 355), 8, "#2DD4BF")
text((175, 337), "OPERATIONAL HOME", 18, "#5EEAD4", "Bold")
text((175, 370), "Identity, workflow and execution", 18, "#8FAAB0")

circle((983, 355), 8, "#A78BFA")
text((1005, 337), "PLANNING CONTEXT", 18, "#C4B5FD", "Bold")
text((1005, 370), "Initiatives, projects and delivery phases", 18, "#A69BBE")

rounded_box((150, 420, 820, 585), "#12323C", "#2A6977", 22, 2, True)
circle((193, 463), 24, "#2DD4BF")
text((193, 463), "T", 19, "#062229", "Bold", "mm")
text((232, 438), "TEAM", 14, "#7DDDD3", "Bold")
text((232, 469), "Gilad-barnea", 28, "#F3FFFE", "Semibold")
pill((660, 438, 785, 477), "REQUIRED", "#0B252C", "#2DD4BF", "#5EEAD4", 13)

pill((178, 520, 365, 562), "Workflow · statuses", "#0C252D", "#285765", "#C5DBDE", 14)
pill((382, 520, 537, 562), "Cycles", "#0C252D", "#285765", "#C5DBDE", 14)
pill((554, 520, 705, 562), "Labels", "#0C252D", "#285765", "#C5DBDE", 14)

arrow((485, 585), (485, 674), "#2DD4BF", 4)
pill((407, 607, 563, 648), "EXACTLY 1", "#103039", "#2D6A76", "#73E7DC", 13)

rounded_box((250, 685, 720, 815), "#F3FFFE", "#5EEAD4", 24, 3, True)
circle((298, 750), 25, "#0F766E")
text((298, 750), "!", 21, "#FFFFFF", "Bold", "mm")
text((340, 711), "ISSUE", 15, "#35716D", "Bold")
text((340, 747), "Belongs to one Team", 27, "#0A2930", "Bold")
text((340, 782), "Its permanent operational address", 17, "#527177")

arrow((485, 815), (485, 850), "#548B91", 3, 10)
rounded_box((325, 860, 645, 920), "#102A32", "#2D5964", 18, 2)
drawing.line(
    [point((355, 875)), point((355, 899)), point((379, 899))],
    fill="#5EEAD4",
    width=scaled(3),
)
circle((355, 875), 4, "#5EEAD4")
circle((379, 899), 4, "#5EEAD4")
text((395, 878), "Sub-issue", 20, "#D9F5F2", "Semibold")
text((530, 882), "can nest", 14, "#7EA0A5")

rounded_box((1035, 420, 1595, 520), "#2C2443", "#624E89", 22, 2, True)
circle((1080, 470), 22, "#8B5CF6")
text((1080, 470), "I", 18, "#FFFFFF", "Bold", "mm")
text((1120, 442), "INITIATIVE", 14, "#BEAEED", "Bold")
text((1120, 473), "Strategic direction", 23, "#F4F0FF", "Semibold")

arrow((1315, 520), (1315, 585), "#8B72C9", 3, 11)
text((1338, 548), "contains", 14, "#9688B1", "Medium", "lm")

rounded_box((1035, 600, 1595, 745), "#332750", "#A78BFA", 24, 3, True)
circle((1082, 672), 24, "#8B5CF6")
text((1082, 672), "P", 19, "#FFFFFF", "Bold", "mm")
text((1124, 625), "PROJECT", 15, "#C4B5FD", "Bold")
text((1124, 660), "Optional issue context", 27, "#FAF8FF", "Bold")
text((1124, 697), "Planning and delivery—not ownership", 17, "#B8ACCF")

arrow((1315, 745), (1315, 840), "#8B72C9", 3, 11)
text((1338, 780), "phases", 14, "#9688B1", "Medium", "lm")

rounded_box((1120, 850, 1510, 915), "#2A223F", "#5D4D7E", 18, 2)
drawing.polygon(
    [point((1159, 874)), point((1168, 883)), point((1159, 892)), point((1150, 883))],
    fill="#A78BFA",
)
text((1185, 869), "Milestone", 20, "#E8E1FA", "Semibold")
text((1320, 873), "inside that Project", 14, "#9C90B3")

dashed_curve(
    (720, 748),
    (850, 748),
    (900, 671),
    (1023, 671),
    "#FBBF24",
    4,
)
pill((790, 649, 995, 704), "MAY ALSO JOIN", "#332B18", "#D6A52D", "#FCD97D", 13)
pill((842, 713, 946, 751), "0 OR 1", "#241E13", "#8D742F", "#F5C95C", 12)

circle((122, 1000), 5, "#2DD4BF")
text((139, 985), "Solid", 15, "#D1DCEB", "Semibold")
text((184, 985), "= structural home or containment", 15, "#7F91AA")

for start_x in (470, 483, 496):
    drawing.line(
        [point((start_x, 1000)), point((start_x + 7, 1000))],
        fill="#FBBF24",
        width=scaled(3),
    )
text((520, 985), "Dashed", 15, "#D1DCEB", "Semibold")
text((580, 985), "= optional issue membership", 15, "#7F91AA")

text(
    (1690, 995),
    "The two axes coexist; neither replaces the other.",
    15,
    "#71849E",
    "Medium",
    "rt",
)

image.convert("RGB").save(OUTPUT_PATH, quality=95)
print(OUTPUT_PATH)
