"""
Проверка железа (CPU, температура, батарея).
Кроссплатформенно: Linux + Windows.
"""
import os
import glob

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-hardware")


def check_hardware() -> dict:
    result = {
        "category": "Железо",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    if os_detector.is_windows:
        result = _check_windows(result)
    elif os_detector.is_linux:
        result = _check_linux(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"ОС {os_detector.system} не поддерживается")

    return result


def _check_windows(result: dict) -> dict:
    """CPU, батарея на Windows."""
    ps_cmd = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$cpu = Get-CimInstance Win32_Processor; "
        "Write-Output \"$($cpu.Name)|$($cpu.NumberOfCores)|$($cpu.NumberOfLogicalProcessors)\""
    )
    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc == 0 and stdout.strip():
        parts = stdout.strip().split("|")
        if len(parts) >= 3:
            result["details"]["cpu"] = {
                "model": parts[0].strip(),
                "cores": int(parts[1]) if parts[1].isdigit() else 0,
                "threads": int(parts[2]) if parts[2].isdigit() else 0,
            }

    ps_cmd = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; "
        "if ($bat) { Write-Output \"$($bat.EstimatedChargeRemaining)|$($bat.BatteryStatus)\" } else { 'none' }"
    )
    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc == 0 and stdout.strip() and stdout.strip() != "none":
        parts = stdout.strip().split("|")
        if len(parts) >= 2:
            try:
                percent = int(parts[0])
                result["details"]["battery"] = {"percent": percent}
                if percent < 20:
                    if result["status"] == "ok":
                        result["status"] = "warning"
                    result["problems"].append(f"🟡 Батарея: {percent}%")
            except ValueError:
                pass
    else:
        result["details"]["battery"] = "нет (стационарный ПК)"

    return result


def _check_linux(result: dict) -> dict:
    """CPU, батарея на Linux."""
    result["details"]["cpu"] = {"cores": os.cpu_count()}

    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "model name" in line:
                    result["details"]["cpu"]["model"] = line.split(":")[1].strip()
                    break
    except Exception:
        pass

    for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
        try:
            with open(f"{zone}/type", "r") as f:
                zone_type = f.read().strip()
            with open(f"{zone}/temp", "r") as f:
                temp_c = int(f.read().strip()) / 1000

            if "cpu" in zone_type.lower() or "x86" in zone_type.lower():
                result["details"]["cpu_temp"] = round(temp_c, 1)
                if temp_c >= 90:
                    result["status"] = "critical"
                    result["problems"].append(f"🔴 Температура CPU: {temp_c:.1f}°C")
                elif temp_c >= 75:
                    if result["status"] == "ok":
                        result["status"] = "warning"
                    result["problems"].append(f"🟡 Температура CPU: {temp_c:.1f}°C")
                break
        except Exception:
            continue

    for bat in glob.glob("/sys/class/power_supply/BAT*"):
        try:
            with open(f"{bat}/capacity", "r") as f:
                percent = int(f.read().strip())
            result["details"]["battery"] = {"percent": percent}
            if percent < 20:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Батарея: {percent}%")
        except Exception:
            pass

    return result
