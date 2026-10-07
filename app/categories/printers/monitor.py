"""
Мониторинг принтеров.
- Сетевые: SNMP-опрос (тонер, статус, страницы)
- Локальные: только список (USB, без SNMP)
Читает три конфига:
  - config/printers.yaml (ручной)
  - config/printers_auto.yaml (авто, сетевые)
  - config/printers_local.yaml (локальные USB)
"""
import json
import yaml
from pathlib import Path
from datetime import datetime

from app.core.logger import setup_logger

logger = setup_logger("printer-monitor")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
PRINTERS_CONFIG = PROJECT_ROOT / "config" / "printers.yaml"
PRINTERS_AUTO_CONFIG = PROJECT_ROOT / "config" / "printers_auto.yaml"
PRINTERS_LOCAL_CONFIG = PROJECT_ROOT / "config" / "printers_local.yaml"
OUTPUT_DIR = PROJECT_ROOT / "output" / "scans"


# =====================================================================
# SNMP OID
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
    """Загружает принтеры из YAML-файла."""
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


def load_network_printers() -> list:
    """Загружает сетевые принтеры (ручной + авто)."""
    manual = load_printers_from_file(PRINTERS_CONFIG)
    auto = load_printers_from_file(PRINTERS_AUTO_CONFIG)

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

    logger.info(f"Сетевых принтеров: ручных {len(manual)}, авто {len(auto)}, итого {len(result)}")
    return result


def load_local_printers() -> list:
    """Загружает локальные принтеры (USB)."""
    local = load_printers_from_file(PRINTERS_LOCAL_CONFIG)
    logger.info(f"Локальных принтеров: {len(local)}")
    return local


# =====================================================================
# SNMP-опрос сетевых
# =====================================================================

def query_printer(printer: dict) -> dict:
    """Опрашивает сетевой принтер по SNMP."""
    result = {
        "name": printer.get("name", "unknown"),
        "ip": printer.get("ip", "unknown"),
        "model": printer.get("model", "unknown"),
        "location": printer.get("location", "unknown"),
        "source": printer.get("_source", "unknown"),
        "type": "network",
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
        result["error"] = "pysnmp не установлен"
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
            result["error"] = f"SNMP: {error_indication}"
            return result
        if error_status:
            result["error"] = f"SNMP: {error_status.prettyPrint()}"
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

    except Exception as e:
        result["error"] = f"Исключение: {e}"
        logger.error(f"{result['name']} ({ip}): {result['error']}")

    return result


def monitor_all() -> dict:
    """Опрашивает сетевые принтеры + собирает локальные."""
    network = load_network_printers()
    local = load_local_printers()

    network_results = [query_printer(p) for p in network]

    local_results = []
    for p in local:
        local_results.append({
            "name": p.get("name", "unknown"),
            "ip": None,
            "model": p.get("driver", "unknown"),
            "location": p.get("location", ""),
            "source": "local",
            "type": "local",
            "status": p.get("status", "unknown"),
            "port": p.get("port", "unknown"),
            "toner_level": None,
            "toner_percent": None,
            "pages_total": None,
            "error": None,
            "checked_at": datetime.now().isoformat(),
        })

    return {
        "network": network_results,
        "local": local_results,
    }


# =====================================================================
# Отчёт
# =====================================================================

def save_report(results: dict) -> Path:
    """Сохраняет отчёт в JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = OUTPUT_DIR / f"printers_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"Отчёт сохранён: {filename}")
    return filename


def print_report(results: dict):
    """Выводит отчёт в консоль."""
    network = results["network"]
    local = results["local"]

    print()
    print("=" * 80)
    print("  МОНИТОРИНГ ПРИНТЕРОВ")
    print("=" * 80)
    print()

    # --- Сетевые ---
    print(f"  🌐 СЕТЕВЫЕ ПРИНТЕРЫ ({len(network)})")
    print("-" * 80)
    if not network:
        print("  Нет сетевых принтеров. Запусти «Сканер сети».")
    for r in network:
        status_icon = "🟢" if r["status"] in ("Простой", "Печать") else "🔴"
        source_icon = "📝" if r.get("source") == "manual" else "🔍"
        print(f"  {status_icon} {source_icon} {r['name']} ({r['ip']})")
        print(f"     Модель:  {r['model']}")
        print(f"     Статус:  {r['status']}")
        if r.get("toner_percent") is not None:
            toner = r["toner_percent"]
            icon = "🔴" if toner < 10 else "🟡" if toner < 30 else "🟢"
            print(f"     Тонер:   {icon} {toner}%")
        if r.get("pages_total"):
            print(f"     Страниц: {r['pages_total']}")
        if r.get("error"):
            print(f"     Ошибка:  {r['error']}")
        print()

    # --- Локальные ---
    print(f"  🔌 ЛОКАЛЬНЫЕ ПРИНТЕРЫ ({len(local)})")
    print("-" * 80)
    if not local:
        print("  Нет локальных принтеров. Запусти «Локальные принтеры (USB)».")
    for r in local:
        print(f"  🔌 {r['name']}")
        print(f"     Драйвер: {r['model']}")
        print(f"     Порт:    {r['port']}")
        print(f"     Статус:  {r['status']}")
        print()

    # --- Итог ---
    total_network = len(network)
    online = sum(1 for r in network if r["status"] not in ("offline", "Неизвестно"))
    low_toner = sum(
        1 for r in network
        if r.get("toner_percent") is not None and r["toner_percent"] < 10
    )

    print("=" * 80)
    print(f"  ИТОГО: Всего {total_network + len(local)} | "
          f"🌐 Сетевых {total_network} (онлайн {online}) | "
          f"🔌 Локальных {len(local)} | "
          f"Тонер < 10%: {low_toner}")
    print("=" * 80)


def run():
    """Точка входа."""
    print()
    print("Загрузка принтеров...")

    results = monitor_all()

    if not results["network"] and not results["local"]:
        print("Список принтеров пуст.")
        print("Запусти «Сканер сети» или «Локальные принтеры (USB)».")
        print()
        input("Нажми Enter для продолжения...")
        return

    print(f"Сетевых: {len(results['network'])}, локальных: {len(results['local'])}")
    print("Опрос сетевых по SNMP...")
    print()

    print_report(results)

    report_file = save_report(results)
    print()
    print(f"📄 Отчёт сохранён: {report_file}")
    print()
    input("Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
