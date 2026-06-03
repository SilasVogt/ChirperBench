from __future__ import annotations

import re
import statistics
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SAMPLE_FIELDS = ("power_w", "vram_mb", "vram_total_mb", "gpu_busy_percent")


@dataclass(frozen=True)
class TelemetryReader:
    provider: str
    status: str
    reason: str = ""

    @property
    def available(self) -> bool:
        return self.status == "ok"

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "reason": self.reason,
        }

    def sample(self) -> dict[str, float | str | None]:
        return {"timestamp": time.time()}


@dataclass(frozen=True)
class AmdSysfsReader(TelemetryReader):
    card: str = ""
    device_path: str = ""
    vendor: str = ""
    pci_address: str = ""
    driver: str = ""
    power_path: str = ""
    vram_used_path: str = ""
    vram_total_path: str = ""
    gpu_busy_path: str = ""

    @classmethod
    def from_device(cls, device_path: Path, card: str) -> "AmdSysfsReader":
        vendor = _read_text(device_path / "vendor")
        if vendor.lower() != "0x1002":
            return cls(
                provider="amd-sysfs",
                status="unavailable",
                reason=f"{card} is not an AMD GPU.",
                card=card,
                device_path=str(device_path),
                vendor=vendor,
            )

        power_path = _find_power_path(device_path)
        vram_used_path = device_path / "mem_info_vram_used"
        vram_total_path = device_path / "mem_info_vram_total"
        gpu_busy_path = device_path / "gpu_busy_percent"
        metric_paths = [power_path, vram_used_path, vram_total_path, gpu_busy_path]
        if not any(path and path.exists() for path in metric_paths):
            return cls(
                provider="amd-sysfs",
                status="unavailable",
                reason=f"{card} has no readable AMD telemetry sysfs counters.",
                card=card,
                device_path=str(device_path),
                vendor=vendor,
                pci_address=device_path.resolve().name,
                driver=_read_driver_name(device_path),
            )

        return cls(
            provider="amd-sysfs",
            status="ok",
            card=card,
            device_path=str(device_path),
            vendor=vendor,
            pci_address=device_path.resolve().name,
            driver=_read_driver_name(device_path),
            power_path=str(power_path) if power_path else "",
            vram_used_path=str(vram_used_path) if vram_used_path.exists() else "",
            vram_total_path=str(vram_total_path) if vram_total_path.exists() else "",
            gpu_busy_path=str(gpu_busy_path) if gpu_busy_path.exists() else "",
        )

    @classmethod
    def from_drm_root(cls, drm_root: Path = Path("/sys/class/drm")) -> "AmdSysfsReader":
        for card_path in sorted(drm_root.glob("card*")):
            if not re.fullmatch(r"card\d+", card_path.name):
                continue
            device_path = card_path / "device"
            if not device_path.exists():
                continue
            reader = cls.from_device(device_path, card_path.name)
            if reader.status == "ok":
                return reader
        return cls(
            provider="amd-sysfs",
            status="unavailable",
            reason=f"No AMD GPU with readable sysfs telemetry found under {drm_root}.",
        )

    def describe(self) -> dict[str, Any]:
        data = super().describe()
        data.update(
            {
                "card": self.card,
                "vendor": self.vendor,
                "pci_address": self.pci_address,
                "driver": self.driver,
                "device_path": self.device_path,
            }
        )
        total_mb = _read_bytes_as_mb(Path(self.vram_total_path)) if self.vram_total_path else None
        if total_mb is not None:
            data["vram_total_mb"] = round(total_mb, 1)
        return data

    def sample(self) -> dict[str, float | str | None]:
        return {
            "timestamp": time.time(),
            "power_w": _read_microwatts_as_watts(Path(self.power_path)) if self.power_path else None,
            "vram_mb": _read_bytes_as_mb(Path(self.vram_used_path)) if self.vram_used_path else None,
            "vram_total_mb": _read_bytes_as_mb(Path(self.vram_total_path)) if self.vram_total_path else None,
            "gpu_busy_percent": _read_float(Path(self.gpu_busy_path)) if self.gpu_busy_path else None,
        }


class TelemetryRecorder:
    def __init__(self, reader: TelemetryReader, interval_seconds: float = 0.5):
        self.reader = reader
        self.interval_seconds = max(0.1, float(interval_seconds))
        self.samples: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._started_at = 0.0
        self._stopped_at = 0.0
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._started_at = time.monotonic()
        if not self.reader.available:
            return
        self._capture()
        self._thread = threading.Thread(target=self._run, name="chirperbench-telemetry", daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        if self.reader.available:
            self._capture()
            self._stop_event.set()
            if self._thread is not None:
                self._thread.join(timeout=max(1.0, self.interval_seconds * 2))
        self._stopped_at = time.monotonic()
        return self.summary()

    def summary(self) -> dict[str, Any]:
        metrics = _summarize_samples(self.samples)
        status = self.reader.status
        if self.reader.available and not self.samples:
            status = "unavailable"
        return {
            "status": status,
            "provider": self.reader.provider,
            "reason": self.reader.reason,
            "device": self.reader.describe(),
            "sample_count": len(self.samples),
            "elapsed_seconds": round(max(0.0, self._stopped_at - self._started_at), 4)
            if self._stopped_at and self._started_at
            else 0.0,
            "metrics": metrics,
            "errors": list(self.errors),
        }

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self._capture()

    def _capture(self) -> None:
        try:
            sample = self.reader.sample()
        except OSError as exc:
            self.errors.append(str(exc))
            return
        if any(sample.get(field) is not None for field in SAMPLE_FIELDS):
            with self._lock:
                self.samples.append(sample)


def build_telemetry_reader(mode: str) -> TelemetryReader:
    if mode == "off":
        return TelemetryReader(provider="none", status="disabled", reason="Telemetry disabled.")
    if mode in {"auto", "amd-sysfs"}:
        return AmdSysfsReader.from_drm_root()
    return TelemetryReader(provider=mode, status="unavailable", reason=f"Unknown telemetry mode: {mode}")


def _summarize_samples(samples: list[dict[str, Any]]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    power = _values(samples, "power_w")
    vram = _values(samples, "vram_mb")
    vram_total = _values(samples, "vram_total_mb")
    gpu_busy = _values(samples, "gpu_busy_percent")

    if power:
        metrics["power_w_avg"] = round(sum(power) / len(power), 2)
        metrics["power_w_peak"] = round(max(power), 2)
    if vram:
        metrics["vram_mb_avg"] = round(sum(vram) / len(vram), 1)
        metrics["vram_mb_peak"] = round(max(vram), 1)
    if vram_total:
        metrics["vram_total_mb"] = round(max(vram_total), 1)
    if gpu_busy:
        metrics["gpu_busy_percent_avg"] = round(sum(gpu_busy) / len(gpu_busy), 1)
        metrics["gpu_busy_percent_peak"] = round(max(gpu_busy), 1)
    if power and samples:
        elapsed_values = _values(samples, "timestamp")
        if len(elapsed_values) >= 2:
            duration_hours = max(0.0, max(elapsed_values) - min(elapsed_values)) / 3600
            metrics["energy_wh_estimate"] = round(statistics.mean(power) * duration_hours, 4)
    return metrics


def _values(samples: list[dict[str, Any]], key: str) -> list[float]:
    values = []
    for sample in samples:
        value = sample.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def _find_power_path(device_path: Path) -> Path | None:
    hwmon_root = device_path / "hwmon"
    if not hwmon_root.exists():
        return None
    candidates: list[Path] = []
    for hwmon in sorted(hwmon_root.glob("hwmon*")):
        if _read_text(hwmon / "name") == "amdgpu":
            candidates.extend([hwmon / "power1_average", hwmon / "power1_input"])
    for hwmon in sorted(hwmon_root.glob("hwmon*")):
        candidates.extend([hwmon / "power1_average", hwmon / "power1_input"])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_driver_name(device_path: Path) -> str:
    driver = device_path / "driver"
    if not driver.exists():
        return ""
    try:
        return driver.resolve().name
    except OSError:
        return ""


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_float(path: Path) -> float | None:
    raw = _read_text(path)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _read_bytes_as_mb(path: Path) -> float | None:
    value = _read_float(path)
    if value is None:
        return None
    return value / (1024 * 1024)


def _read_microwatts_as_watts(path: Path) -> float | None:
    value = _read_float(path)
    if value is None:
        return None
    return value / 1_000_000

