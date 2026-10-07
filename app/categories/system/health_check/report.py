"""
Генерация отчёта по здоровью ПК.
- Красивый вывод в консоль
- Сохранение в JSON
- Экспорт в CSV
- Рекомендации по решению проблем
"""
import json
import csv
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("health-check-report")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.resolve()
REPORTS_DIR = PROJECT_ROOT / "output" / "health"


def print_report(results: list, summary: dict):
    """Красивый вывод отчёта."""
    print()
    print("=" * 80)
    print("  ОТЧЁТ О ЗДОРОВЬЕ ПК")
    print("=" * 80)
    print(f"  ПК: {os_detector.get_system_info()['hostname']}")
    print(f"  ОС: {os_detector.system}")
    print(f"  Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print()

    # Сначала показываем проблемные проверки
    problems = [r for r in results if r.get("status") in ("warning", "critical")]
    ok_checks = [r for r in results if r.get("status") == "ok"]

    if problems:
        print("=" * 80)
        print("  ⚠️  ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ")
        print("=" * 80)
        print()

        for r in problems:
            status = r.get("status", "ok")
            icon = {"warning": "🟡", "critical": "🔴"}.get(status, "⚪")
            print(f"  {icon} {r['category']}")
            print("-" * 80)

            # Детали
            details = r.get("details", {})
            if details:
                for key, val in details.items():
                    if isinstance(val, dict):
                        for k2, v2 in val.items():
                            print(f"     {k2}: {v2}")
                    elif isinstance(val, list):
                        for item in val[:5]:
                            if isinstance(item, dict):
                                print(f"     • {item}")
                            else:
                                print(f"     • {item}")
                    else:
                        print(f"     {key}: {val}")

            # Проблемы
            probs = r.get("problems", [])
            if probs:
                print()
                for p in probs:
                    print(f"     {p}")

            # Рекомендации
            recs = r.get("recommendations", [])
            if recs:
                print()
                print("     💡 РЕКОМЕНДАЦИИ:")
                for rec in recs:
                    print(f"       → {rec}")

            print()
            print()

    # Потом — успешные проверки
    if ok_checks:
        print("=" * 80)
        print("  ✅ УСПЕШНЫЕ ПРОВЕРКИ")
        print("=" * 80)
        print()

        for r in ok_checks:
            print(f"  🟢 {r['category']}")

            # Краткие детали для контекста
            details = r.get("details", {})
            if details:
                for key, val in details.items():
                    if isinstance(val, dict):
                        for k2, v2 in val.items():
                            print(f"     {k2}: {v2}")
                    elif isinstance(val, list):
                        for item in val[:3]:
                            print(f"     • {item}")
                    else:
                        print(f"     {key}: {val}")
            print()

    # Итог
    print("=" * 80)
    print(f"  ИТОГ: Всего {summary['total']} проверок | "
          f"🟢 OK: {summary['ok']} | "
          f"🟡 Warning: {summary['warning']} | "
          f"🔴 Critical: {summary['critical']}")
    print("=" * 80)


def save_json(results: list, summary: dict) -> Path:
    """Сохраняет отчёт в JSON."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = REPORTS_DIR / f"health_{timestamp}.json"

    data = {
        "generated_at": datetime.now().isoformat(),
        "hostname": os_detector.get_system_info()["hostname"],
        "os": os_detector.system,
        "summary": summary,
        "results": results,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"Отчёт сохранён: {filename}")
    return filename


def save_csv(results: list) -> Path:
    """Экспорт в CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = REPORTS_DIR / f"health_{timestamp}.csv"

    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Категория", "Статус", "Проблемы", "Рекомендации"])
        for r in results:
            problems = " | ".join(r.get("problems", []))
            recs = " | ".join(r.get("recommendations", []))
            writer.writerow([
                r.get("category", ""),
                r.get("status", ""),
                problems,
                recs,
            ])

    logger.info(f"CSV сохранён: {filename}")
    return filename
