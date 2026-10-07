"""
Мониторинг принтеров по SNMP.
Собирает: модель, статус, уровень тонера, количество страниц.
"""
import json
import yaml
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("printer-monitor")

# Путь к конфигу принтеров
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
PRINTERS_CONFIG = PROJECT_ROOT / "config" / "printers.yaml"
OUTPUT_DIR = PROJECT_ROOT / "output" / "scans"


# =====================================================================
# SNMP OID (стандартные идентификаторы для принтеров)
# =====================================================================
# Это "адреса" параметров в SNMP-дереве принтера.
# Они одинаковы для большинства принтеров (стандарт Printer MIB).
# =====================================================================
OIDS = {
    "model": "1.3.6.1.2.1.25.3.2.1.3.1",           # Модель принтера
    "status": "1.3.6.1.2.1.25.3.2.1.5.1",          # Статус
    "pages_total": "1.3.6.1.2.1.43.10.2.1.4.1.1",  # Всего страниц
    "toner_level": "1.3.6.1.2.1.43.11.1.1.9.1.1",  # Уровень тонера (%)
    "toner_max": "1.3.6.1.2.1.43.11.1.1.8.1.1",    # Максимум тонера
}

# Расшифровка статусов принтера (стандарт Printer MIB)
STATUS_MAP = {
    1: "Другое",
    2: "Неизвестно",
    3: "Простой",
    4: "Печать",
    5: "Прогрев",
}


def load_printers() -> list:
    """Загружает список принтеров из config/printers.yaml."""
    if not PRINTERS_CONFIG.exists():
        logger.error(f"Конфиг не найден: {PRINTERS_CONFIG}")
        return []

    with open(PRINTERS_CONFIG, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    printers = data.get("printers", [])
    # Фильтруем только включённые
    enabled = [p for p in printers if p.get("enabled", True)]
    logger.info(f"Загружено принтеров: {len(enabled)}")
    return enabled


def query_printer(printer: dict) -> dict:
    """
    Опрашивает один принтер по SNMP.
    Возвращает словарь с данными или с ошибкой.
    """
    result = {
        "name": printer.get("name", "unknown"),
        "ip": printer.get("ip", "unknown"),
        "model": printer.get("model", "unknown"),
        "location": printer.get("location", "unknown"),
        "status": "offline",
        "toner_level": None,
        "toner_percent": None,
        "pages_total": None,
        "error": None,
        "checked_at": datetime.now().isoformat(),
    }

    # Проверяем, установлен ли pysnmp
    try:
        from pysnmp.hlapi import (
            getCmd,
            SnmpEngine,
            CommunityData,
            UdpTransportTarget,
            ContextData,
            ObjectType,
            ObjectIdentity,
        )
    except ImportError:
        result["error"] = "pysnmp не установлен. Выполни: pip install --target=libs/ pysnmp"
        logger.error(result["error"])
        return result

    ip = printer["ip"]
    community = printer.get("snmp_community", "public")

    try:
        # Запрашиваем все OID одним запросом
        error_indication, error_status, error_index, var_binds = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),  # mpModel=1 = SNMPv2c
                UdpTransportTarget((ip, 161), timeout=2, retries=1),
                ContextData(),
                *[ObjectType(ObjectIdentity(oid)) for oid in OIDS.values()],
            )
        )

        if error_indication:
            result["error"] = f"SNMP ошибка: {error_indication}"
            logger.warning(f"{result['name']} ({ip}): {result['error']}")
            return result

        if error_status:
            result["error"] = f"SNMP статус: {error_status.prettyPrint()}"
            logger.warning(f"{result['name']} ({ip}): {result['error']}")
            return result

        # Разбираем ответ
        oid_keys = list(OIDS.keys())
        for i, var_bind in enumerate(var_binds):
            key = oid_keys[i]
            value = var_bind[1].prettyPrint()

            if key == "model":
                result["model"] = value
            elif key == "status":
                try:
                    result["status"] = STATUS_MAP.get(int(value), "Неизвестно")
                except (ValueError, TypeError):
                    result["status"] = str(value)
            elif key == "pages_total":
                result["pages_total"] = int(value) if value.isdigit() else value
            elif key == "toner_level":
                result["toner_level"] = int(value) if value.isdigit() else value
            elif key == "toner_max":
                result["toner_max"] = int(value) if value.isdigit() else value

        # Считаем процент тонера
        if result["toner_level"] is not None and result.get("toner_max"):
            if result["toner_max"] > 0:
                result["toner_percent"] = round(
                    (result["toner_level"] / result["toner_max"]) * 100, 1
                )

        logger.info(f"{result['name']} ({ip}): {result['status']}, тонер: {result['toner_percent']}%")

    except Exception as e:
        result["error"] = f"Исключение: {e}"
        logger.error(f"{result['name']} ({ip}): {result['error']}")

    return result


def monitor_all(printers: list = None) -> list:
    """Опрашивает все принтеры. Возвращает список результатов."""
    if printers is None:
        printers = load_printers()

    results = []
    for printer in printers:
        results.append(query_printer(printer))

    return results


def save_report(results: list) -> Path:
    """Сохраняет отчёт в JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = OUTPUT_DIR / f"printers_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"Отчёт сохранён: {filename}")
    return filename


def print_report(results: list):
    """Выводит отчёт в консоль (красиво)."""
    print()
    print("=" * 80)
    print("  МОНИТОРИНГ ПРИНТЕРОВ")
    print("=" * 80)
    print()

    for r in results:
        status_icon = "🟢" if r["status"] in ("Простой", "Печать") else "🔴"
        print(f"  {status_icon} {r['name']} ({r['ip']})")
        print(f"     Модель:  {r['model']}")
        print(f"     Статус:  {r['status']}")

        if r.get("toner_percent") is not None:
            toner = r["toner_percent"]
            if toner < 10:
                toner_icon = "🔴"
            elif toner < 30:
                toner_icon = "🟡"
            else:
                toner_icon = "🟢"
            print(f"     Тонер:   {toner_icon} {toner}%")

        if r.get("pages_total"):
            print(f"     Страниц: {r['pages_total']}")

        if r.get("error"):
            print(f"     Ошибка:  {r['error']}")

        print()

    # Итог
    total = len(results)
    online = sum(1 for r in results if r["status"] not in ("offline", "Неизвестно"))
    with_error = sum(1 for r in results if r["error"])
    low_toner = sum(
        1 for r in results
        if r.get("toner_percent") is not None and r["toner_percent"] < 10
    )

    print("-" * 80)
    print(f"  Всего: {total} | Онлайн: {online} | Ошибок: {with_error} | Тонер < 10%: {low_toner}")
    print("=" * 80)


def run():
    """Точка входа для этой функции (вызывается из меню)."""
    print()
    print("Загрузка списка принтеров...")
    printers = load_printers()

    if not printers:
        print("Список принтеров пуст. Проверь config/printers.yaml")
        return

    print(f"Найдено принтеров: {len(printers)}")
    print("Опрос по SNMP...")
    print()

    results = monitor_all(printers)
    print_report(results)

    # Сохраняем отчёт
    report_file = save_report(results)
    print()
    print(f"📄 Отчёт сохранён: {report_file}")


if __name__ == "__main__":
    # Для отладки: запуск напрямую
    run()
