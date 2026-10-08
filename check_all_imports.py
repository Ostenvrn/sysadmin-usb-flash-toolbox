"""
Проверка всех импортов в проекте.
Запускать через Wine с портативным Python.
"""
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "libs")

MODULES = [
    # Принтеры
    "app.categories.printers.monitor",
    "app.categories.printers.auto_fix",
    "app.categories.printers.scanner",
    "app.categories.printers.local_scanner",
    "app.categories.printers.reports",
    # Сеть
    "app.categories.network.diagnostics",
    "app.categories.network.scan",
    "app.categories.network.ports",
    "app.categories.network.map",
    # Система
    "app.categories.system.health_check",
    "app.categories.system.health_check.runner",
    "app.categories.system.health_check.report",
    "app.categories.system.health_check.checks.hardware",
    "app.categories.system.health_check.checks.temperature",
    "app.categories.system.health_check.checks.memory",
    "app.categories.system.health_check.checks.disks",
    "app.categories.system.health_check.checks.network",
    "app.categories.system.health_check.checks.wifi",
    "app.categories.system.health_check.checks.services",
    "app.categories.system.health_check.checks.drivers",
    "app.categories.system.health_check.checks.usb",
    "app.categories.system.health_check.checks.events",
    "app.categories.system.health_check.checks.processes",
    "app.categories.system.health_check.checks.security",
    "app.categories.system.health_check.checks.power",
    "app.categories.system.info",
    "app.categories.system.cleanup",
    "app.categories.system.update",
    # Бэкапы
    "app.categories.backup.create",
    "app.categories.backup.disk_image",
    "app.categories.backup.list",
    "app.categories.backup.verify",
    "app.categories.backup.restore",
    # AD
    "app.categories.ad.config",
    "app.categories.ad.users",
    "app.categories.ad.audit",
    "app.categories.ad.passwords",
    # Отчёты
    "app.categories.reports.generate",
    "app.categories.reports.export",
    "app.categories.reports.history",
]

ok = 0
errors = []

for mod in MODULES:
    try:
        __import__(mod)
        print(f"✅ {mod}")
        ok += 1
    except Exception as e:
        print(f"❌ {mod}: {e}")
        errors.append((mod, str(e)))

print()
print(f"ИТОГО: {ok}/{len(MODULES)} OK")
if errors:
    print()
    print("ОШИБКИ:")
    for mod, err in errors:
        print(f"  ❌ {mod}: {err}")
