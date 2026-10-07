"""
Запуск функций из веба.
Перехватывает stdout и возвращает результат.
"""
import io
import sys
import threading
from datetime import datetime
from contextlib import redirect_stdout

from app.core.logger import setup_logger

logger = setup_logger("web-runner")


# =====================================================================
# Разрешённые функции (неинтерактивные)
# =====================================================================
ALLOWED_FUNCTIONS = {
    "system": ["health_check", "info"],
    "network": ["scan"],
    "backup": ["list"],
    "ad": ["users", "audit", "passwords"],
    "reports": ["generate", "history"],
    "printers": ["monitor", "local_scanner", "reports"],
}

# Результаты запусков (в памяти)
RESULTS = {}


def is_allowed(category: str, func_id: str) -> bool:
    """Проверяет, разрешена ли функция для запуска из веба."""
    return func_id in ALLOWED_FUNCTIONS.get(category, [])


def run_function(category: str, func_id: str) -> dict:
    """
    Запускает функцию и возвращает результат.
    Перехватывает stdout.
    """
    if not is_allowed(category, func_id):
        return {
            "ok": False,
            "error": f"Функция {category}.{func_id} не разрешена для запуска из веба",
        }

    logger.info(f"Запуск из веба: {category}.{func_id}")

    # Перехватываем stdout
    buffer = io.StringIO()

    try:
        with redirect_stdout(buffer):
            _dispatch(category, func_id)

        output = buffer.getvalue()

        return {
            "ok": True,
            "category": category,
            "func_id": func_id,
            "output": output,
            "time": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        return {
            "ok": False,
            "error": str(e),
            "output": buffer.getvalue(),
        }


def _dispatch(category: str, func_id: str):
    """Вызывает нужную функцию."""
    if category == "system":
        if func_id == "health_check":
            from app.categories.system import health_check
            health_check.run()
        elif func_id == "info":
            from app.categories.system import info
            info.run()

    elif category == "network":
        if func_id == "scan":
            from app.categories.network import scan
            # scan.run() интерактивный — вызываем внутренние функции
            _run_network_scan()

    elif category == "backup":
        if func_id == "list":
            from app.categories.backup import list as backup_list
            backup_list.run()

    elif category == "ad":
        if func_id == "users":
            from app.categories.ad import users
            _run_ad_users()
        elif func_id == "audit":
            from app.categories.ad import audit
            _run_ad_audit()
        elif func_id == "passwords":
            from app.categories.ad import passwords
            _run_ad_passwords()

    elif category == "reports":
        if func_id == "generate":
            from app.categories.reports import generate
            _run_reports_generate()
        elif func_id == "history":
            from app.categories.reports import history
            history.run()

    elif category == "printers":
        if func_id == "monitor":
            from app.categories.printers import monitor
            _run_printers_monitor()
        elif func_id == "local_scanner":
            from app.categories.printers import local_scanner
            _run_local_scanner()
        elif func_id == "reports":
            from app.categories.printers import reports
            reports.run()


# =====================================================================
# Обёртки для интерактивных функций
# =====================================================================

def _run_network_scan():
    """Запускает сканирование без интерактива."""
    from app.categories.network import scan

    local_ip = scan.get_local_ip()
    if not local_ip:
        print("Не удалось определить локальный IP")
        return

    subnet = scan.get_subnet(local_ip, prefix=24)
    print(f"Твой IP: {local_ip}")
    print(f"Подсеть: {subnet}")
    print()
    print("Сканирование...")
    print()

    devices = scan.scan_subnet(subnet, timeout=1, use_nmap=False)
    scan.print_report(devices, subnet)

    # Сохраняем
    import json
    from pathlib import Path
    output_dir = Path(__file__).parent.parent.parent.parent / "output" / "scans"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = output_dir / f"network_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({
            "subnet": subnet,
            "scanned_at": datetime.now().isoformat(),
            "mode": "ping",
            "devices": devices,
        }, f, indent=2, ensure_ascii=False)

    print(f"Результат сохранён: {filepath}")


def _run_ad_users():
    """Список пользователей AD."""
    from app.categories.ad import users
    from app.categories.ad.config import load_ad_config, is_ad_configured

    config = load_ad_config()
    if not is_ad_configured(config):
        print("AD не настроен. Проверь .env")
        return

    print(f"Домен: {config['domain']}")
    print()
    print("Запрос к AD...")
    user_list = users.list_users(config, limit=100)
    users.print_users(user_list)


def _run_ad_audit():
    """Аудит AD."""
    from app.categories.ad import audit
    from app.categories.ad.config import load_ad_config, is_ad_configured

    config = load_ad_config()
    if not is_ad_configured(config):
        print("AD не настроен. Проверь .env")
        return

    print(f"Домен: {config['domain']}")
    print()
    print("Аудит AD...")
    result = audit.audit_ad(config)
    audit.print_audit(result)


def _run_ad_passwords():
    """Аудит паролей."""
    from app.categories.ad import passwords
    from app.categories.ad.config import load_ad_config, is_ad_configured

    config = load_ad_config()
    if not is_ad_configured(config):
        print("AD не настроен. Проверь .env")
        return

    print(f"Домен: {config['domain']}")
    print()
    print("Аудит паролей...")
    result = passwords.audit_passwords(config)
    passwords.print_audit(result)


def _run_reports_generate():
    """Генерация отчёта."""
    from app.categories.reports import generate

    print("Сбор данных...")
    print()

    data = {}
    print("🖥️  Система...")
    data["system"] = generate.collect_system_info()
    print(f"   ✅ {data['system']['hostname']}")

    print("🏥 Health Check...")
    data["health_check"] = generate.collect_health_check()
    summary = data["health_check"].get("summary", {})
    print(f"   ✅ Проверок: {summary.get('total', 0)}")

    print("🖨️  Принтеры...")
    data["printers"] = generate.collect_printers()
    print(f"   ✅ Найдено: {data['printers']['count']}")

    print("💾 Бэкапы...")
    data["backups"] = generate.collect_backups()
    print(f"   ✅ Найдено: {data['backups']['count']}")

    print("🌐 Сеть...")
    data["network"] = generate.collect_network_scan()
    print(f"   ✅ Устройств: {data['network']['count']}")

    print()
    markdown = generate.generate_markdown(data)

    import json
    from pathlib import Path
    reports_dir = Path(__file__).parent.parent.parent.parent / "output" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    md_path = reports_dir / f"report_{timestamp}.md"
    json_path = reports_dir / f"report_{timestamp}.json"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    print("✅ Отчёт готов")
    print(f"📄 Markdown: {md_path}")
    print(f"📄 JSON: {json_path}")


def _run_printers_monitor():
    """Мониторинг принтеров."""
    from app.categories.printers import monitor

    print("Загрузка принтеров...")
    printers = monitor.load_printers()

    if not printers:
        print("Список принтеров пуст.")
        return

    print(f"Найдено: {len(printers)}")
    print()

    results = monitor.monitor_all()
    monitor.print_report(results)

    report_file = monitor.save_report(results)
    print(f"📄 Отчёт: {report_file}")


def _run_local_scanner():
    """Сканер локальных принтеров."""
    from app.categories.printers import local_scanner

    print("Сканирование локальных принтеров...")
    printers = local_scanner.scan_local_printers()
    local_scanner.print_report(printers)
