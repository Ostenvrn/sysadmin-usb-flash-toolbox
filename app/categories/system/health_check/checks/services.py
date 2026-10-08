"""
Проверка критичных служб.
Кроссплатформенно: Linux (systemctl) + Windows (sc query).
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-services")


CRITICAL_SERVICES_WINDOWS = [
    "Spooler",           # Печать
    "Dhcp",              # DHCP-клиент
    "Dnscache",          # DNS-клиент
    "LanmanWorkstation", # Сеть
    "AudioSrv",          # Звук
    "WinDefend",         # Защитник Windows
    "wuauserv",          # Windows Update
]

CRITICAL_SERVICES_LINUX = [
    "cups",
    "NetworkManager",
    "systemd-resolved",
]


def check_services() -> dict:
    result = {
        "category": "Службы",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {"stopped": [], "running": []},
    }

    if os_detector.is_windows:
        services = CRITICAL_SERVICES_WINDOWS
    elif os_detector.is_linux:
        services = CRITICAL_SERVICES_LINUX
    else:
        result["status"] = "warning"
        result["problems"].append(f"ОС {os_detector.system} не поддерживается")
        return result

    for svc in services:
        is_running = _is_running(svc)
        if is_running:
            result["details"]["running"].append(svc)
        else:
            result["details"]["stopped"].append(svc)
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(f"🟡 Служба {svc} остановлена")

    if result["details"]["stopped"]:
        result["recommendations"].append(
            "Запустите остановленные службы. Windows: services.msc. "
            "Linux: systemctl start <service>."
        )

    return result


def _is_running(service: str) -> bool:
    if os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(["sc", "query", service])
        if rc == 0:
            return "RUNNING" in stdout.upper()
        return False
    else:
        rc, stdout, _ = os_detector.run_command(["systemctl", "is-active", service])
        if rc == 0:
            return "active" in stdout.lower()
        return False
