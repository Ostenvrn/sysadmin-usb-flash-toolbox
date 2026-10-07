"""
Главный запуск всех проверок здоровья ПК.
Собирает результаты из всех модулей checks/.
"""
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("health-check-runner")


def run_all_checks() -> list:
    """
    Запускает все проверки.
    Возвращает список результатов: [dict, dict, ...]
    """
    results = []

    # Список проверок: (имя, модуль, функция)
    checks = [
        ("hardware", "app.categories.system.health_check.checks.hardware", "check_hardware"),
        ("temperature", "app.categories.system.health_check.checks.temperature", "check_temperature"),
        ("memory", "app.categories.system.health_check.checks.memory", "check_memory"),
        ("disks", "app.categories.system.health_check.checks.disks", "check_disks"),
        ("network", "app.categories.system.health_check.checks.network", "check_network"),
        ("wifi", "app.categories.system.health_check.checks.wifi", "check_wifi"),
        ("services", "app.categories.system.health_check.checks.services", "check_services"),
        ("drivers", "app.categories.system.health_check.checks.drivers", "check_drivers"),
        ("usb", "app.categories.system.health_check.checks.usb", "check_usb"),
        ("events", "app.categories.system.health_check.checks.events", "check_events"),
        ("processes", "app.categories.system.health_check.checks.processes", "check_processes"),
        ("security", "app.categories.system.health_check.checks.security", "check_security"),
        ("power", "app.categories.system.health_check.checks.power", "check_power"),
    ]

    for name, module_path, func_name in checks:
        print(f"  🔍 Проверка: {name}...")
        try:
            module = __import__(module_path, fromlist=[func_name])
            func = getattr(module, func_name)
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
    """Подводит итог: сколько ok/warning/critical."""
    summary = {"ok": 0, "warning": 0, "critical": 0, "total": len(results)}
    for r in results:
        status = r.get("status", "ok")
        if status in summary:
            summary[status] += 1
    return summary
