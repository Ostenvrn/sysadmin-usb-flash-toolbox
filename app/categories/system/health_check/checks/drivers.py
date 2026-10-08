"""
Проверка драйверов.
Кроссплатформенно: Linux (dmesg) + Windows (WMI PnPEntity).
"""
import json

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-drivers")


def check_drivers() -> dict:
    result = {
        "category": "Драйверы",
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
    """Проверка драйверов на Windows через WMI."""
    ps_cmd = (
        "Get-CimInstance Win32_PnPEntity | "
        "Where-Object {$_.ConfigManagerErrorCode -ne 0} | "
        "Select-Object Name,ConfigManagerErrorCode,DeviceID | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    problems = []
    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]
            for dev in data:
                problems.append({
                    "name": dev.get("Name", "unknown"),
                    "code": dev.get("ConfigManagerErrorCode", 0),
                })
        except Exception as e:
            logger.error(f"Ошибка парсинга драйверов: {e}")

    result["details"]["problem_devices"] = problems
    result["details"]["problem_count"] = len(problems)

    if problems:
        result["status"] = "warning"
        for dev in problems[:10]:
            result["problems"].append(
                f"🟡 Проблемное устройство: {dev['name']} (код {dev['code']})"
            )
        if len(problems) > 10:
            result["problems"].append(f"🟡 ... и ещё {len(problems) - 10}")
        result["recommendations"].append(
            "Откройте Диспетчер устройств (devmgmt.msc). "
            "Обновите драйверы у проблемных устройств (жёлтый треугольник)."
        )

    return result


def _check_linux(result: dict) -> dict:
    """Проверка драйверов на Linux через dmesg."""
    rc, stdout, _ = os_detector.run_command(["dmesg", "--level=err,warn"])
    if rc != 0:
        result["details"]["note"] = "dmesg недоступен (нужен root?)"
        return result

    errors = [line for line in stdout.splitlines() if line.strip()]
    result["details"]["dmesg_errors"] = len(errors)

    if len(errors) > 10:
        result["status"] = "warning"
        result["problems"].append(
            f"🟡 В dmesg {len(errors)} ошибок/предупреждений"
        )
        for line in errors[:3]:
            result["problems"].append(f"   • {line[:120]}")
        result["recommendations"].append(
            "Проверьте dmesg на наличие ошибок драйверов."
        )

    rc, stdout, _ = os_detector.run_command(["lsmod"])
    if rc == 0:
        modules = [line.split()[0] for line in stdout.splitlines()[1:] if line.strip()]
        result["details"]["loaded_modules"] = len(modules)

    return result
