"""Turn Conky text into draw tokens."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

import psutil

from .colors import Color, looks_like_color, parse_color
from .config import Config, parse_font_spec
from .stats import Stats, format_uptime, human_bytes, win_path

TOKEN_RE = re.compile(r"\$\{([^{}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
CREATE_NO_WINDOW = 0x08000000
_EXEC_CACHE: dict[str, tuple[float, str]] = {}
_UNKNOWN: set[str] = set()


@dataclass
class Text:
    text: str
    color: Color
    font_name: str
    font_size: int
    bold: bool


@dataclass
class Bar:
    fraction: float
    color: Color
    height: int
    width: int | None


@dataclass
class Graph:
    values: list[float]
    color: Color
    color2: Color
    height: int
    width: int | None
    autoscale: bool


@dataclass
class HRule:
    color: Color
    thickness: int


@dataclass
class Marker:
    kind: str
    value: int = 0


Token = Text | Bar | Graph | HRule | Marker


def _scale(value: int | float, scale: float, minimum: int = 0) -> int:
    scaled = int(round(value * scale))
    if minimum and scaled < minimum and value > 0:
        return minimum
    return scaled


def _pct(value: float, pad: int) -> str:
    text = f"{value:.0f}"
    if pad > 0:
        return text.rjust(pad)
    return text


def _filesystem_type(spec: str) -> str:
    path = win_path(spec).lower()
    best = ""
    best_len = -1
    try:
        partitions = psutil.disk_partitions(all=False)
    except psutil.Error:
        return "n/a"
    for part in partitions:
        mount = part.mountpoint.lower()
        if path.startswith(mount) and len(mount) > best_len:
            best = part.fstype or ""
            best_len = len(mount)
    return best or "n/a"


def _cpu_index(rest: str) -> int:
    text = rest.strip().lower()
    if not text or text in {"cpu0", "0"}:
        return 0
    if text.startswith("cpu"):
        text = text[3:]
    try:
        return max(0, int(text))
    except ValueError:
        return 0


def _cpu_value(stats: Stats, index: int) -> float:
    if index <= 0:
        return stats.cpu
    if index - 1 < len(stats.cpu_cores):
        return stats.cpu_cores[index - 1]
    return 0.0


def _battery_text(stats: Stats) -> str:
    battery = stats.battery
    if battery is None:
        return "AC"
    percent = float(battery.percent or 0)
    if battery.power_plugged and percent >= 98:
        state = "Full"
    elif battery.power_plugged:
        state = "Charging"
    else:
        state = "Discharging"
    return f"{state} {percent:.0f}%"


def _battery_time(stats: Stats) -> str:
    battery = stats.battery
    if battery is None or battery.secsleft is None:
        return ""
    seconds = int(battery.secsleft)
    if seconds < 0:
        return ""
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _top(stats: Stats, rest: str, by_mem: bool, width: int) -> str:
    bits = rest.split()
    kind = bits[0].lower() if bits else "name"
    try:
        index = int(bits[1]) if len(bits) > 1 else 1
    except ValueError:
        index = 1
    rows = stats.top_mem if by_mem else stats.top_cpu
    if index < 1 or index > len(rows):
        return ""
    row = rows[index - 1]
    if kind == "pid":
        return str(row.pid)
    if kind in {"cpu", "cpu_percent"}:
        return f"{row.cpu:.0f}"
    if kind in {"mem", "mem_percent"}:
        return f"{row.mem:.1f}"
    name = row.name
    if len(name) > width:
        return name[: max(1, width - 1)] + "…"
    return name


def _run_exec(command: str, interval: float) -> str:
    if not command.strip():
        return ""
    now = __import__("time").monotonic()
    cached = _EXEC_CACHE.get(command)
    if cached and now - cached[0] < interval:
        return cached[1]
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=2,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
        output = (completed.stdout or completed.stderr or "").strip()
    except (OSError, subprocess.SubprocessError):
        output = ""
    lines = output.splitlines()[:8]
    output = "\n".join(line[:240] for line in lines)
    _EXEC_CACHE[command] = (now, output)
    return output


def _match_iface(rest: str, stats: Stats) -> tuple[str, str]:
    names = sorted(set(list(stats.addrs) + list(stats.totals)), key=len, reverse=True)
    for name in names:
        if rest == name or rest.startswith(name + " "):
            return name, rest[len(name) :].strip()
    return "", rest


def _parse_visual_args(rest: str, stats: Stats, allow_iface: bool = False, allow_path: bool = False):
    iface = ""
    working = rest.strip()
    if allow_iface and working:
        iface, working = _match_iface(working, stats)
    height: int | None = None
    width: int | None = None
    cpu = 0
    colors: list[str] = []
    subjects: list[str] = []
    for token in working.split():
        lower = token.lower()
        if re.fullmatch(r"cpu\d+", lower):
            cpu = int(lower[3:])
            continue
        if re.fullmatch(r"\d+,\d+", token):
            raw_h, raw_w = token.split(",")
            height = int(raw_h)
            width = int(raw_w) or None
            continue
        if token.isdigit() and len(token) <= 4:
            number = int(token)
            if height is None:
                height = number
            elif width is None:
                width = number or None
            continue
        if looks_like_color(token) and not (token.isdigit() and len(token) <= 4):
            colors.append(token)
            continue
        subjects.append(token)
    path = " ".join(subjects).strip()
    if allow_path and not path:
        path = "/"
    return {
        "height": 6 if height is None else height,
        "width": width,
        "cpu": cpu,
        "colors": colors,
        "iface": iface,
        "path": path or "/",
    }


class Expander:
    def __init__(self, config: Config, stats: Stats, scale: float) -> None:
        self.config = config
        self.stats = stats
        self.scale = scale
        self.color = parse_color(config.default_color)
        self.font_name = config.font
        self.font_size = _scale(config.font_size, scale, 8)
        self.bold = config.font_bold
        self.lines: list[list[Token]] = []
        self.current: list[Token] = []
        self.unknown: list[str] = []

    def expand(self, text: str) -> list[list[Token]]:
        source = text.replace("$$", "\x00")
        for raw_line in source.splitlines():
            position = 0
            for match in TOKEN_RE.finditer(raw_line):
                if match.start() > position:
                    self._add_text(raw_line[position : match.start()])
                expr = match.group(1) if match.group(1) is not None else match.group(2)
                self._add_var(expr.strip())
                position = match.end()
            if position < len(raw_line):
                self._add_text(raw_line[position:])
            self.lines.append(self.current)
            self.current = []
        if not self.lines:
            self.lines.append([])
        return self.lines

    def _add_text(self, text: str) -> None:
        text = text.replace("\x00", "$")
        if self.config.uppercase:
            text = text.upper()
        parts = text.split("\n")
        for index, part in enumerate(parts):
            if part:
                self.current.append(
                    Text(part, self.color, self.font_name, self.font_size, self.bold)
                )
            if index < len(parts) - 1:
                self.lines.append(self.current)
                self.current = []

    def _set_color(self, value: str | None) -> None:
        if value is None:
            self.color = parse_color(self.config.default_color)
            return
        if re.fullmatch(r"[0-9]", value.strip()):
            self.color = parse_color(self.config.palette(int(value)))
            return
        self.color = parse_color(value, self.color)

    def _add_var(self, expr: str) -> None:
        if not expr:
            return
        name, _, rest = expr.partition(" ")
        name = name.strip()
        rest = rest.strip()
        lower = name.lower()
        produced = self._eval(lower, rest)
        if produced is None:
            if lower not in _UNKNOWN:
                _UNKNOWN.add(lower)
                self.unknown.append(lower)
            return
        for token in produced:
            if isinstance(token, Text) and "\n" in token.text:
                self._add_text(token.text)
            else:
                self.current.append(token)

    def _text(self, value: str) -> list[Token]:
        return [Text(value, self.color, self.font_name, self.font_size, self.bold)]

    def _eval(self, name: str, rest: str) -> list[Token] | None:
        stats = self.stats
        config = self.config
        scale = self.scale

        if re.fullmatch(r"color[0-9]", name):
            self._set_color(config.palette(int(name[-1])))
            return []
        if name == "color":
            self._set_color(None if not rest else rest)
            return []
        if name == "font":
            if not rest:
                self.font_name = config.font
                self.font_size = _scale(config.font_size, scale, 8)
                self.bold = config.font_bold
            else:
                font_name, font_size, bold = parse_font_spec(rest, config.font_size)
                self.font_name = font_name
                self.font_size = _scale(font_size, scale, 8)
                self.bold = bold
            return []
        if name in {"alignr", "alignc"}:
            pad = _scale(int(rest), scale) if rest.isdigit() else 0
            return [Marker(name, pad)]
        if name in {"voffset", "offset", "goto"}:
            try:
                amount = int(float(rest or "0"))
            except ValueError:
                amount = 0
            kind = {"voffset": "voffset", "offset": "hoffset", "goto": "goto"}[name]
            return [Marker(kind, _scale(amount, scale))]
        if name == "hr":
            thickness = _scale(int(rest), scale, 1) if rest.isdigit() else _scale(1, scale, 1)
            return [HRule(self.color, max(1, thickness))]

        if name in {"cpubar", "cpugraph", "membar", "memgraph", "swapbar", "fs_bar", "battery_bar", "downspeedgraph", "upspeedgraph", "diskiograph"}:
            return [self._widget(name, rest)]

        value = self._string_var(name, rest)
        if value is None:
            return None
        if config.uppercase:
            value = value.upper()
        return self._text(value)

    def _widget(self, name: str, rest: str) -> Token:
        stats = self.stats
        scale = self.scale
        allow_iface = name in {"downspeedgraph", "upspeedgraph"}
        allow_path = name == "fs_bar"
        args = _parse_visual_args(rest, stats, allow_iface=allow_iface, allow_path=allow_path)
        height = _scale(args["height"], scale, 3)
        width = _scale(args["width"], scale, 1) if args["width"] else None
        colors = args["colors"]
        primary = parse_color(colors[0], self.color) if colors else self.color
        secondary = parse_color(colors[1], primary) if len(colors) > 1 else primary

        if name == "cpubar":
            return Bar(_cpu_value(stats, args["cpu"]) / 100, primary, height, width)
        if name == "cpugraph":
            key = "cpu" if args["cpu"] <= 0 else f"cpu{args['cpu']}"
            return Graph(stats.series(key), primary, secondary, height, width, False)
        if name == "membar":
            return Bar(stats.mem_percent / 100, primary, height, width)
        if name == "memgraph":
            return Graph(stats.series("mem"), primary, secondary, height, width, False)
        if name == "swapbar":
            return Bar(stats.swap_percent / 100, primary, height, width)
        if name == "fs_bar":
            usage = stats.disk(args["path"])
            fraction = (usage.percent / 100) if usage else 0
            return Bar(fraction, primary, height, width)
        if name == "battery_bar":
            percent = float(stats.battery.percent) if stats.battery else 0
            return Bar(percent / 100, primary, height, width)
        if name == "downspeedgraph":
            key = f"down:{args['iface']}" if args["iface"] else "down"
            return Graph(stats.series(key), primary, secondary, height, width, True)
        if name == "upspeedgraph":
            key = f"up:{args['iface']}" if args["iface"] else "up"
            return Graph(stats.series(key), primary, secondary, height, width, True)
        return Graph(stats.series("disk"), primary, secondary, height, width, True)

    def _string_var(self, name: str, rest: str) -> str | None:
        stats = self.stats
        config = self.config
        short = config.short_units

        if name in {"nodename", "hostname"}:
            return stats.nodename
        if name == "sysname":
            return stats.sysname
        if name == "kernel":
            return stats.kernel
        if name == "machine":
            return stats.machine
        if name in {"username", "user"}:
            return stats.username
        if name in {"uptime", "uptime_short"}:
            return format_uptime(stats.uptime_seconds)
        if name in {"time", "utime"}:
            fmt = rest or "%H:%M:%S"
            fmt = fmt.replace("%-", "%#")
            try:
                return __import__("time").strftime(fmt)
            except ValueError:
                return __import__("time").strftime("%H:%M:%S")
        if name == "cpu":
            return _pct(_cpu_value(stats, _cpu_index(rest)), config.pad_percents)
        if name == "freq":
            return "n/a" if stats.freq_mhz is None else f"{stats.freq_mhz:.0f}"
        if name == "freq_g":
            return "n/a" if stats.freq_mhz is None else f"{stats.freq_mhz / 1000:.2f} GHz"
        if name in {"acpitemp", "hwmon"}:
            return "n/a" if stats.temp is None else f"{stats.temp:.0f}°C"
        if name == "cpu_count":
            count = __import__("psutil").cpu_count() or 0
            return str(count)
        if name == "mem":
            return human_bytes(stats.mem_used, short)
        if name in {"memmax", "memtotal"}:
            return human_bytes(stats.mem_total, short)
        if name in {"memfree", "memeasyfree"}:
            return human_bytes(max(0, stats.mem_total - stats.mem_used), short)
        if name == "memperc":
            return _pct(stats.mem_percent, config.pad_percents)
        if name == "swap":
            return human_bytes(stats.swap_used, short)
        if name == "swapmax":
            return human_bytes(stats.swap_total, short)
        if name == "swapfree":
            return human_bytes(max(0, stats.swap_total - stats.swap_used), short)
        if name == "swapperc":
            return _pct(stats.swap_percent, config.pad_percents)
        if name in {"fs_used", "fs_free", "fs_size", "fs_used_perc", "fs_free_perc", "fs_type"}:
            usage = stats.disk(rest or "/")
            if usage is None:
                return "n/a"
            if name == "fs_used":
                return human_bytes(usage.used, short)
            if name == "fs_free":
                return human_bytes(usage.free, short)
            if name == "fs_size":
                return human_bytes(usage.total, short)
            if name == "fs_used_perc":
                return _pct(usage.percent, config.pad_percents)
            if name == "fs_free_perc":
                free = 100 - usage.percent
                return _pct(free, config.pad_percents)
            return _filesystem_type(rest or "/")
        if name in {"downspeed", "upspeed", "downspeedf", "upspeedf", "totaldown", "totalup", "addr", "iface"}:
            iface = rest.strip()
            down, up = stats.nic_speed(iface)
            total_down, total_up = stats.nic_total(iface)
            if name == "downspeed":
                return human_bytes(down, short) + "/s"
            if name == "upspeed":
                return human_bytes(up, short) + "/s"
            if name == "downspeedf":
                return f"{down / 1024:.1f}"
            if name == "upspeedf":
                return f"{up / 1024:.1f}"
            if name == "totaldown":
                return human_bytes(total_down, short)
            if name == "totalup":
                return human_bytes(total_up, short)
            if name == "addr":
                return stats.nic_addr(iface) or "—"
            return iface or stats.iface or "—"
        if name in {"diskio", "diskio_read", "diskio_write"}:
            if name == "diskio_read":
                return human_bytes(stats.disk_read, short) + "/s"
            if name == "diskio_write":
                return human_bytes(stats.disk_write, short) + "/s"
            return (
                human_bytes(stats.disk_read, short)
                + "/s  "
                + human_bytes(stats.disk_write, short)
                + "/s"
            )
        if name == "processes":
            return str(stats.process_count)
        if name == "running_processes":
            return str(stats.running_count)
        if name == "threads":
            return str(stats.thread_count)
        if name == "top":
            return _top(stats, rest, False, config.top_name_width)
        if name == "top_mem":
            return _top(stats, rest, True, config.top_name_width)
        if name == "battery":
            return _battery_text(stats)
        if name == "battery_percent":
            percent = float(stats.battery.percent) if stats.battery else 0
            return _pct(percent, config.pad_percents)
        if name in {"battery_time", "battery_short"}:
            if name == "battery_short":
                if stats.battery is None:
                    return "AC"
                return f"{float(stats.battery.percent):.0f}%"
            return _battery_time(stats)
        if name == "loadavg":
            if not stats.loadavg:
                return "n/a"
            return ", ".join(f"{value:.2f}" for value in stats.loadavg)
        if name == "exec":
            return _run_exec(rest, 0)
        if name in {"execi", "texeci"}:
            interval_text, _, command = rest.partition(" ")
            try:
                interval = float(interval_text)
            except ValueError:
                interval = config.update_interval
                command = rest
            return _run_exec(command, max(interval, 0))
        return None


def expand(config: Config, stats: Stats, scale: float) -> tuple[list[list[Token]], list[str]]:
    expander = Expander(config, stats, scale)
    return expander.expand(config.text), expander.unknown
