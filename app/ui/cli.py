"""
Консольное меню sysadmin-usb.
Красивое оформление: рамки, цвета, ASCII-арт.
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger
from app.ui.colors import (
    C, bold, dim, red, green, yellow, blue, cyan, magenta,
    bright_cyan, bright_green, bright_yellow, bright_red, bright_magenta,
    box_top, box_bottom, box_line, box_sep, simple_line,
)

logger = setup_logger("cli")


# =====================================================================
# Красивое главное меню
# =====================================================================

def show_main_menu(config: dict) -> str:
    """Показывает главное меню с рамкой."""
    print()
    print(box_top(68, C.BRIGHT_CYAN))
    print(box_line("", 68, C.BRIGHT_CYAN))
    print(box_line("ГЛАВНОЕ МЕНЮ", 68, C.BRIGHT_CYAN, align="center"))
    print(box_line("", 68, C.BRIGHT_CYAN))
    print(box_sep(68, C.BRIGHT_CYAN))

    categories = config.get("categories", {})
    enabled = {k: v for k, v in categories.items() if v.get("enabled")}

    # Нумерация с иконками
    for i, (key, cat) in enumerate(enabled.items(), start=1):
        name = cat['name']
        # Красим номер и название
        line = f"[{i}]  {name}"
        print(box_line(line, 68, C.CYAN))

    print(box_line("", 68, C.BRIGHT_CYAN))
    print(box_line("[0]  🚪 Выход", 68, C.RED))
    print(box_line("", 68, C.BRIGHT_CYAN))
    print(box_bottom(68, C.BRIGHT_CYAN))

    print()
    return input(f"  {bold(bright_cyan('Ваш выбор:'))} ").strip()


# =====================================================================
# Красивое меню категории
# =====================================================================

def show_category_menu(category_key: str, category: dict, config: dict) -> str:
    """Показывает меню категории с рамкой."""
    title = category['name']

    print()
    print(box_top(68, C.BRIGHT_MAGENTA))
    print(box_line("", 68, C.BRIGHT_MAGENTA))
    print(box_line(title, 68, C.BRIGHT_MAGENTA, align="center"))
    print(box_line("", 68, C.BRIGHT_MAGENTA))
    print(box_sep(68, C.BRIGHT_MAGENTA))

    functions = category.get("functions", [])
    for i, func in enumerate(functions, start=1):
        if func.get("enabled", True):
            name = func['name']
            line = f"[{i}]  {name}"
            print(box_line(line, 68, C.MAGENTA))

    print(box_line("", 68, C.BRIGHT_MAGENTA))
    print(box_line("[0]  ← Назад", 68, C.YELLOW))
    print(box_line("", 68, C.BRIGHT_MAGENTA))
    print(box_bottom(68, C.BRIGHT_MAGENTA))

    print()
    return input(f"  {bold(bright_magenta('Ваш выбор:'))} ").strip()


# =====================================================================
# Запуск
# =====================================================================

def run_cli(config: dict):
    """Запускает консольное меню."""
    logger.info("Запуск консольного меню")

    while True:
        categories = config.get("categories", {})
        enabled = {k: v for k, v in categories.items() if v.get("enabled")}
        keys = list(enabled.keys())

        choice = show_main_menu(config)

        if choice == "0":
            from app.ui.banner import print_footer
            print_footer()
            break

        if not choice.isdigit():
            print(f"\n  {bright_red('✗')} Неверный выбор. Введи число.\n")
            continue

        idx = int(choice) - 1
        if idx < 0 or idx >= len(keys):
            print(f"\n  {bright_red('✗')} Такой категории нет.\n")
            continue

        category_key = keys[idx]
        category = enabled[category_key]

        while True:
            func_choice = show_category_menu(category_key, category, config)

            if func_choice == "0":
                break

            if not func_choice.isdigit():
                print(f"\n  {bright_red('✗')} Неверный выбор. Введи число.\n")
                continue

            functions = [f for f in category.get("functions", []) if f.get("enabled", True)]
            fidx = int(func_choice) - 1

            if fidx < 0 or fidx >= len(functions):
                print(f"\n  {bright_red('✗')} Такой функции нет.\n")
                continue

            func = functions[fidx]
            run_function(category_key, func, config)


def run_function(category_key: str, func: dict, config: dict):
    """Запускает конкретную функцию."""
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
        elif func_id == "disk_image":
            from app.categories.backup import disk_image
            disk_image.run(); return
        elif func_id == "list":
            from app.categories.backup import list as backup_list
            backup_list.run(); return
        elif func_id == "verify":
            from app.categories.backup import verify
            verify.run(); return
        elif func_id == "restore":
            from app.categories.backup import restore
            restore.run(); return

    # --- Active Directory ---
    if category_key == "ad":
        if func_id == "users":
            from app.categories.ad import users
            users.run(); return
        elif func_id == "audit":
            from app.categories.ad import audit
            audit.run(); return
        elif func_id == "passwords":
            from app.categories.ad import passwords
            passwords.run(); return

    # --- Отчёты ---
    if category_key == "reports":
        if func_id == "generate":
            from app.categories.reports import generate
            generate.run(); return
        elif func_id == "export":
            from app.categories.reports import export
            export.run(); return
        elif func_id == "history":
            from app.categories.reports import history
            history.run(); return

    # --- Заглушка ---
    print()
    print(f"  {bright_yellow('⚠')}  Функция «{func['name']}» ещё не реализована.")
    print(f"     {dim('Будет добавлена на следующем этапе.')}")
    print()
