"""
Мониторинг принтеров по SNMP.
Собирает: модель, статус, уровень тонера, количество страниц.
Читает оба конфига: config/printers.yaml (ручной) и config/printers_auto.yaml (авто).
"""
import json
import yaml
from pathlib import Path
from datetime import datetime

from app.core.logger import setup_logger

logger = setup_logger("printer-monitor")

# Пути
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
PRINTERS_CONFIG = PROJECT_ROOT / "config" / "printers.yaml"
PRINTERS_AUTO_CONFIG = PROJECT_ROOT / "config" / "printers_auto.yaml"
OUTPUT_DIR = PROJECT_ROOT / "output" / "scans"


# =====================================================================
# SNMP OID (стандартные идентификаторы для принтеров)
# =====================================================================
OIDS = {
    "model": "1.3.6.1.2.1.25.3.2.1.3.1",
    "status": "1.3.6.1.2.1.25.3.2.1.5.1",
    "pages_total": "1.3.6.1.2.1.43.10.2.1.4.1.1",
    "toner_level": "1.3.6.1.2.1.43.11.1.1.9.1.1",
    "toner_max": "1.3.6.1.2.1.43.11.1.1.8.1.1",
}

STATUS_MAP = {
    1: "Другое",
    2: "Неизвестно",
    3: "Простой",
    4: "Печать",
    5: "Прогрев",
}


# =====================================================================
# Загрузка конфигов
# =====================================================================

def load_printers_from_file(path: Path) -> list:
    """Загружает принтеры из одного YAML-файла."""
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        printers = data.get("printers", [])
        return [p for p in printers if p.get("enabled", True)]
    except Exception as e:
        logger.error(f"Ошибка чтения {path}: {e}")
        return []


def load_printers() -> list:
    """
    Загружает принтеры из обоих конфигов:
    - config/printers.yaml (ручной)
    - config/printers_auto.yaml (авто)
    Дедупликация по IP: если IP есть в обоих — берётся из ручного.
    """
    manual = load_printers_from_file(PRINTERS_CONFIG)
    auto = load_printers_from_file(PRINTERS_AUTO_CONFIG)

    # Дедупликация по IP
    seen_ips = set()
    result = []

    for p in manual:
        ip = p.get("ip")
        if ip and ip not in seen_ips:
            seen_ips.add(ip)
            p["_source"] = "manual"
            result.append(p)

    for p in auto:
        ip = p.get("ip")
        if ip and ip not in seen_ips:
            seen_ips.add(ip)
            p["_source"] = "auto"
            result.append(p)

    logger.info(f"Загружено принтеров: ручных {len(manual)}, авто {len(auto)}, итого {len(result)}")
    return result


# =====================================================================
# SNMP-опрос
# =====================================================================

def query_printer(printer: dict) -> dict:
    """Опрашивает один принтер по SNMP."""
    result = {
        "name": printer.get("name", "unknown"),
        "ip": printer.get("ip", "unknown"),
        "model": printer.get("model", "unknown"),
        "location": printer.get("location", "unknown"),
        "source": printer.get("_source", "unknown"),
        "status": "offline",
        "toner_level": None,
        "toner_percent": None,
        "pages_total": None,
        "error": None,
        "checked_at": datetime.now().isoformat(),
    }

    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData,
            UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity,
        )
    except ImportError:
        result["error"] = "pysnmp не установлен. Выполни: pip install --target=libs/ pysnmp"
        logger.error(result["error"])
        return result

    ip = printer["ip"]
    community = printer.get("snmp_community", "public")

    try:
        error_indication, error_status, _, var_binds = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ip, 161), timeout=2, retries=1),
                ContextData(),
                *[ObjectType(ObjectIdentity(oid)) for oid in OIDS.values()],
            )
        )

        if error_indication:
            result["error"] = f"SNMP ошибка: {error_indication}"
            return result

        if error_status:
            result["error"] = f"SNMP статус: {error_status.prettyPrint()}"
            return result

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
    """Опрашивает все принтеры."""
    if printers is None:
        printers = load_printers()

    results = []
    for printer in printers:
        results.append(query_printer(printer))

    return results


# =====================================================================
# Отчёт
# =====================================================================

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
    """Выводит отчёт в консоль."""
    print()
    print("=" * 80)
    print("  МОНИТОРИНГ ПРИНТЕРОВ")
    print("=" * 80)
    print()

    for r in results:
        status_icon = "🟢" if r["status"] in ("Простой", "Печать") else "🔴"
        source_icon = "📝" if r.get("source") == "manual" else "🔍"
        print(f"  {status_icon} {source_icon} {r['name']} ({r['ip']})")
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
    """Точка входа для мониторинга."""
    print()
    print("Загрузка списка принтеров...")
    printers = load_printers()

    if not printers:
        print("Список принтеров пуст. Проверь config/printers.yaml")
        print("Или запусти «Сканер сети» для автопоиска.")
        return

    print(f"Найдено принтеров: {len(printers)}")
    print("Опрос по SNMP...")
    print()

    results = monitor_all(printers)
    print_report(results)

    report_file = save_report(results)
    print()
    print(f"📄 Отчёт сохранён: {report_file}")
    print()
    input("Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
