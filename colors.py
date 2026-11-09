"""Color names and hex parsing for Conky configs."""

from __future__ import annotations

import re

Color = tuple[int, int, int, int]

_NAMES: dict[str, Color] = {
    "white": (255, 255, 255, 255),
    "black": (0, 0, 0, 255),
    "red": (255, 59, 48, 255),
    "green": (48, 209, 88, 255),
    "blue": (10, 132, 255, 255),
    "yellow": (255, 214, 10, 255),
    "cyan": (100, 210, 255, 255),
    "magenta": (255, 55, 95, 255),
    "orange": (255, 159, 10, 255),
    "pink": (255, 55, 95, 255),
    "purple": (191, 90, 242, 255),
    "brown": (172, 142, 104, 255),
    "gold": (255, 214, 10, 255),
    "violet": (191, 90, 242, 255),
    "navy": (10, 64, 129, 255),
    "skyblue": (100, 210, 255, 255),
    "royalblue": (64, 156, 255, 255),
    "lightblue": (100, 210, 255, 255),
    "darkblue": (10, 88, 202, 255),
    "lightgreen": (48, 209, 88, 255),
    "darkgreen": (36, 138, 61, 255),
    "lime": (48, 209, 88, 255),
    "limegreen": (48, 209, 88, 255),
    "teal": (64, 200, 224, 255),
    "turquoise": (64, 200, 224, 255),
    "silver": (174, 174, 178, 255),
    "grey": (142, 142, 147, 255),
    "gray": (142, 142, 147, 255),
    "lightgrey": (174, 174, 178, 255),
    "lightgray": (174, 174, 178, 255),
    "darkgrey": (99, 99, 102, 255),
    "darkgray": (99, 99, 102, 255),
    "dimgray": (72, 72, 74, 255),
    "slategray": (99, 99, 102, 255),
    "hotpink": (255, 55, 95, 255),
    "deeppink": (255, 45, 85, 255),
    "crimson": (255, 69, 58, 255),
    "salmon": (255, 100, 90, 255),
    "tomato": (255, 69, 58, 255),
    "orangered": (255, 69, 58, 255),
    "coral": (255, 127, 80, 255),
    "khaki": (240, 230, 140, 255),
    "olive": (128, 128, 0, 255),
    "maroon": (128, 0, 0, 255),
    "indigo": (94, 92, 230, 255),
    "orchid": (191, 90, 242, 255),
    "plum": (191, 90, 242, 255),
    "beige": (245, 245, 220, 255),
    "ivory": (255, 255, 240, 255),
    "azure": (240, 255, 255, 255),
    "snow": (255, 250, 250, 255),
    "wheat": (245, 222, 179, 255),
    "tan": (210, 180, 140, 255),
    "chocolate": (210, 105, 30, 255),
    "transparent": (0, 0, 0, 0),
}


def looks_like_color(token: str) -> bool:
    raw = token.strip().lower()
    if raw.startswith("#"):
        raw = raw[1:]
    if raw in _NAMES:
        return True
    return bool(re.fullmatch(r"[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8}", raw))


def parse_color(value: str | Color | None, default: Color = (242, 242, 247, 255)) -> Color:
    if value is None:
        return default
    if isinstance(value, tuple):
        if len(value) == 3:
            return (value[0], value[1], value[2], 255)
        return value  # type: ignore[return-value]
    raw = str(value).strip().lower()
    if not raw:
        return default
    if raw.startswith("#"):
        raw = raw[1:]
    if raw in _NAMES:
        return _NAMES[raw]
    if re.fullmatch(r"[0-9a-f]{3}", raw):
        raw = "".join(ch * 2 for ch in raw)
    if re.fullmatch(r"[0-9a-f]{6}", raw):
        return (
            int(raw[0:2], 16),
            int(raw[2:4], 16),
            int(raw[4:6], 16),
            255,
        )
    if re.fullmatch(r"[0-9a-f]{8}", raw):
        return (
            int(raw[2:4], 16),
            int(raw[4:6], 16),
            int(raw[6:8], 16),
            int(raw[0:2], 16),
        )
    return default
