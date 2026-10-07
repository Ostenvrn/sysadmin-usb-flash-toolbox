"""
Health check — полная диагностика ПК.
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger
from app.categories.system.health_check import runner, report

logger = setup_logger("health-check")


def run():
    """Точка входа для health check."""
    print()
    print("=" * 80)
    print("  ДИАГНОСТИКА ПК (HEALTH CHECK)")
    print("=" * 80)
    print(f"  ПК: {os_detector.get_system_info()['hostname']}")
    print(f"  ОС: {os_detector.system}")
    print()
    print("  Запуск всех проверок...")
    print()

    # Запускаем все проверки
    results = runner.run_all_checks()

    # Итог
    summary = runner.summarize(results)

    # Вывод
    report.print_report(results, summary)

    # Сохранение
    print()
    save = input("  Сохранить отчёт? [Y/n]: ").strip().lower()
    if save != "n":
        json_path = report.save_json(results, summary)
        csv_path = report.save_csv(results)
        print()
        print(f"  ✅ JSON: {json_path}")
        print(f"  ✅ CSV:  {csv_path}")

    print()
    input("  Нажми Enter для продолжения...")
