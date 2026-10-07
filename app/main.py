"""
Главная точка входа sysadmin-usb.
Определяет ОС, загружает конфиг, запускает меню или веб-интерфейс.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы работали импорты
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "libs"))

from app.os_detect import os_detector
from app.core.config import load_config
from app.core.logger import setup_logger
from app.ui.cli import run_cli
from app.ui.web import run_web


def main():
    """Точка входа."""
    # 1. Определяем ОС
    info = os_detector.get_system_info()

    # 2. Настраиваем логирование
    logger = setup_logger()
    logger.info(f"Запуск sysadmin-usb на {info['system']} {info['release']}")
    logger.info(f"Hostname: {info['hostname']}")

    # 3. Загружаем конфиг
    config = load_config()

    # 4. Показываем приветствие
    print("=" * 60)
    print(f"  SYSADMIN-USB v{config['app']['version']}")
    print(f"  ОС: {info['system']} {info['release']} ({info['architecture']})")
    print(f"  Hostname: {info['hostname']}")
    print("=" * 60)
    print()

    # 5. Спрашиваем, какой интерфейс использовать
    print("Выберите режим работы:")
    print("  [1] Консольное меню")
    print("  [2] Веб-интерфейс (откроется в браузере)")
    print("  [3] Оба (консоль + веб)")
    print("  [0] Выход")
    print()

    choice = input("Ваш выбор: ").strip()

    if choice == "1":
        run_cli(config)
    elif choice == "2":
        run_web(config)
    elif choice == "3":
        # Запускаем веб в фоне, консоль — в foreground
        import threading
        web_thread = threading.Thread(target=run_web, args=(config,), daemon=True)
        web_thread.start()
        run_cli(config)
    elif choice == "0":
        print("До свидания!")
        sys.exit(0)
    else:
        print("Неверный выбор. Попробуйте снова.")
        main()


if __name__ == "__main__":
    main()
