"""
Консольное меню sysadmin-usb.
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("cli")


def show_main_menu(config: dict) -> str:
    print()
    print("=" * 60)
    print("  ГЛАВНОЕ МЕНЮ")
    print("=" * 60)
    print()

    categories = config.get("categories", {})
    enabled = {k: v for k, v in categories.items() if v.get("enabled")}

    for i, (key, cat) in enumerate(enabled.items(), start=1):
        print(f"  [{i}] {cat['name']}")

    print("  [0] Выход")
    print()

    return input("Ваш выбор: ").strip()


def show_category_menu(category_key: str, category: dict, config: dict) -> str:
    print()
    print("=" * 60)
    print(f"  {category['name']}")
    print("=" * 60)
    print()

    functions = category.get("functions", [])
    for i, func in enumerate(functions, start=1):
        if func.get("enabled", True):
            print(f"  [{i}] {func['name']}")

    print("  [0] ← Назад")
    print()

    return input("Ваш выбор: ").strip()


def run_cli(config: dict):
    logger.info("Запуск консольного меню")

    while True:
        categories = config.get("categories", {})
        enabled = {k: v for k, v in categories.items() if v.get("enabled")}
        keys = list(enabled.keys())

        choice = show_main_menu(config)

        if choice == "0":
            print("До свидания!")
            break

        if not choice.isdigit():
            print("Неверный выбор. Введи число.")
            continue

        idx = int(choice) - 1
        if idx < 0 or idx >= len(keys):
            print("Неверный выбор. Такой категории нет.")
            continue

        category_key = keys[idx]
        category = enabled[category_key]

        while True:
            func_choice = show_category_menu(category_key, category, config)

            if func_choice == "0":
                break

            if not func_choice.isdigit():
                print("Неверный выбор. Введи число.")
                continue

            functions = [f for f in category.get("functions", []) if f.get("enabled", True)]
            fidx = int(func_choice) - 1

            if fidx < 0 or fidx >= len(functions):
                print("Неверный выбор. Такой функции нет.")
                continue

            func = functions[fidx]
            run_function(category_key, func, config)


def run_function(category_key: str, func: dict, config: dict):
    func_id = func.get("id", "")
    logger.info(f"Запуск функции: {category_key}.{func_id}")

    # --- Принтеры ---
    if category_key == "printers":
        if func_id == "monitor":
            from app.categories.printers import monitor
            monitor.run(); return
        elif func_id == "auto_fix":
            from app.categories.printers import auto_fix
            auto_fix.run(); return
        elif func_id == "scanner":
            from app.categories.printers import scanner
            scanner.run(); return
        elif func_id == "local_scanner":
            from app.categories.printers import local_scanner
            local_scanner.run(); return
        elif func_id == "reports":
            from app.categories.printers import reports
            reports.run(); return

    # --- Система ---
    if category_key == "system":
        if func_id == "health_check":
            from app.categories.system import health_check
            health_check.run(); return
        elif func_id == "info":
            from app.categories.system import info
            info.run(); return
        elif func_id == "cleanup":
            from app.categories.system import cleanup
            cleanup.run(); return
        elif func_id == "update":
            from app.categories.system import update
            update.run(); return

    # --- Сеть ---
    if category_key == "network":
        if func_id == "diagnostics":
            from app.categories.network import diagnostics
            diagnostics.run(); return
        elif func_id == "scan":
            from app.categories.network import scan
            scan.run(); return
        elif func_id == "ports":
            from app.categories.network import ports
            ports.run(); return
        elif func_id == "map":
            from app.categories.network import map as net_map
            net_map.run(); return

    # --- Бэкапы ---
    if category_key == "backup":
        if func_id == "create":
            from app.categories.backup import create
            create.run(); return
        # verify, restore, list — заглушки

    # --- Заглушка ---
    print()
    print(f"⚠️  Функция «{func['name']}» ещё не реализована.")
    print("   Будет добавлена на следующем этапе.")
    print()
