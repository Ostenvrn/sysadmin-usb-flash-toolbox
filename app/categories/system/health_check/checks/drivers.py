"""
Проверка драйверов.
- Windows: проблемные устройства через WMI
- Linux: модули ядра, dmesg на ошибки
"""
import os
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-drivers")


def check_drivers() -> dict:
    """Проверяет драйверы."""
    result = {
        "category": "Драйверы",
        "status": "ok",
        "problems": [],
        "details": {},
    }

    if os_detector.is_windows:
        result = _check_windows(result)
    elif os_detector.is_linux:
        result = _check_linux(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"🟡 ОС {os_detector.system} не поддерживается")

    return result


def _check_windows(result: dict) -> dict:
    """Проверка драйверов на Windows."""
    # Проблемные устройства (жёлтый восклицательный знак)
    ps_cmd = (
        "Get-CimInstance Win32_PnPEntity | "
        "Where-Object {$_.ConfigManagerErrorCode -ne 0} | "
        "Select-Object Name,ConfigManagerErrorCode | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    problems = []
    if rc == 0 and stdout.strip():
        import json
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]
            for dev in data:
                problems.append(dev.get("Name", "unknown"))
        except Exception:
            pass

    result["details"]["problem_devices"] = problems

    if problems:
        result["status"] = "warning"
        for dev in problems[:5]:
            result["problems"].append(f"🟡 Проблемное устройство: {dev}")
        if len(problems) > 5:
            result["problems"].append(f"🟡 ... и ещё {len(problems) - 5}")

    return result


def _check_linux(result: dict) -> dict:
    """Проверка драйверов на Linux."""
    # 1. Ошибки в dmesg (за последний запуск)
    rc, stdout, _ = os_detector.run_command(["dmesg", "--level=err,warn"])
    if rc == 0 and stdout.strip():
        errors = [line for line in stdout.splitlines() if line.strip()]
        result["details"]["dmesg_errors"] = len(errors)

        if len(errors) > 10:
            result["status"] = "warning"
            result["problems"].append(
                f"🟡 В dmesg {len(errors)} ошибок/предупреждений за последний запуск"
            )
            # Показываем первые 3
            for line in errors[:3]:
                short = line[:120]
                result["problems"].append(f"   • {short}")
        else:
            result["details"]["dmesg_errors"] = len(errors)

    # 2. Загруженные модули
    rc, stdout, _ = os_detector.run_command(["lsmod"])
    if rc == 0:
        modules = [line.split()[0] for line in stdout.splitlines()[1:] if line.strip()]
        result["details"]["loaded_modules"] = len(modules)

    return result
