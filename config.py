"""Load classic Conky configs and the common Lua config subset."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def _as_bool(value: str, default: bool) -> bool:
    text = str(value).strip().lower()
    if text in {"yes", "true", "1", "on"}:
        return True
    if text in {"no", "false", "0", "off"}:
        return False
    return default


def _as_int(value: str, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _as_float(value: str, default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_font_spec(spec: str, fallback_size: int = 13) -> tuple[str, int, bool]:
    parts = [part.strip() for part in spec.split(":") if part.strip()]
    if not parts:
        return "Segoe UI", fallback_size, False
    name = parts[0]
    size = fallback_size
    bold = False
    for part in parts[1:]:
        lower = part.lower()
        if lower.startswith("size="):
            size = _as_int(lower.split("=", 1)[1], fallback_size)
        elif lower == "bold":
            bold = True
    return name, max(6, size), bold


def _canon_key(key: str) -> str:
    key = key.strip().lower()
    aliases = {
        "own_window_color": "own_window_colour",
        "default_colour": "default_color",
        "default_shade_colour": "default_shade_color",
        "default_outline_colour": "default_outline_color",
        "border_colour": "border_color",
        "xftfont": "font",
    }
    return aliases.get(key, key)


@dataclass
class Config:
    alignment: str = "top_right"
    gap_x: int = 24
    gap_y: int = 48
    minimum_width: int = 300
    minimum_height: int = 0
    maximum_width: int = 420
    update_interval: float = 1.0
    own_window_transparent: bool = True
    own_window_argb_visual: bool = True
    own_window_argb_value: int = 150
    own_window_colour: str = "1C1C1E"
    own_window_type: str = "normal"
    font: str = "Segoe UI"
    font_size: int = 14
    font_bold: bool = False
    default_color: str = "F2F2F7"
    default_shade_color: str = "000000"
    default_outline_color: str = "000000"
    colors: dict[int, str] = field(default_factory=dict)
    draw_shades: bool = True
    draw_outline: bool = False
    draw_borders: bool = False
    border_width: int = 1
    border_inner_margin: int = 16
    border_color: str = "3A3A3C"
    uppercase: bool = False
    short_units: bool = True
    pad_percents: int = 0
    top_name_width: int = 20
    cpu_avg_samples: int = 2
    net_avg_samples: int = 2
    click_through: bool = False
    corner_radius: int = 16
    monitor: int = 0
    line_spacing: int = 3
    text: str = ""
    path: str = ""

    def background_alpha(self) -> int:
        if self.own_window_argb_visual:
            return max(0, min(255, self.own_window_argb_value))
        if self.own_window_transparent:
            return 0
        return 255

    def palette(self, index: int) -> str:
        if index in self.colors:
            return self.colors[index]
        return self.default_color


def _apply_setting(config: Config, key: str, value: str) -> None:
    key = _canon_key(key)
    value = value.strip().strip(",").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]

    if key == "alignment":
        config.alignment = value.lower().replace("-", "_")
    elif key == "gap_x":
        config.gap_x = _as_int(value, config.gap_x)
    elif key == "gap_y":
        config.gap_y = _as_int(value, config.gap_y)
    elif key == "minimum_width":
        config.minimum_width = _as_int(value, config.minimum_width)
    elif key == "minimum_height":
        config.minimum_height = _as_int(value, config.minimum_height)
    elif key == "maximum_width":
        config.maximum_width = _as_int(value, config.maximum_width)
    elif key == "update_interval":
        config.update_interval = max(0.2, _as_float(value, config.update_interval))
    elif key == "own_window_transparent":
        config.own_window_transparent = _as_bool(value, config.own_window_transparent)
    elif key == "own_window_argb_visual":
        config.own_window_argb_visual = _as_bool(value, config.own_window_argb_visual)
    elif key == "own_window_argb_value":
        config.own_window_argb_value = max(0, min(255, _as_int(value, config.own_window_argb_value)))
    elif key == "own_window_colour":
        config.own_window_colour = value
    elif key == "own_window_type":
        config.own_window_type = value.lower()
    elif key == "font":
        name, size, bold = parse_font_spec(value, config.font_size)
        config.font = name
        config.font_size = size
        config.font_bold = bold
    elif key == "default_color":
        config.default_color = value
    elif key == "default_shade_color":
        config.default_shade_color = value
    elif key == "default_outline_color":
        config.default_outline_color = value
    elif re.fullmatch(r"color[0-9]", key):
        config.colors[int(key[-1])] = value
    elif key == "draw_shades":
        config.draw_shades = _as_bool(value, config.draw_shades)
    elif key == "draw_outline":
        config.draw_outline = _as_bool(value, config.draw_outline)
    elif key == "draw_borders":
        config.draw_borders = _as_bool(value, config.draw_borders)
    elif key == "border_width":
        config.border_width = _as_int(value, config.border_width)
    elif key == "border_inner_margin":
        config.border_inner_margin = _as_int(value, config.border_inner_margin)
    elif key == "border_color":
        config.border_color = value
    elif key == "uppercase":
        config.uppercase = _as_bool(value, config.uppercase)
    elif key == "short_units":
        config.short_units = _as_bool(value, config.short_units)
    elif key == "pad_percents":
        config.pad_percents = _as_int(value, config.pad_percents)
    elif key == "top_name_width":
        config.top_name_width = max(4, _as_int(value, config.top_name_width))
    elif key == "cpu_avg_samples":
        config.cpu_avg_samples = max(1, _as_int(value, config.cpu_avg_samples))
    elif key == "net_avg_samples":
        config.net_avg_samples = max(1, _as_int(value, config.net_avg_samples))
    elif key == "click_through":
        config.click_through = _as_bool(value, config.click_through)
    elif key == "corner_radius":
        config.corner_radius = max(0, _as_int(value, config.corner_radius))
    elif key == "monitor":
        config.monitor = max(0, _as_int(value, config.monitor))
    elif key == "line_spacing":
        config.line_spacing = _as_int(value, config.line_spacing)


def _strip_inline_comment(line: str, marker: str) -> str:
    in_single = False
    in_double = False
    index = 0
    while index < len(line):
        char = line[index]
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double and line.startswith(marker, index):
            return line[:index]
        index += 1
    return line


def _parse_classic(text: str, config: Config) -> None:
    lines = text.splitlines()
    body: list[str] = []
    in_text = False
    for line in lines:
        if not in_text and line.strip() == "TEXT":
            in_text = True
            continue
        if in_text:
            body.append(line)
            continue
        stripped = _strip_inline_comment(line, "#").strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("--"):
            continue
        pieces = stripped.split(None, 1)
        if len(pieces) == 1:
            _apply_setting(config, pieces[0], "yes")
        else:
            _apply_setting(config, pieces[0], pieces[1])
    config.text = "\n".join(body)


def _parse_lua(text: str, config: Config) -> None:
    match = re.search(r"conky\.text\s*=\s*\[\[(.*?)\]\]", text, re.S)
    if not match:
        raise ValueError("Lua config is missing conky.text = [[ ... ]].")
    config.text = match.group(1).strip("\n")
    config_match = re.search(r"conky\.config\s*=\s*\{(.*)\}", text, re.S)
    body = config_match.group(1) if config_match else ""
    cleaned: list[str] = []
    for line in body.splitlines():
        if line.strip().startswith("--"):
            continue
        cleaned.append(_strip_inline_comment(line, "--"))
    for key, raw in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^,\n]+)", "\n".join(cleaned)):
        _apply_setting(config, key, raw.strip())


def parse_config(text: str, path: str = "") -> Config:
    config = Config(path=path)
    if re.search(r"conky\.text\s*=", text):
        _parse_lua(text, config)
    else:
        _parse_classic(text, config)
    if not config.text.strip():
        config.text = "${color}Conky Windows\n${color grey}Add a TEXT section to your config."
    return config


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return parse_config(handle.read(), path)
