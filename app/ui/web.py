"""
Веб-интерфейс sysadmin-usb (Flask).
"""
from app.os_detect import os_detector


def run_web(config: dict):
    """Запускает веб-сервер."""
    print()
    print("=" * 60)
    print("  ВЕБ-ИНТЕРФЕЙС")
    print("=" * 60)
    print()
    print(f"  Открой в браузере: http://{config['web']['host']}:{config['web']['port']}")
    print()
    print("(Заглушка — Flask будет добавлен на следующем этапе)")
