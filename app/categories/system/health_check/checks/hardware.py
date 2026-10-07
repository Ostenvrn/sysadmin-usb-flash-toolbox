"""
Проверка железа.
Ищет: высокую температуру, проблемы с CPU, батарею.
"""
import os
import subprocess

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-hardware")


def check_hardware() -> dict:
    """Проверяет железо."""
    result = {
        "category": "Железо",
        "status": "ok",
        "problems": [],
        "details": {},
    }

    # CPU
    result["details"]["cpu"] = _get_cpu_info()

    # Температура (Linux, если доступно)
    if os_detector.is_linux:
        temp = _get_cpu_temp_linux()
        if temp is not None:
            result["details"]["cpu_temp"] = temp
            if temp >= 90:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Температура CPU: {temp}°C (перегрев!)")
            elif temp >= 75:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Температура CPU: {temp}°C (высокая)")

    # Батарея (Linux, если ноутбук)
    if os_detector.is_linux:
        bat = _get_battery_linux()
        if bat:
            result["details"]["battery"] = bat
            if bat.get("percent") is not None and bat["percent"] < 20:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Батарея: {bat['percent']}% (низкий заряд)"
                )

    return result


def _get_cpu_info() -> dict:
    """Информация о CPU."""
    return {
        "cores": os.cpu_count(),
    }


def _get_cpu_temp_linux() -> float:
    """Температура CPU на Linux (через sensors или /sys)."""
    # Пробуем через /sys/class/thermal
    try:
        import glob
        for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
            try:
                with open(f"{zone}/type", "r") as f:
                    zone_type = f.read().strip()
                if "cpu" in zone_type.lower() or "x86" in zone_type.lower():
                    with open(f"{zone}/temp", "r") as f:
                        temp = int(f.read().strip()) / 1000
                    return round(temp, 1)
            except Exception:
                continue
    except Exception:
        pass
    return None


def _get_battery_linux() -> dict:
    """Информация о батарее на Linux."""
    import glob
    try:
        for bat in glob.glob("/sys/class/power_supply/BAT*"):
            info = {}
            try:
                with open(f"{bat}/capacity", "r") as f:
                    info["percent"] = int(f.read().strip())
                with open(f"{bat}/status", "r") as f:
                    info["status"] = f.read().strip()
                return info
            except Exception:
                continue
    except Exception:
        pass
    return {}
