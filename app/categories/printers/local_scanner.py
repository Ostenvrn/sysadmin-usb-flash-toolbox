"""
Поиск локальных принтеров (подключённых к ПК через USB).
- Windows: PowerShell Get-Printer + WMI
- Linux: CUPS (lpstat, lpinfo)
Сохраняет найденные принтеры в config/printers_local.yaml.
"""
import json
import yaml
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("local-printer-scanner")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
LOCAL_CONFIG = PROJECT_ROOT / "config" / "printers_local.yaml"


# =====================================================================
# Windows: поиск локальных принтеров
# =====================================================================

def scan_windows_printers() -> list:
    """
    Ищет локальные принтеры на Windows через PowerShell.
    Возвращает список словарей: name, driver, port, status, type.
    """
    printers = []

    # PowerShell-команда: получить все принтеры + их порты
    ps_cmd = (
        "Get-Printer | "
        "Select-Object Name,DriverName,PortName,PrinterStatus | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, stderr = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0:
        logger.error(f"PowerShell ошибка: {stderr}")
        return printers

    try:
        data = json.loads(stdout)
        # Если один принтер — PowerShell вернёт объект, а не массив
        if isinstance(data, dict):
            data = [data]

        for p in data:
            port = p.get("PortName", "")
            # Локальные принтеры: порты USB001, LPT1, COM1, PORTPROMPT
            # Сетевые: IP_192.168.x.x, WSD-xxxx
            is_local = (
                port.upper().startswith("USB")
                or port.upper().startswith("LPT")
                or port.upper().startswith("COM")
                or port.upper() == "PORTPROMPT:"
            )

            printers.append({
                "name": p.get("Name", "unknown"),
                "driver": p.get("DriverName", "unknown"),
                "port": port,
                "status": str(p.get("PrinterStatus", "unknown")),
                "type": "local" if is_local else "network",
            })
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")

    return printers


# =====================================================================
# Linux: поиск локальных принтеров
# =====================================================================

def scan_linux_printers() -> list:
    """
    Ищет принтеры на Linux через CUPS (lpstat, lpinfo).
    Возвращает список словарей: name, driver, port, status, type.
    """
    printers = []

    # 1. Получаем список принтеров через lpstat
    rc, stdout, stderr = os_detector.run_command(["lpstat", "-p", "-l"])

    if rc != 0:
        logger.warning(f"lpstat не работает: {stderr}")
        logger.warning("CUPS установлен? sudo apt install cups")
        return printers

    # Парсим вывод lpstat
    # Формат: printer HP_LaserJet is idle. enabled since ...
    current_printer = None
    for line in stdout.splitlines():
        if line.startswith("printer "):
            parts = line.split()
            name = parts[1] if len(parts) > 1 else "unknown"
            status = "idle" if "idle" in line else "unknown"
            current_printer = {
                "name": name,
                "driver": "unknown",
                "port": "unknown",
                "status": status,
                "type": "local",
            }
            printers.append(current_printer)
        elif current_printer and "Description:" in line:
            current_printer["description"] = line.split(":", 1)[1].strip()
        elif current_printer and "Location:" in line:
            current_printer["location"] = line.split(":", 1)[1].strip()
        elif current_printer and "Make and Model:" in line:
            current_printer["driver"] = line.split(":", 1)[1].strip()

    # 2. Определяем тип (USB или сетевой) через lpinfo -v
    rc2, stdout2, _ = os_detector.run_command(["lpinfo", "-v"])
    if rc2 == 0:
        for line in stdout2.splitlines():
            # Формат: direct usb://HP/LaserJet?serial=...
            #         network socket://192.168.1.100
            if "usb://" in line:
                for p in printers:
                    if p.get("type") == "local":
                        p["port"] = "usb"
            elif "socket://" in line or "ipp://" in line:
                # Сетевой — можно пометить, но пока оставим как есть
                pass

    return printers


# =====================================================================
# Универсальная точка входа
# =====================================================================

def scan_local_printers() -> list:
    """Определяет ОС и вызывает нужный сканер."""
    if os_detector.is_windows:
        logger.info("Сканирование локальных принтеров (Windows)")
        return scan_windows_printers()
    elif os_detector.is_linux:
        logger.info("Сканирование локальных принтеров (Linux)")
        return scan_linux_printers()
    else:
        logger.warning(f"ОС {os_detector.system} не поддерживается")
        return []


def save_local_config(printers: list) -> Path:
    """Сохраняет найденные локальные принтеры в config/printers_local.yaml."""
    data = {
        "generated_at": datetime.now().isoformat(),
        "hostname": os_detector.get_system_info()["hostname"],
        "os": os_detector.system,
        "printers": printers,
    }

    with open(LOCAL_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    logger.info(f"Локальный конфиг сохранён: {LOCAL_CONFIG}")
    return LOCAL_CONFIG


def print_report(printers: list):
    """Красивый вывод результата."""
    print()
    print("=" * 70)
    print("  ЛОКАЛЬНЫЕ ПРИНТЕРЫ")
    print("=" * 70)
    print(f"  ПК: {os_detector.get_system_info()['hostname']}")
    print(f"  ОС: {os_detector.system}")
    print()

    if not printers:
        print("  Локальные принтеры не найдены.")
        print()
        if os_detector.is_linux:
            print("  Проверь:")
            print("    - Установлен ли CUPS: sudo apt install cups")
            print("    - Запущен ли CUPS: sudo systemctl status cups")
            print("    - Есть ли принтеры: lpstat -p")
        elif os_detector.is_windows:
            print("  Проверь:")
            print("    - Запущен ли PowerShell")
            print("    - Есть ли принтеры: Get-Printer")
        return

    local_count = sum(1 for p in printers if p.get("type") == "local")
    network_count = sum(1 for p in printers if p.get("type") == "network")

    for p in printers:
        icon = "🔌" if p.get("type") == "local" else "🌐"
        print(f"  {icon} {p['name']}")
        print(f"     Драйвер: {p.get('driver', 'unknown')}")
        print(f"     Порт:    {p.get('port', 'unknown')}")
        print(f"     Статус:  {p.get('status', 'unknown')}")
        print(f"     Тип:     {p.get('type', 'unknown')}")
        if p.get("location"):
            print(f"     Где:     {p['location']}")
        print()

    print("-" * 70)
    print(f"  Всего: {len(printers)} | 🔌 Локальных: {local_count} | 🌐 Сетевых: {network_count}")
    print("=" * 70)


def run():
    """Точка входа."""
    print()
    print("=" * 70)
    print("  ПОИСК ЛОКАЛЬНЫХ ПРИНТЕРОВ")
    print("=" * 70)
    print()
    print(f"  Сканирую принтеры на этом ПК ({os_detector.get_system_info()['hostname']})...")
    print()

    printers = scan_local_printers()
    print_report(printers)

    if not printers:
        print()
        input("  Нажми Enter для продолжения...")
        return

    print()
    save = input("  Сохранить в config/printers_local.yaml? [Y/n]: ").strip().lower()
    if save != "n":
        path = save_local_config(printers)
        print()
        print(f"  ✅ Сохранено: {path}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
