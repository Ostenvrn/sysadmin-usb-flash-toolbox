"""
История отчётов.
"""
from pathlib import Path
from datetime import datetime

from app.core.logger import setup_logger

logger = setup_logger("reports-history")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
REPORTS_DIR = PROJECT_ROOT / "output" / "reports"


def format_size(size: int) -> str:
    for unit in ["Б", "КБ", "МБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ГБ"


def list_all_reports() -> list:
    """Возвращает все файлы отчётов."""
    if not REPORTS_DIR.exists():
        return []

    reports = []
    for f in REPORTS_DIR.iterdir():
        if f.is_file() and f.name.startswith("report_"):
            try:
                stat = f.stat()
                reports.append({
                    "path": f,
                    "name": f.name,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime),
                    "ext": f.suffix,
                })
            except Exception:
                pass

    reports.sort(key=lambda x: x["mtime"], reverse=True)
    return reports


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  ИСТОРИЯ ОТЧЁТОВ")
    print("=" * 80)
    print()

    reports = list_all_reports()

    if not reports:
        print("  📭 Отчётов не найдено.")
        print("  Сначала запусти «Сгенерировать отчёт».")
        print()
        input("  Нажми Enter...")
        return

    # Группируем по базовому имени (report_TIMESTAMP)
    by_base = {}
    for r in reports:
        base = r["name"].replace(".md", "").replace(".json", "").replace(".html", "").replace(".csv", "")
        by_base.setdefault(base, []).append(r)

    print(f"  Всего отчётов: {len(by_base)}")
    print()

    for base, files in sorted(by_base.items(), key=lambda x: x[1][0]["mtime"], reverse=True)[:20]:
        date_str = files[0]["mtime"].strftime("%d.%m.%Y %H:%M:%S")
        formats = ", ".join(f["ext"][1:] for f in files)
        total_size = sum(f["size"] for f in files)
        print(f"  📄 {base}")
        print(f"     Дата: {date_str}")
        print(f"     Форматы: {formats}")
        print(f"     Размер: {format_size(total_size)}")
        print()

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
