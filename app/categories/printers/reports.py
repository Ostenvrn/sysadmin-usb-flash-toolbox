"""
Отчёты по принтерам.
- Читает сохранённые JSON-отчёты из output/scans/
- Показывает историю: когда, какой принтер, тонер
- Экспортирует в CSV
"""
import json
import csv
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("printer-reports")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
SCANS_DIR = PROJECT_ROOT / "output" / "scans"
REPORTS_DIR = PROJECT_ROOT / "output" / "reports"


# =====================================================================
# Загрузка отчётов
# =====================================================================

def list_reports() -> list:
    """Возвращает список JSON-отчётов, отсортированных по дате (новые сверху)."""
    if not SCANS_DIR.exists():
        return []

    files = sorted(SCANS_DIR.glob("printers_*.json"), reverse=True)
    return files


def load_report(path: Path) -> dict:
    """Загружает один JSON-отчёт."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {path}: {e}")
        return {}


# =====================================================================
# Показ отчётов
# =====================================================================

def show_reports_list():
    """Показывает список доступных отчётов."""
    reports = list_reports()

    print()
    print("=" * 70)
    print("  ОТЧЁТЫ ПО ПРИНТЕРАМ")
    print("=" * 70)
    print()

    if not reports:
        print("  Отчётов нет.")
        print("  Запусти «Мониторинг» — он создаст первый отчёт.")
        print()
        input("  Нажми Enter для продолжения...")
        return

    print(f"  Найдено отчётов: {len(reports)}")
    print()

    for i, path in enumerate(reports[:20], start=1):
        # Имя файла: printers_2026-10-07_14-30-00.json
        name = path.stem.replace("printers_", "")
        try:
            dt = datetime.strptime(name, "%Y-%m-%d_%H-%M-%S")
            date_str = dt.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            date_str = name

        size_kb = path.stat().st_size / 1024
        print(f"  [{i:2}] {date_str}  ({size_kb:.1f} КБ)")

    print()
    print("  [0] ← Назад")
    print()

    choice = input("  Выбери отчёт для просмотра: ").strip()

    if choice == "0":
        return

    if not choice.isdigit():
        print("  Неверный выбор.")
        return

    idx = int(choice) - 1
    if idx < 0 or idx >= len(reports[:20]):
        print("  Неверный выбор.")
        return

    show_report_detail(reports[idx])


def show_report_detail(path: Path):
    """Показывает содержимое одного отчёта."""
    data = load_report(path)

    print()
    print("=" * 70)
    print(f"  ОТЧЁТ: {path.name}")
    print("=" * 70)
    print()

    # Поддержка двух форматов: старый (list) и новый (dict)
    if isinstance(data, list):
        # Старый формат — просто список принтеров
        network = data
        local = []
    elif isinstance(data, dict):
        network = data.get("network", [])
        local = data.get("local", [])
    else:
        print("  Неизвестный формат отчёта.")
        return

    # --- Сетевые ---
    if network:
        print(f"  🌐 СЕТЕВЫЕ ({len(network)})")
        print("-" * 70)
        for r in network:
            status = r.get("status", "unknown")
            icon = "🟢" if status in ("Простой", "Печать") else "🔴"
            print(f"  {icon} {r.get('name', 'unknown')} ({r.get('ip', '?')})")
            print(f"     Модель: {r.get('model', '?')}")
            print(f"     Статус: {status}")

            toner = r.get("toner_percent")
            if toner is not None:
                t_icon = "🔴" if toner < 10 else "🟡" if toner < 30 else "🟢"
                print(f"     Тонер:  {t_icon} {toner}%")

            if r.get("pages_total"):
                print(f"     Страниц: {r['pages_total']}")

            if r.get("error"):
                print(f"     Ошибка: {r['error']}")

            print()

    # --- Локальные ---
    if local:
        print(f"  🔌 ЛОКАЛЬНЫЕ ({len(local)})")
        print("-" * 70)
        for r in local:
            print(f"  🔌 {r.get('name', 'unknown')}")
            print(f"     Драйвер: {r.get('model', '?')}")
            print(f"     Порт:    {r.get('port', '?')}")
            print(f"     Статус:  {r.get('status', '?')}")
            print()

    # --- Итог ---
    total = len(network) + len(local)
    print("=" * 70)
    print(f"  ВСЕГО: {total} | 🌐 Сетевых: {len(network)} | 🔌 Локальных: {len(local)}")
    print("=" * 70)

    print()
    export = input("  Экспортировать в CSV? [y/N]: ").strip().lower()
    if export == "y":
        csv_path = export_to_csv(data, path.stem)
        if csv_path:
            print()
            print(f"  ✅ CSV сохранён: {csv_path}")

    print()
    input("  Нажми Enter для продолжения...")


# =====================================================================
# Экспорт
# =====================================================================

def export_to_csv(data, base_name: str) -> Path:
    """Экспортирует отчёт в CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / f"{base_name}.csv"

    if isinstance(data, list):
        network = data
        local = []
    elif isinstance(data, dict):
        network = data.get("network", [])
        local = data.get("local", [])
    else:
        return None

    try:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")

            # Заголовок
            writer.writerow([
                "Тип", "Имя", "IP", "Модель", "Расположение",
                "Статус", "Тонер (%)", "Страниц", "Ошибка", "Проверено"
            ])

            # Сетевые
            for r in network:
                writer.writerow([
                    "Сетевой",
                    r.get("name", ""),
                    r.get("ip", ""),
                    r.get("model", ""),
                    r.get("location", ""),
                    r.get("status", ""),
                    r.get("toner_percent", ""),
                    r.get("pages_total", ""),
                    r.get("error", ""),
                    r.get("checked_at", ""),
                ])

            # Локальные
            for r in local:
                writer.writerow([
                    "Локальный",
                    r.get("name", ""),
                    "",
                    r.get("model", ""),
                    r.get("location", ""),
                    r.get("status", ""),
                    "",
                    "",
                    "",
                    r.get("checked_at", ""),
                ])

        logger.info(f"CSV сохранён: {csv_path}")
        return csv_path
    except Exception as e:
        logger.error(f"Ошибка экспорта в CSV: {e}")
        print(f"  ❌ Ошибка: {e}")
        return None


# =====================================================================
# Точка входа
# =====================================================================

def run():
    """Точка входа для отчётов."""
    show_reports_list()


if __name__ == "__main__":
    run()
