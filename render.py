"""Draw a Conky frame to an RGBA image."""

from __future__ import annotations

import math
import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .colors import parse_color
from .config import Config
from .stats import Stats
from .variables import Bar, Graph, HRule, Marker, Text, Token, expand

FONT_FILES: dict[str, tuple[str, str]] = {
    "segoe ui": ("segoeui.ttf", "segoeuib.ttf"),
    "segoe ui semibold": ("seguisb.ttf", "seguisb.ttf"),
    "segoe ui light": ("segoeuil.ttf", "segoeuil.ttf"),
    "consolas": ("consola.ttf", "consolab.ttf"),
    "cascadia mono": ("CascadiaMono.ttf", "CascadiaMono.ttf"),
    "cascadia code": ("CascadiaCode.ttf", "CascadiaCode.ttf"),
    "calibri": ("calibri.ttf", "calibrib.ttf"),
    "arial": ("arial.ttf", "arialbd.ttf"),
    "tahoma": ("tahoma.ttf", "tahomabd.ttf"),
    "verdana": ("verdana.ttf", "verdanab.ttf"),
    "courier new": ("cour.ttf", "courbd.ttf"),
    "georgia": ("georgia.ttf", "georgiab.ttf"),
}


def _fonts_dir() -> Path:
    return Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"


def _font_file(name: str, bold: bool) -> str:
    folder = _fonts_dir()
    mapped = FONT_FILES.get(name.strip().lower())
    if mapped:
        candidate = folder / (mapped[1] if bold else mapped[0])
        if candidate.exists():
            return str(candidate)
        regular = folder / mapped[0]
        if regular.exists():
            return str(regular)
    direct = folder / name
    if direct.exists():
        return str(direct)
    for fallback in ("segoeui.ttf", "arial.ttf", "consola.ttf"):
        candidate = folder / fallback
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError(name)


@lru_cache(maxsize=64)
def load_font(name: str, size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(_font_file(name, bold), size)
    except (OSError, FileNotFoundError):
        return ImageFont.load_default(size=size)


def _font_height(font: ImageFont.ImageFont) -> int:
    metrics = getattr(font, "getmetrics", None)
    if metrics:
        ascent, descent = metrics()
        return int(ascent + descent)
    bbox = font.getbbox("Ag")
    return max(1, bbox[3] - bbox[1])


def _text_width(font: ImageFont.ImageFont, text: str) -> float:
    if not text:
        return 0
    return float(font.getlength(text))


def _font_for(token: Text) -> ImageFont.ImageFont:
    return load_font(token.font_name, token.font_size, token.bold)


def _item_height(token: Token) -> int:
    if isinstance(token, Text):
        return _font_height(_font_for(token))
    if isinstance(token, (Bar, Graph)):
        return token.height
    if isinstance(token, HRule):
        return max(8, token.thickness + 4)
    return 0


def _is_expander(token: Token) -> bool:
    if isinstance(token, HRule):
        return True
    if isinstance(token, (Bar, Graph)) and not token.width:
        return True
    return False


def _fixed_width(token: Token) -> float:
    if isinstance(token, Text):
        return _text_width(_font_for(token), token.text)
    if isinstance(token, Marker) and token.kind == "hoffset":
        return token.value
    if isinstance(token, (Bar, Graph)) and token.width:
        return token.width
    return 0


def _split_align(tokens: list[Token]) -> tuple[list[Token], list[Token], str]:
    for index, token in enumerate(tokens):
        if isinstance(token, Marker) and token.kind in {"alignr", "alignc"}:
            right = list(tokens[index + 1 :])
            if token.value and token.kind == "alignr":
                right.insert(0, Marker("hoffset", token.value))
            return list(tokens[:index]), right, token.kind
    return list(tokens), [], ""


def _group_fixed(tokens: list[Token]) -> float:
    width = 0.0
    cursor = 0.0
    for token in tokens:
        if isinstance(token, Marker) and token.kind == "goto":
            cursor = float(token.value)
            width = max(width, cursor)
            continue
        if isinstance(token, Marker) and token.kind == "hoffset":
            cursor += token.value
            width = max(width, cursor)
            continue
        if _is_expander(token):
            continue
        cursor += _fixed_width(token)
        width = max(width, cursor)
    return width


def _line_height(tokens: list[Token]) -> int:
    heights = [_item_height(token) for token in tokens]
    return max(heights) if heights else 0


def _is_voffset(token: Token) -> bool:
    return isinstance(token, Marker) and token.kind == "voffset"


def _leading_voffset(tokens: list[Token]) -> int:
    extra = 0
    for token in tokens:
        if _is_voffset(token):
            extra += token.value
        else:
            break
    return extra


def _draw_group(
    draw: ImageDraw.ImageDraw,
    tokens: list[Token],
    x: float,
    y: int,
    row_h: int,
    expand_width: float,
    config: Config,
    scale: float,
) -> None:
    expanders = [token for token in tokens if _is_expander(token)]
    each = expand_width / len(expanders) if expanders else 0
    cursor = x
    for token in tokens:
        if isinstance(token, Marker) and token.kind == "goto":
            cursor = x + token.value
            continue
        if isinstance(token, Marker) and token.kind == "hoffset":
            cursor += token.value
            continue
        if isinstance(token, Text):
            _draw_text(draw, cursor, y, row_h, token, config, scale)
            cursor += _text_width(_font_for(token), token.text)
            continue
        if isinstance(token, Bar):
            width = float(token.width or max(4, each))
            top = y + max(0, (row_h - token.height) / 2)
            _draw_bar(draw, cursor, top, width, token)
            cursor += width
            continue
        if isinstance(token, Graph):
            width = float(token.width or max(8, each))
            top = y + max(0, (row_h - token.height) / 2)
            _draw_graph(draw, cursor, top, width, token)
            cursor += width
            continue
        if isinstance(token, HRule):
            width = max(4.0, each)
            mid = y + row_h / 2
            draw.line(
                [(cursor, mid), (cursor + width, mid)],
                fill=token.color,
                width=token.thickness,
            )
            cursor += width


def _draw_text(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: int,
    row_h: int,
    token: Text,
    config: Config,
    scale: float,
) -> None:
    font = _font_for(token)
    text_h = _font_height(font)
    top = y + max(0, (row_h - text_h) / 2)
    if config.draw_outline:
        outline = parse_color(config.default_outline_color)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            draw.text((x + dx, top + dy), token.text, font=font, fill=outline, anchor="lt")
    if config.draw_shades:
        shade = parse_color(config.default_shade_color)
        shade = (shade[0], shade[1], shade[2], 180)
        step = max(1, int(round(scale)))
        draw.text((x + step, top + step), token.text, font=font, fill=shade, anchor="lt")
    draw.text((x, top), token.text, font=font, fill=token.color, anchor="lt")


def _draw_bar(draw: ImageDraw.ImageDraw, x: float, y: float, width: float, token: Bar) -> None:
    radius = max(1, token.height / 2)
    draw.rounded_rectangle(
        [x, y, x + width, y + token.height],
        radius=radius,
        fill=(255, 255, 255, 36),
    )
    fraction = max(0.0, min(1.0, token.fraction))
    if fraction <= 0:
        return
    fill_w = width * fraction
    if fraction > 0.03:
        fill_w = max(token.height, fill_w)
    fill_w = min(width, fill_w)
    draw.rounded_rectangle(
        [x, y, x + fill_w, y + token.height],
        radius=radius,
        fill=token.color,
    )


def _lerp(start: tuple[int, int, int, int], end: tuple[int, int, int, int], t: float):
    return tuple(int(start[index] + (end[index] - start[index]) * t) for index in range(4))


def _graph_peak(values: list[float], autoscale: bool) -> float:
    if not autoscale:
        return 100.0
    peak = max(values) if values else 1.0
    if peak <= 1:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(peak))
    snapped = math.ceil((peak * 1.15) / magnitude) * magnitude
    return max(snapped, peak * 1.25, 1.0)


def _draw_graph(draw: ImageDraw.ImageDraw, x: float, y: float, width: float, token: Graph) -> None:
    radius = max(2, int(min(6, token.height / 3)))
    draw.rounded_rectangle(
        [x, y, x + width, y + token.height],
        radius=radius,
        fill=(255, 255, 255, 34),
    )
    values = list(token.values)
    if not values:
        return
    if len(values) < 12:
        values = [0.0] * (12 - len(values)) + values
    if len(values) > int(width):
        values = values[-int(width) :]
    peak = _graph_peak(values, token.autoscale)
    points: list[tuple[float, float]] = []
    last = max(len(values) - 1, 1)
    for index, value in enumerate(values):
        px = x + (index / last) * max(width - 1, 1)
        clamped = max(0.0, min(peak, value))
        py = y + token.height - 2 - (clamped / peak) * max(token.height - 4, 1)
        points.append((px, py))
    fill = (token.color[0], token.color[1], token.color[2], 70)
    polygon = [(x, y + token.height)] + points + [(x + width, y + token.height)]
    draw.polygon(polygon, fill=fill)
    span = max(len(points) - 2, 1)
    for index in range(len(points) - 1):
        color = _lerp(token.color, token.color2, index / span)
        draw.line([points[index], points[index + 1]], fill=color, width=2)


def _measure_natural(lines: list[list[Token]]) -> int:
    widest = 0.0
    for line in lines:
        left, right, _mode = _split_align([token for token in line if not _is_voffset(token)])
        natural = _group_fixed(left) + _group_fixed(right)
        if left and right:
            natural += 16
        widest = max(widest, natural)
    return int(widest)


def _measure_height(lines: list[list[Token]], line_gap: int) -> int:
    height = 0
    for index, line in enumerate(lines):
        left, right, _mode = _split_align([token for token in line if not _is_voffset(token)])
        row_h = _line_height(left + right) or 8
        gap = 0 if index == len(lines) - 1 else line_gap
        height += _leading_voffset(line) + row_h + gap
    return height


def _paint(
    draw: ImageDraw.ImageDraw,
    lines: list[list[Token]],
    origin_x: int,
    origin_y: int,
    inner_w: int,
    line_gap: int,
    config: Config,
    scale: float,
) -> None:
    y = origin_y
    for index, line in enumerate(lines):
        y += _leading_voffset(line)
        body = [token for token in line if not _is_voffset(token)]
        left, right, mode = _split_align(body)
        row_h = _line_height(left + right) or 8
        left_fixed = _group_fixed(left)
        right_fixed = _group_fixed(right)
        gap = 16 if left and right else 0
        free = inner_w - left_fixed - right_fixed - gap
        left_expanders = sum(1 for token in left if _is_expander(token))
        right_expanders = sum(1 for token in right if _is_expander(token))
        if mode == "alignc" and right and not left:
            group_w = right_fixed
            start = origin_x + max(0, (inner_w - group_w) / 2)
            _draw_group(draw, right, start, y, row_h, max(0, inner_w - group_w), config, scale)
        else:
            left_extra = free if left_expanders else 0
            if left_expanders and right_expanders:
                left_extra = free * left_expanders / (left_expanders + right_expanders)
            _draw_group(draw, left, origin_x, y, row_h, max(0, left_extra), config, scale)
            if right:
                right_extra = max(0, free - left_extra) if right_expanders else 0
                right_w = right_fixed + (right_extra if right_expanders else 0)
                _draw_group(
                    draw,
                    right,
                    origin_x + inner_w - right_w,
                    y,
                    row_h,
                    right_extra,
                    config,
                    scale,
                )
        y += row_h + (0 if index == len(lines) - 1 else line_gap)


def render_frame(config: Config, stats: Stats, scale: float = 1.0) -> Image.Image:
    scale = max(0.55, float(scale))
    lines, _unknown = expand(config, stats, scale)
    margin = max(0, int(round(config.border_inner_margin * scale)))
    minimum = int(round(config.minimum_width * scale))
    maximum = int(round(config.maximum_width * scale)) if config.maximum_width else 0
    line_gap = int(round(config.line_spacing * scale))
    natural = _measure_natural(lines)
    panel_w = max(minimum, natural + margin * 2)
    if maximum and natural + margin * 2 <= maximum:
        panel_w = min(max(panel_w, minimum), maximum)
    panel_w = max(panel_w, margin * 2 + 40)
    inner_w = panel_w - margin * 2
    content_h = _measure_height(lines, line_gap)
    panel_h = max(int(round(config.minimum_height * scale)), content_h + margin * 2)
    alpha = config.background_alpha()
    shadow = int(round(12 * scale)) if alpha else 0
    image = Image.new("RGBA", (panel_w + shadow * 2, panel_h + shadow * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if alpha:
        rect = [shadow, shadow, shadow + panel_w - 1, shadow + panel_h - 1]
        radius = int(round(config.corner_radius * scale))
        bg = parse_color(config.own_window_colour)
        draw.rounded_rectangle(
            [rect[0] + 3, rect[1] + 6, rect[2] + 3, rect[3] + 6],
            radius=radius,
            fill=(0, 0, 0, 90),
        )
        draw.rounded_rectangle(rect, radius=radius, fill=(bg[0], bg[1], bg[2], alpha))
        if config.draw_borders and config.border_width > 0:
            border = parse_color(config.border_color)
            draw.rounded_rectangle(
                rect,
                radius=radius,
                outline=border,
                width=max(1, int(round(config.border_width * scale))),
            )
    _paint(draw, lines, shadow + margin, shadow + margin, inner_w, line_gap, config, scale)
    return image


def render_message(title: str, body: str, scale: float = 1.0) -> Image.Image:
    config = Config()
    config.text = "${color #FF453A}" + title + "\n${color #F2F2F7}" + body
    config.minimum_width = 360
    config.own_window_argb_value = 210
    stats = Stats()
    return render_frame(config, stats, scale)
