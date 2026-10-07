"""
Автопочинка принтеров.
Перезапуск службы печати, очистка очереди, перезапуск принтера.
Работает на Windows и Linux.
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("printer-auto-fix")


def restart_spooler() -> bool:
    """
    Перезапускает службу печати.
    Windows: Spooler
    Linux: cups
    """
    service = "Spooler" if os_detector.is_windows else "cups"

    print(f"  🔄 Перезапуск службы печати ({service})...")

    if os_detector.is_windows:
        # Windows: net stop / net start
        rc1, _, err1 = os_detector.run_command(["net", "stop", service])
        rc2, _, err2 = os_detector.run_command(["net", "start", service])
        if rc1 == 0 and rc2 == 0:
            print(f"  ✅ Служба {service} перезапущена")
            logger.info(f"Служба {service} перезапущена")
            return True
        else:
            print(f"  ❌ Ошибка: {err1 or err2}")
            logger.error(f"Ошибка перезапуска {service}: {err1 or err2}")
            return False
    else:
        # Linux: systemctl restart cups
        rc, _, err = os_detector.run_command(["sudo", "systemctl", "restart", service])
        if rc == 0:
            print(f"  ✅ Служба {service} перезапущена")
            logger.info(f"Служба {service} перезапущена")
            return True
        else:
            print(f"  ❌ Ошибка: {err}")
            print("     Возможно, нужен sudo. Попробуй: sudo systemctl restart cups")
            logger.error(f"Ошибка перезапуска {service}: {err}")
            return False


def clear_print_queue() -> bool:
    """
    Очищает очередь печати.
    Windows: удаляет файлы из C:\\Windows\\System32\\spool\\PRINTERS
    Linux: cancel -a
    """
    print("  🗑️  Очистка очереди печати...")

    if os_detector.is_windows:
        # Windows: удаляем файлы из спулера
        spool_dir = "C:\\Windows\\System32\\spool\\PRINTERS"
        rc, _, err = os_detector.run_command(
            ["del", "/Q", f"{spool_dir}\\*.*"]
        )
        if rc == 0:
            print("  ✅ Очередь очищена")
            logger.info("Очередь печати очищена (Windows)")
            return True
        else:
            print(f"  ⚠️  Ошибка: {err}")
            logger.warning(f"Ошибка очистки очереди: {err}")
            return False
    else:
        # Linux: cancel -a
        rc, _, err = os_detector.run_command(["cancel", "-a"])
        if rc == 0:
            print("  ✅ Очередь очищена")
            logger.info("Очередь печати очищена (Linux)")
            return True
        else:
            print(f"  ⚠️  Ошибка: {err}")
            print("     Возможно, CUPS не установлен или очередь пуста")
            logger.warning(f"Ошибка очистки очереди: {err}")
            return False


def check_printer_status(ip: str) -> str:
    """
    Проверяет доступность принтера по IP (ping).
    Возвращает 'online' или 'offline'.
    """
    print(f"  📡 Проверка доступности {ip}...")

    if os_detector.is_windows:
        cmd = ["ping", "-n", "1", "-w", "1000", ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]

    rc, _, _ = os_detector.run_command(cmd)
    status = "online" if rc == 0 else "offline"

    icon = "🟢" if status == "online" else "🔴"
    print(f"  {icon} {ip}: {status}")
    return status


def run():
    """Точка входа для автопочинки."""
    print()
    print("=" * 60)
    print("  АВТОПОЧИНКА ПРИНТЕРОВ")
    print("=" * 60)
    print()
    print(f"  ОС: {os_detector.system}")
    print()

    # Меню
    print("  Выберите действие:")
    print("    [1] Перезапустить службу печати")
    print("    [2] Очистить очередь печати")
    print("    [3] Проверить доступность принтера по IP")
    print("    [4] Всё сразу (служба + очередь)")
    print("    [0] ← Назад")
    print()

    choice = input("  Ваш выбор: ").strip()

    if choice == "1":
        restart_spooler()
    elif choice == "2":
        clear_print_queue()
    elif choice == "3":
        ip = input("  Введи IP принтера: ").strip()
        if ip:
            check_printer_status(ip)
        else:
            print("  ❌ IP не введён")
    elif choice == "4":
        print()
        print("  🚀 Запуск полной автопочинки...")
        print()
        restart_spooler()
        print()
        clear_print_queue()
        print()
        print("  ✅ Автопочинка завершена")
    elif choice == "0":
        return
    else:
        print("  ❌ Неверный выбор")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
