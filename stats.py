"""Live Windows system stats for the Conky text engine."""

from __future__ import annotations

import os
import platform
import socket
import sys
import time
import winreg
from collections import deque
from dataclasses import dataclass

import psutil


SKIP_PROCESSES = {"system idle process", "idle"}
VIRTUAL_NICS = (
    "loopback",
    "vethernet",
    "vmware",
    "virtualbox",
    "vbox",
    "bluetooth",
    "teredo",
    "isatap",
    "wsl",
    "hyper-v",
    "default switch",
    "npcap",
    "tunnel",
)


@dataclass
class ProcessRow:
    pid: int
    name: str
    cpu: float
    mem: float


def _windows_label() -> str:
    version = sys.getwindowsversion()
    base = "Windows 11" if version.build >= 22000 else "Windows 10" if version.build >= 10240 else "Windows"
    edition = ""
    display = ""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        ) as key:
            product = str(winreg.QueryValueEx(key, "ProductName")[0])
            edition = product.replace("Windows 10", "").replace("Windows 11", "").strip()
            try:
                display = str(winreg.QueryValueEx(key, "DisplayVersion")[0])
            except OSError:
                display = ""
    except OSError:
        pass
    return " ".join(part for part in (base, display, edition) if part)


def human_bytes(num: float, short: bool = True) -> str:
    value = float(max(num, 0))
    units = ["B", "K", "M", "G", "T"] if short else ["B", "KiB", "MiB", "GiB", "TiB"]
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1
    if index == 0:
        text = str(int(value))
    elif value >= 100:
        text = f"{value:.0f}"
    elif value >= 10:
        text = f"{value:.1f}"
    else:
        text = f"{value:.2f}"
    if short:
        return text + units[index]
    return f"{text} {units[index]}"


def format_uptime(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def win_path(spec: str) -> str:
    text = (spec or "/").strip().strip('"')
    if text in {"", "/", "\\"}:
        return os.environ.get("SystemDrive", "C:") + "\\"
    if len(text) == 1 and text.isalpha():
        return text.upper() + ":\\"
    if len(text) == 2 and text[1] == ":" and text[0].isalpha():
        return text.upper() + "\\"
    if len(text) >= 3 and text[1] == ":" and text[0].isalpha():
        return text[0].upper() + text[1:]
    if text.startswith("/") and len(text) > 2 and text[2] == "/" and text[1].isalpha():
        return text[1].upper() + ":" + text[2:].replace("/", "\\")
    if text.startswith("/"):
        return os.environ.get("SystemDrive", "C:") + text.replace("/", "\\")
    return text


class Stats:
    def __init__(self) -> None:
        version = sys.getwindowsversion()
        self.nodename = platform.node() or socket.gethostname()
        self.sysname = _windows_label()
        self.kernel = f"{version.major}.{version.minor}.{version.build}"
        self.machine = platform.machine()
        self.username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        self.boot_time = psutil.boot_time()
        self.uptime_seconds = 0.0
        self.cpu = 0.0
        self.cpu_cores: list[float] = []
        self.freq_mhz: float | None = None
        self.mem_used = 0
        self.mem_total = 0
        self.mem_percent = 0.0
        self.swap_used = 0
        self.swap_total = 0
        self.swap_percent = 0.0
        self.net_down = 0.0
        self.net_up = 0.0
        self.net_total_down = 0
        self.net_total_up = 0
        self.iface = ""
        self.addr = ""
        self.addrs: dict[str, str] = {}
        self.speeds: dict[str, tuple[float, float]] = {}
        self.totals: dict[str, tuple[int, int]] = {}
        self.battery = None
        self.process_count = 0
        self.running_count = 0
        self.thread_count = 0
        self.top_cpu: list[ProcessRow] = []
        self.top_mem: list[ProcessRow] = []
        self.disk_read = 0.0
        self.disk_write = 0.0
        self.loadavg: tuple[float, float, float] | None = None
        self.temp: float | None = None
        self.history: dict[str, deque[float]] = {}
        self.need_processes = False
        self.cpu_avg_samples = 2
        self.net_avg_samples = 2
        self._last_time = 0.0
        self._last_net: dict[str, tuple[int, int]] = {}
        self._last_disk: tuple[int, int] | None = None
        self._cpu_raw: deque[float] = deque(maxlen=32)
        self._core_raw: deque[list[float]] = deque(maxlen=32)
        self._down_raw: deque[float] = deque(maxlen=32)
        self._up_raw: deque[float] = deque(maxlen=32)
        self._primed = False
        self._temp_checked = False
        self._disk_cache: dict[str, object] = {}

    def configure(self, text: str) -> None:
        lowered = text.lower()
        self.need_processes = any(
            token in lowered
            for token in ("${top", "$top", "${processes", "${running_processes", "${threads")
        )

    def _history(self, key: str) -> deque[float]:
        if key not in self.history:
            self.history[key] = deque(maxlen=600)
        return self.history[key]

    def _push(self, key: str, value: float) -> None:
        self._history(key).append(value)

    def series(self, key: str) -> list[float]:
        return list(self.history.get(key, ()))

    def _virtual_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(part in lowered for part in VIRTUAL_NICS)

    def _choose_iface(self, counters: dict, stats_up: dict[str, bool]) -> str:
        names = [name for name in counters if name.lower() != "loopback pseudo-interface"]
        physical = [name for name in names if not self._virtual_name(name)]
        pool = physical or names

        def rank(name: str) -> tuple[int, int, int]:
            info = counters[name]
            traffic = int(info.bytes_recv + info.bytes_sent)
            has_ip = 1 if self.addrs.get(name) else 0
            is_up = 1 if stats_up.get(name, True) else 0
            return (is_up, has_ip, traffic)

        if not pool:
            return ""
        return max(pool, key=rank)

    def _sample_processes(self) -> None:
        rows: list[ProcessRow] = []
        running = 0
        threads = 0
        own_pid = os.getpid()
        for proc in psutil.process_iter(["pid", "name", "status", "num_threads"]):
            try:
                info = proc.info
                name = info.get("name") or ""
                if not name or info.get("pid") == own_pid or name.lower() in SKIP_PROCESSES:
                    continue
                cpu = proc.cpu_percent(interval=None)
                mem = info.get("memory_percent")
                if mem is None:
                    mem = proc.memory_percent()
                rows.append(
                    ProcessRow(
                        pid=int(info.get("pid") or 0),
                        name=name[:-4] if name.lower().endswith(".exe") else name,
                        cpu=float(cpu or 0),
                        mem=float(mem or 0),
                    )
                )
                status = (info.get("status") or "").lower()
                if status == psutil.STATUS_RUNNING:
                    running += 1
                threads += int(info.get("num_threads") or 0)
            except (psutil.Error, OSError, TypeError, ValueError):
                continue
        self.process_count = len(rows)
        self.running_count = running
        self.thread_count = threads
        self.top_cpu = sorted(rows, key=lambda row: row.cpu, reverse=True)[:12]
        self.top_mem = sorted(rows, key=lambda row: row.mem, reverse=True)[:12]

    def sample(self) -> None:
        now = time.monotonic()
        dt = now - self._last_time if self._last_time else 0.0
        self.uptime_seconds = max(0.0, time.time() - self.boot_time)
        self._disk_cache.clear()

        percpu = [float(value) for value in psutil.cpu_percent(interval=None, percpu=True)]
        total = float(psutil.cpu_percent(interval=None))
        if self._last_time:
            self._cpu_raw.append(total)
            self._core_raw.append(percpu)
            samples = list(self._cpu_raw)[-max(1, self.cpu_avg_samples) :]
            self.cpu = sum(samples) / len(samples)
            width = len(self._core_raw[-1])
            averaged: list[float] = []
            for index in range(width):
                values = [sample[index] for sample in list(self._core_raw)[-self.cpu_avg_samples :] if index < len(sample)]
                averaged.append(sum(values) / len(values) if values else 0.0)
            self.cpu_cores = averaged
            self._push("cpu", self.cpu)
            for index, value in enumerate(self.cpu_cores, start=1):
                self._push(f"cpu{index}", value)
        else:
            self.cpu_cores = percpu

        freq = psutil.cpu_freq()
        self.freq_mhz = float(freq.current) if freq and freq.current else None

        memory = psutil.virtual_memory()
        self.mem_total = int(memory.total)
        self.mem_used = int(max(0, memory.total - memory.available))
        self.mem_percent = float(memory.percent)
        self._push("mem", self.mem_percent)
        swap = psutil.swap_memory()
        self.swap_total = int(swap.total)
        self.swap_used = int(swap.used)
        self.swap_percent = float(swap.percent)

        self.addrs = {}
        for name, addresses in psutil.net_if_addrs().items():
            for address in addresses:
                if address.family != socket.AF_INET:
                    continue
                ip = address.address
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue
                self.addrs[name] = ip
                break

        try:
            nic_stats = {name: item.isup for name, item in psutil.net_if_stats().items()}
        except psutil.Error:
            nic_stats = {}
        counters = psutil.net_io_counters(pernic=True)
        self.iface = self._choose_iface(counters, nic_stats) or self.iface
        self.speeds = {}
        self.totals = {}
        if dt > 0 and self._last_net:
            for name, info in counters.items():
                previous = self._last_net.get(name)
                if not previous:
                    self.speeds[name] = (0.0, 0.0)
                    continue
                down = max(0.0, (info.bytes_recv - previous[0]) / dt)
                up = max(0.0, (info.bytes_sent - previous[1]) / dt)
                self.speeds[name] = (down, up)
        for name, info in counters.items():
            self.totals[name] = (int(info.bytes_recv), int(info.bytes_sent))
        self._last_net = {
            name: (int(info.bytes_recv), int(info.bytes_sent)) for name, info in counters.items()
        }
        if self.iface and self.iface in self.speeds:
            down, up = self.speeds[self.iface]
        else:
            down = up = 0.0
        if dt > 0:
            self._down_raw.append(down)
            self._up_raw.append(up)
        if self._down_raw:
            width_down = max(1, min(len(self._down_raw), self.net_avg_samples))
            width_up = max(1, min(len(self._up_raw), self.net_avg_samples))
            self.net_down = sum(list(self._down_raw)[-width_down:]) / width_down
            self.net_up = sum(list(self._up_raw)[-width_up:]) / width_up
        self.net_total_down = self.totals.get(self.iface, (0, 0))[0]
        self.net_total_up = self.totals.get(self.iface, (0, 0))[1]
        self.addr = self.addrs.get(self.iface, "")
        if dt > 0:
            self._push("down", self.net_down)
            self._push("up", self.net_up)
            for name, (nic_down, nic_up) in self.speeds.items():
                self._push(f"down:{name}", nic_down)
                self._push(f"up:{name}", nic_up)

        try:
            disk = psutil.disk_io_counters()
        except psutil.Error:
            disk = None
        if disk is not None and self._last_disk and dt > 0:
            self.disk_read = max(0.0, (disk.read_bytes - self._last_disk[0]) / dt)
            self.disk_write = max(0.0, (disk.write_bytes - self._last_disk[1]) / dt)
        if disk is not None:
            self._last_disk = (int(disk.read_bytes), int(disk.write_bytes))
        self._push("disk", self.disk_read + self.disk_write)

        try:
            self.battery = psutil.sensors_battery()
        except psutil.Error:
            self.battery = None

        if not self._temp_checked:
            self._temp_checked = True
            sensors = {}
            reader = getattr(psutil, "sensors_temperatures", None)
            if reader is not None:
                try:
                    sensors = reader() or {}
                except (psutil.Error, OSError):
                    sensors = {}
            for entries in sensors.values():
                if entries:
                    self.temp = float(entries[0].current)
                    break

        loadavg = getattr(psutil, "getloadavg", None)
        if loadavg is None:
            self.loadavg = None
        else:
            try:
                self.loadavg = tuple(float(value) for value in loadavg())  # type: ignore[assignment]
            except (OSError, AttributeError):
                self.loadavg = None

        if self.need_processes:
            self._sample_processes()
        else:
            try:
                self.process_count = len(psutil.pids())
            except psutil.Error:
                self.process_count = 0

        self._last_time = now
        self._primed = True

    def prime(self) -> None:
        self.sample()
        time.sleep(0.35)
        self.sample()

    def disk(self, spec: str):
        path = win_path(spec)
        if path not in self._disk_cache:
            try:
                self._disk_cache[path] = psutil.disk_usage(path)
            except (psutil.Error, OSError):
                self._disk_cache[path] = None
        return self._disk_cache[path]

    def nic_speed(self, name: str) -> tuple[float, float]:
        if not name or name == self.iface:
            return self.net_down, self.net_up
        return self.speeds.get(name, (0.0, 0.0))

    def nic_total(self, name: str) -> tuple[int, int]:
        target = name or self.iface
        return self.totals.get(target, (0, 0))

    def nic_addr(self, name: str) -> str:
        target = name or self.iface
        return self.addrs.get(target, "")
