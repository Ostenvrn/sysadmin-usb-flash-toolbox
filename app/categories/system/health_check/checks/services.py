"""
Проверка служб.
Ищет: остановленные критичные службы.
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-services")


# Критичные службы по ОС
# Для Linux-ноутбуков ssh не критичен — убираем
CRITICAL_SERVICES = {
    "Windows": [
        "Spooler",
        "Dhcp",
        "Dnscache",
        "LanmanWorkstation",
        "Themes",
        "AudioSrv",
        "WinDefend",
    ],
    "Linux": [
        "cups",
        "NetworkManager",
        "systemd-resolved",
    ],
}


def check_services() -> dict:
    """Проверяет критичные службы."""
    result = {
        "category": "Службы",
        "status": "ok",
        "problems": [],
        "details": {"stopped": [], "running": []},
    }

    services = CRITICAL_SERVICES.get(os_detector.system, [])
    if not services:
        result["status"] = "warning"
        result["problems"].append(f"🟡 ОС {os_detector.system} не поддерживается")
        return result

    for svc in services:
        if _is_running(svc):
            result["details"]["running"].append(svc)
        else:
            result["details"]["stopped"].append(svc)
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(f"🟡 Служба {svc} остановлена")

    return result


def _is_running(service: str) -> bool:
    """Проверяет, запущена ли служба."""
    if os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(
            ["sc", "query", service]
        )
        return rc == 0 and "RUNNING" in stdout.upper()
    else:
        rc, stdout, _ = os_detector.run_command(
            ["systemctl", "is-active", service]
        )
        return rc == 0 and "active" in stdout.lower()
