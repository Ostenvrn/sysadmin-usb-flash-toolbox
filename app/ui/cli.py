"""
Консольное меню sysadmin-usb.
"""
from app.os_detect import os_detector


def run_cli(config: dict):
    """Запускает консольное меню."""
    print()
    print("=" * 60)
    print("  КОНСОЛЬНОЕ МЕНЮ")
    print("=" * 60)
    print()
    print("Категории:")
    for key, cat in config.get("categories", {}).items():
        if cat.get("enabled"):
            print(f"  [{key}] {cat['name']}")
    print("  [0] Выход")
    print()
    print("(Заглушка — функции будут добавлены на следующем этапе)")
