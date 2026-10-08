"""
Проверка USB-устройств.
Кроссплатформенно: Linux (lsusb) + Windows (WMI).
"""
import json
import glob

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-usb")


def check_usb() -> dict:
    result = {
        "category": "USB-устройства",
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
    """USB на Windows через PowerShell."""
    ps_cmd = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "Get-PnpDevice -Class USB -Status OK -ErrorAction SilentlyContinue | "
        "Where-Object {$_.FriendlyName -notlike '*Root Hub*' -and "
        "$_.FriendlyName -notlike '*Host Controller*'} | "
        "Select-Object FriendlyName,Status | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip():
        result["details"]["note"] = "USB-устройства не найдены"
        return result

    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]

        devices = []
        for dev in data:
            name = dev.get("FriendlyName", "unknown")
            if name and name != "unknown":
                devices.append({"name": name, "status": dev.get("Status", "OK")})

        result["details"]["total_devices"] = len(devices)
        result["details"]["devices"] = devices[:20]

        if not devices:
            result["details"]["note"] = "USB-устройства не найдены"
    except Exception as e:
        logger.error(f"Ошибка парсинга USB: {e}")
        result["details"]["note"] = f"Ошибка: {e}"

    return result


def _check_linux(result: dict) -> dict:
    """USB на Linux через lsusb."""
    rc, stdout, _ = os_detector.run_command(["lsusb"])
    if rc != 0:
        result["details"]["note"] = "lsusb не найден"
        return result

    devices = []
    for line in stdout.splitlines():
        if line.strip():
            parts = line.split("ID ")
            if len(parts) >= 2:
                id_part = parts[1].split()[0]
                name = " ".join(parts[1].split()[1:])[:80]
                devices.append({"id": id_part, "name": name})

    result["details"]["total_devices"] = len(devices)
    result["details"]["devices"] = devices[:20]

    rc, stdout, _ = os_detector.run_command(["dmesg", "--level=err", "--grep", "usb"])
    if rc == 0 and stdout.strip():
        usb_errors = [line for line in stdout.splitlines() if line.strip()]
        result["details"]["dmesg_errors"] = len(usb_errors)
        if len(usb_errors) > 5:
            result["status"] = "warning"
            result["problems"].append(f"🟡 {len(usb_errors)} ошибок USB в dmesg")

    return result
