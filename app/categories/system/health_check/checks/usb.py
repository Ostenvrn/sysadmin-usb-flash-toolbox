"""
Проверка USB-устройств.
- Linux: lsusb, /sys/bus/usb/devices
- Windows: WMI Win32_USBControllerDevice
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-usb")


def check_usb() -> dict:
    """Проверяет USB-устройства."""
    result = {
        "category": "USB-устройства",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    if os_detector.is_linux:
        result = _check_linux(result)
    elif os_detector.is_windows:
        result = _check_windows(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"🟡 ОС {os_detector.system} не поддерживается")

    return result


def _check_linux(result: dict) -> dict:
    """Проверка USB на Linux."""
    # 1. Список USB-устройств
    rc, stdout, _ = os_detector.run_command(["lsusb"])
    if rc != 0:
        result["details"]["note"] = "lsusb не установлен (sudo apt install usbutils)"
        return result

    devices = []
    for line in stdout.splitlines():
        if line.strip():
            # Формат: Bus 001 Device 002: ID 1234:5678 Manufacturer Product
            parts = line.split("ID ")
            if len(parts) >= 2:
                id_part = parts[1].split()[0]
                name = " ".join(parts[1].split()[1:])[:50]
                devices.append({"id": id_part, "name": name})

    result["details"]["total_devices"] = len(devices)
    result["details"]["devices"] = devices[:10]

    # 2. Ошибки USB в dmesg
    rc, stdout, _ = os_detector.run_command(
        ["dmesg", "--level=err", "--grep", "usb"]
    )
    if rc == 0 and stdout.strip():
        usb_errors = [line for line in stdout.splitlines() if line.strip()]
        result["details"]["dmesg_errors"] = len(usb_errors)

        if len(usb_errors) > 5:
            result["status"] = "warning"
            result["problems"].append(
                f"🟡 {len(usb_errors)} ошибок USB в dmesg"
            )
            result["recommendations"].append(
                "Проверьте USB-порты и кабели. Возможно, одно из устройств "
                "работает нестабильно. Попробуйте переподключить его в другой порт."
            )
            for line in usb_errors[:3]:
                result["problems"].append(f"   • {line[:100]}")

    return result


def _check_windows(result: dict) -> dict:
    """Проверка USB на Windows."""
    ps_cmd = (
        "Get-CimInstance Win32_USBControllerDevice | "
        "ForEach-Object { [Wmi]$_.Dependent } | "
        "Select-Object Name,DeviceID,Status | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip():
        return result

    import json
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]

        devices = []
        problem_devices = []

        for dev in data:
            name = dev.get("Name", "unknown")
            status = dev.get("Status", "OK")
            devices.append({"name": name, "status": status})

            if status and status.upper() != "OK":
                problem_devices.append({"name": name, "status": status})

        result["details"]["total_devices"] = len(devices)
        result["details"]["devices"] = devices[:10]

        if problem_devices:
            result["status"] = "warning"
            result["problems"].append(
                f"🟡 Проблемных USB-устройств: {len(problem_devices)}"
            )
            for dev in problem_devices[:5]:
                result["problems"].append(
                    f"   • {dev['name']}: {dev['status']}"
                )
            result["recommendations"].append(
                "Проверьте проблемные USB-устройства. Попробуйте переподключить "
                "их или обновить драйверы через Диспетчер устройств."
            )
    except Exception as e:
        logger.error(f"Ошибка парсинга USB (Windows): {e}")

    return result
