"""
Главный запуск всех проверок здоровья ПК.
Собирает результаты из всех модулей checks/.

ВАЖНО: используется СТАТИЧЕСКИЙ импорт, чтобы PyInstaller
включил все модули в .exe.
"""
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

# === СТАТИЧЕСКИЕ ИМПОРТЫ (для PyInstaller) ===
from app.categories.system.health_check.checks import (
    hardware,
    temperature,
    memory,
    disks,
    network,
    wifi,
    services,
    drivers,
    usb,
    events,
    processes,
    security,
    power,
)

logger = setup_logger("health-check-runner")


# Список проверок (функция, имя)
CHECKS = [
    ("hardware", hardware.check_hardware),
    ("temperature", temperature.check_temperature),
    ("memory", memory.check_memory),
    ("disks", disks.check_disks),
    ("network", network.check_network),
    ("wifi", wifi.check_wifi),
    ("services", services.check_services),
    ("drivers", drivers.check_drivers),
    ("usb", usb.check_usb),
    ("events", events.check_events),
    ("processes", processes.check_processes),
    ("security", security.check_security),
    ("power", power.check_power),
]


def run_all_checks() -> list:
    """Запускает все проверки."""
    results = []

    for name, func in CHECKS:
        print(f"  🔍 Проверка: {name}...")
        try:
            result = func()
            results.append(result)
            icon = {"ok": "🟢", "warning": "🟡", "critical": "🔴"}.get(result["status"], "⚪")
            print(f"     {icon} {result['category']}: {result['status']}")
        except Exception as e:
            logger.error(f"Ошибка в проверке {name}: {e}")
            results.append({
                "category": name,
                "status": "warning",
                "problems": [f"Ошибка выполнения: {e}"],
                "recommendations": [],
                "details": {},
            })
            print(f"     ⚠️  {name}: ошибка — {e}")

    return results


def summarize(results: list) -> dict:
    """Подводит итог."""
    summary = {"ok": 0, "warning": 0, "critical": 0, "total": len(results)}
    for r in results:
        status = r.get("status", "ok")
        if status in summary:
            summary[status] += 1
    return summary
