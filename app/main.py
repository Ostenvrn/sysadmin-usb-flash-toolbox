"""
Главная точка входа sysadmin-usb.
Определяет ОС, загружает конфиг, запускает меню или веб-интерфейс.
"""
import sys
import getpass
from pathlib import Path

# Добавляем корень проекта в sys.path
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

    # 4. Показываем ASCII-баннер + приветствие
    from app.ui.banner import print_ascii_banner, print_welcome
    from app.ui.colors import dim, bright_cyan, bright_yellow, C

    print_ascii_banner()

    try:
        user = getpass.getuser()
    except Exception:
        user = ""

    print_welcome(
        hostname=info['hostname'],
        os_name=f"{info['system']} {info['release']}",
        user=user,
    )

    # 5. Выбор режима
    print(f"  {dim('Выберите режим работы:')}")
    print()
    print(f"    {bright_cyan('[1]')} 💻  Консольное меню")
    print(f"    {bright_cyan('[2]')} 🌐  Веб-интерфейс (в браузере)")
    print(f"    {bright_cyan('[3]')} 🔀  Оба (консоль + веб)")
    print(f"    {dim('[0]')} 🚪  Выход")
    print()

    choice = input(f"  {bright_yellow('Ваш выбор')} {dim('[1]')}: ").strip() or "1"

    if choice == "1":
        run_cli(config)
    elif choice == "2":
        run_web(config)
    elif choice == "3":
        import threading
        web_thread = threading.Thread(target=run_web, args=(config,), daemon=True)
        web_thread.start()
        run_cli(config)
    elif choice == "0":
        from app.ui.banner import print_footer
        print_footer()
        sys.exit(0)
    else:
        print(f"\n  {C.BRIGHT_RED}Неверный выбор.{C.RESET}\n")
        main()


if __name__ == "__main__":
    main()
