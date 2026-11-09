"""Run Conky Windows from a config file."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageDraw

from . import __version__
from .config import load_config
from .render import render_frame, render_message
from .stats import Stats
from .variables import expand
from .window import LayeredWindow, dpi_scale, message_box, work_area

CREATE_NO_WINDOW = 0x08000000
APP_DIR = Path(os.environ.get("APPDATA", ".")) / "ConkyWindows"
STATE_PATH = APP_DIR / "state.json"
STARTUP_LINK = (
    Path(os.environ.get("APPDATA", "."))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
    / "Conky Windows.lnk"
)

ID_RELOAD = 1
ID_EDIT = 2
ID_CLICK = 3
ID_NORMAL = 4
ID_DESKTOP = 5
ID_DOCK = 6
ID_RESET = 7
ID_STARTUP = 8
ID_QUIT = 9
ID_USE_CONFIG = 10


def log(message: str) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + message
    print(line, flush=True)
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        path = APP_DIR / "conky.log"
        if path.exists() and path.stat().st_size > 200_000:
            path.write_text("", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _bundled_config() -> Path | None:
    candidate = Path(__file__).resolve().parents[1] / "conkyrc"
    return candidate if candidate.exists() else None


def resolve_config(explicit: str) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise SystemExit(f"Config not found: {path}")
        return path.resolve()
    local = Path.cwd() / "conkyrc"
    if local.exists():
        return local.resolve()
    bundled = _bundled_config()
    if bundled:
        return bundled.resolve()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    destination = APP_DIR / "conkyrc"
    if not destination.exists():
        destination.write_text(
            "alignment top_right\ngap_x 24\ngap_y 48\nfont Segoe UI:size=14\nTEXT\n${nodename}\nCPU ${cpu}%\n",
            encoding="utf-8",
        )
    return destination.resolve()


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(data: dict) -> None:
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        log(f"Could not save state: {exc}")


def _single_instance(config_path: Path) -> bool:
    digest = hashlib.sha1(str(config_path).lower().encode("utf-8")).hexdigest()[:20]
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    dll.CreateMutexW.restype = wintypes.HANDLE
    handle = dll.CreateMutexW(None, False, f"Local\\ConkyWindows_{digest}")
    if ctypes.get_last_error() == 183:
        return False
    _single_instance.handle = handle  # type: ignore[attr-defined]
    return True


def _write_icon(path: Path) -> None:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([2, 2, 61, 61], radius=16, fill=(23, 23, 26, 255))
    draw.rounded_rectangle([4, 4, 59, 59], radius=14, outline=(100, 210, 255, 255), width=3)
    draw.rounded_rectangle([16, 38, 24, 48], radius=2, fill=(100, 210, 255, 255))
    draw.rounded_rectangle([28, 26, 36, 48], radius=2, fill=(48, 209, 88, 255))
    draw.rounded_rectangle([40, 16, 48, 48], radius=2, fill=(255, 159, 10, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])


class App:
    def __init__(self, config_path: Path, scale: float) -> None:
        self.config_path = config_path
        self.config = load_config(str(config_path))
        self.mtime = config_path.stat().st_mtime
        self.error = ""
        self.stats = Stats()
        self._apply_stats_options()
        self.user_scale = scale if scale > 0 else dpi_scale()
        self.fit = 1.0
        self.fitted = False
        self.image = None
        self.x = 0
        self.y = 0
        self.manual = False
        self.click_through = self.config.click_through
        self.window_type = self._normalize_type(self.config.own_window_type)
        self.click_override = False
        self.type_override = False
        self._drag_origin = (0, 0)
        self._drag_pos = (0, 0)
        self._moved = False
        self._fast_ticks = 2
        self.window = LayeredWindow(self)
        saved = _load_state().get(str(config_path), {})
        if saved.get("manual_position"):
            self.manual = True
            self.x = int(saved.get("x", 0))
            self.y = int(saved.get("y", 0))
        if "click_through" in saved:
            self.click_through = bool(saved["click_through"])
            self.click_override = True
        if saved.get("window_type"):
            self.window_type = self._normalize_type(str(saved["window_type"]))
            self.type_override = True

    def _apply_stats_options(self) -> None:
        self.stats.configure(self.config.text)
        self.stats.cpu_avg_samples = self.config.cpu_avg_samples
        self.stats.net_avg_samples = self.config.net_avg_samples

    def _normalize_type(self, value: str) -> str:
        value = value.lower()
        if value in {"dock", "panel", "override"}:
            return "dock"
        if value == "desktop":
            return "desktop"
        return "normal"

    def run(self) -> None:
        log(f"Conky Windows {__version__} — {self.config_path}")
        self.window.create()
        # Paint the panel before the first process walk, which is the slow sample.
        wants_processes = self.stats.need_processes
        self.stats.need_processes = False
        self.stats.sample()
        self.redraw()
        self.window.show()
        if not self.window.blit_ok:
            self.window.show()
            self.redraw()
        self.stats.need_processes = wants_processes
        self.window.set_click_through(self.click_through)
        self.window.set_z_order(self.window_type)
        self.redraw()
        icon_path = APP_DIR / "tray.ico"
        try:
            _write_icon(icon_path)
            self.window.load_icon(str(icon_path))
        except Exception as exc:
            log(f"Tray icon was not created: {exc}")
            self.window.load_icon("")
        if not self.window.add_tray("Conky Windows"):
            log(f"Tray icon was not added (error {ctypes.get_last_error()}). Use right-click on the panel to quit.")
        else:
            welcomed = APP_DIR / "welcomed"
            if not welcomed.exists():
                self.window.balloon(
                    "Conky Windows is running",
                    "Right-click the panel or this icon to move it, edit it, or quit.",
                )
                try:
                    welcomed.write_text("ok", encoding="utf-8")
                except OSError:
                    pass
        self.window.set_timer(0.45)
        self.window.loop()

    def on_timer(self) -> None:
        try:
            self._reload_if_changed()
            self.stats.sample()
            self.redraw()
            if self._fast_ticks:
                self._fast_ticks -= 1
                if self._fast_ticks == 0:
                    self.window.set_timer(self.config.update_interval)
        except Exception:
            details = traceback.format_exc()
            log(details)
            self._show_error("Update failed", details.splitlines()[-1])

    def on_drag_start(self, x: int, y: int) -> None:
        self._drag_origin = (x, y)
        self._drag_pos = (self.x, self.y)
        self._moved = False

    def on_drag(self, x: int, y: int) -> None:
        dx = x - self._drag_origin[0]
        dy = y - self._drag_origin[1]
        if abs(dx) + abs(dy) < 4:
            return
        self._moved = True
        self.manual = True
        self.x = self._drag_pos[0] + dx
        self.y = self._drag_pos[1] + dy
        if self.image is not None:
            self.window.present(self.image, int(self.x), int(self.y))

    def on_drag_end(self) -> None:
        if self._moved:
            self._persist()

    def on_context_menu(self) -> None:
        startup = STARTUP_LINK.exists()
        choice = self.window.popup(
            [
                {"id": ID_RELOAD, "label": "Reload config"},
                {"id": ID_EDIT, "label": "Edit config"},
                {"separator": True},
                {"id": ID_CLICK, "label": "Click-through", "checked": self.click_through},
                {
                    "label": "Window",
                    "children": [
                        {"id": ID_NORMAL, "label": "Normal", "checked": self.window_type == "normal"},
                        {"id": ID_DESKTOP, "label": "On the desktop", "checked": self.window_type == "desktop"},
                        {"id": ID_DOCK, "label": "Always on top", "checked": self.window_type == "dock"},
                    ],
                },
                {"id": ID_RESET, "label": "Reset position"},
                {"id": ID_USE_CONFIG, "label": "Use settings from config"},
                {"separator": True},
                {"id": ID_STARTUP, "label": "Start with Windows", "checked": startup},
                {"id": ID_QUIT, "label": "Quit"},
            ]
        )
        self._handle_menu(choice)

    def on_edit(self) -> None:
        self._open_config()

    def on_blit_error(self, code: int) -> None:
        log(f"The desktop window could not be drawn (Windows error {code}).")

    def _handle_menu(self, choice: int) -> None:
        if choice == ID_RELOAD:
            self._reload_now()
        elif choice == ID_EDIT:
            self._open_config()
        elif choice == ID_CLICK:
            self.click_through = not self.click_through
            self.click_override = True
            self.window.set_click_through(self.click_through)
            self._persist()
            if self.click_through:
                self.window.balloon(
                    "Click-through is on",
                    "The panel ignores the mouse. Right-click the tray icon to turn it off.",
                )
        elif choice in {ID_NORMAL, ID_DESKTOP, ID_DOCK}:
            self.window_type = {ID_NORMAL: "normal", ID_DESKTOP: "desktop", ID_DOCK: "dock"}[choice]
            self.type_override = True
            self.window.set_z_order(self.window_type)
            self.redraw()
            self._persist()
        elif choice == ID_RESET:
            self.manual = False
            self.fitted = False
            self.fit = 1.0
            self._persist()
            self.redraw()
        elif choice == ID_USE_CONFIG:
            self.click_override = False
            self.type_override = False
            self.click_through = self.config.click_through
            self.window_type = self._normalize_type(self.config.own_window_type)
            self.window.set_click_through(self.click_through)
            self.window.set_z_order(self.window_type)
            self._persist()
            self.redraw()
        elif choice == ID_STARTUP:
            self._set_startup(not STARTUP_LINK.exists())
        elif choice == ID_QUIT:
            self.window.close()

    def _reload_if_changed(self) -> None:
        try:
            mtime = self.config_path.stat().st_mtime
        except OSError:
            return
        if mtime != self.mtime:
            self._reload_now()

    def _reload_now(self) -> None:
        self.mtime = self.config_path.stat().st_mtime
        try:
            self.config = load_config(str(self.config_path))
            self._apply_stats_options()
            self.error = ""
            self.fitted = False
            self.fit = 1.0
            if not self.click_override:
                self.click_through = self.config.click_through
                self.window.set_click_through(self.click_through)
            if not self.type_override:
                self.window_type = self._normalize_type(self.config.own_window_type)
                self.window.set_z_order(self.window_type)
            self.window.set_timer(self.config.update_interval)
            self._fast_ticks = 0
        except Exception as exc:
            self.error = str(exc)
            log(f"Config was not reloaded: {exc}")

    def _open_config(self) -> None:
        try:
            os.startfile(self.config_path)  # type: ignore[attr-defined]
        except OSError:
            subprocess.Popen(["notepad.exe", str(self.config_path)])

    def _set_startup(self, enabled: bool) -> None:
        if not enabled:
            try:
                STARTUP_LINK.unlink(missing_ok=True)
            except OSError as exc:
                log(f"Could not remove the startup shortcut: {exc}")
            return
        exe = Path(sys.executable)
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            exe = pythonw
        arguments = f'-m conky_windows --config "{self.config_path}"'
        script = "; ".join(
            [
                f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({_ps_quote(str(STARTUP_LINK))})",
                f"$s.TargetPath = {_ps_quote(str(exe))}",
                f"$s.Arguments = {_ps_quote(arguments)}",
                f"$s.WorkingDirectory = {_ps_quote(str(self.config_path.parent))}",
                "$s.Description = 'Conky Windows'",
                "$s.Save()",
            ]
        )
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        if completed.returncode != 0:
            log(completed.stderr.strip() or "Could not create the startup shortcut.")

    def _persist(self) -> None:
        data = _load_state()
        entry: dict = {}
        if self.manual:
            entry["manual_position"] = True
            entry["x"] = int(self.x)
            entry["y"] = int(self.y)
        if self.click_override:
            entry["click_through"] = self.click_through
        if self.type_override:
            entry["window_type"] = self.window_type
        key = str(self.config_path)
        if entry:
            data[key] = entry
        else:
            data.pop(key, None)
        _save_state(data)

    def _show_error(self, title: str, body: str) -> None:
        image = render_message(title, body[:240], self.user_scale)
        self.image = image
        if not self.manual:
            self.x, self.y = self._place(image.width, image.height)
        self.window.present(image, int(self.x), int(self.y))

    def redraw(self) -> None:
        scale = self.user_scale * self.fit
        if self.error:
            image = render_message("Config problem", self.error[:240], scale)
        else:
            image = render_frame(self.config, self.stats, scale)
            work = work_area(self.config.monitor)
            limit = max(200, (work[3] - work[1]) - 24)
            if image.height > limit and not self.fitted and self.fit > 0.55:
                self.fit *= limit / image.height
                self.fitted = True
                image = render_frame(self.config, self.stats, self.user_scale * self.fit)
        self.image = image
        if not self.manual:
            self.x, self.y = self._place(image.width, image.height)
        self.window.present(image, int(self.x), int(self.y))

    def _place(self, width: int, height: int) -> tuple[int, int]:
        left, top, right, bottom = work_area(self.config.monitor)
        scale = self.user_scale * self.fit
        gap_x = int(round(self.config.gap_x * scale))
        gap_y = int(round(self.config.gap_y * scale))
        alignment = self.config.alignment.replace("-", "_")
        if alignment in {"", "none"}:
            return left + gap_x, top + gap_y
        vertical, _, horizontal = alignment.partition("_")
        if horizontal == "right":
            x = right - gap_x - width
        elif horizontal == "middle":
            x = (left + right - width) // 2
        else:
            x = left + gap_x
        if vertical == "bottom":
            y = bottom - gap_y - height
        elif vertical == "middle":
            y = (top + bottom - height) // 2
        else:
            y = top + gap_y
        return int(x), int(y)


def write_preview(config_path: Path, output: Path, scale: float) -> None:
    config = load_config(str(config_path))
    stats = Stats()
    stats.configure(config.text)
    stats.cpu_avg_samples = config.cpu_avg_samples
    stats.net_avg_samples = config.net_avg_samples
    stats.prime()
    used = scale if scale > 0 else dpi_scale()
    _lines, unknown = expand(config, stats, used)
    if unknown:
        print("Unrecognized variables:", ", ".join(unknown))
    image = render_frame(config, stats, used)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(
        f"Wrote {output} ({image.width}x{image.height}) at scale {used:.2f}. "
        f"{stats.nodename}: CPU {stats.cpu:.0f}%, RAM {stats.mem_percent:.0f}%, {stats.iface} {stats.addr}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Conky Windows desktop system monitor")
    parser.add_argument("--config", default="", help="Path to a Conky config. Defaults to ./conkyrc")
    parser.add_argument("--preview", default="", help="Render one frame to a PNG and exit")
    parser.add_argument("--scale", type=float, default=0, help="Override DPI scale, useful for previews")
    args = parser.parse_args(argv)
    config_path = resolve_config(args.config)
    if args.preview:
        write_preview(config_path, Path(args.preview), args.scale)
        return
    if not _single_instance(config_path):
        message_box(
            "Conky Windows is already running for this config.\n\n"
            "Right-click its tray icon, or the panel, to open the menu."
        )
        return
    try:
        App(config_path, args.scale).run()
    except Exception:
        details = traceback.format_exc()
        log(details)
        message_box(details[-900:], error=True)
