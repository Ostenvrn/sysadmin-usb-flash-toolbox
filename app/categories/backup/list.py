"""
Список бэкапов.
Показывает все архивы в output/backups/ с информацией:
размер, дата, что внутри, профиль.
"""
import json
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("backup-list")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


def format_size(size: int) -> str:
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def get_backup_dir() -> Path:
    """Возвращает папку с бэкапами."""
    import yaml
    config_path = PROJECT_ROOT / "config" / "backup.yaml"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return PROJECT_ROOT / cfg.get("backup_dir", "output/backups")
        except Exception:
            pass
    return PROJECT_ROOT / "output" / "backups"


def list_backups() -> list:
    """Возвращает список бэкапов."""
    backup_dir = get_backup_dir()

    if not backup_dir.exists():
        return []

    backups = []

    # Ищем .tar.gz и .zip
    for pattern in ["*.tar.gz", "*.zip"]:
        for f in backup_dir.glob(pattern):
            try:
                stat = f.stat()
                # Парсим имя: <имя>_<дата>_<время>.tar.gz
                stem = f.stem.replace(".tar", "")

                # Пытаемся выделить дату
                date_str = None
                parts = stem.rsplit("_", 2)
                if len(parts) >= 3:
                    date_part = f"{parts[-2]}_{parts[-1]}"
                    try:
                        dt = datetime.strptime(date_part, "%Y-%m-%d_%H-%M-%S")
                        date_str = dt.strftime("%d.%m.%Y %H:%M:%S")
                    except ValueError:
                        pass

                name_part = parts[0] if len(parts) >= 3 else stem

                backups.append({
                    "path": f,
                    "name": name_part,
                    "size": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime),
                    "date_str": date_str or "unknown",
                    "format": "zip" if f.suffix == ".zip" else "tar.gz",
                })
            except Exception as e:
                logger.error(f"Ошибка чтения {f}: {e}")

    # Сортируем по дате (новые сверху)
    backups.sort(key=lambda b: b["mtime"], reverse=True)
    return backups


def print_backups(backups: list):
    """Красивый вывод списка."""
    if not backups:
        print()
        print("  📭 Бэкапов не найдено.")
        print("  Запусти «Создать бэкап» — он создаст первый архив.")
        print()
        return

    total_size = sum(b["size"] for b in backups)

    print()
    print("=" * 80)
    print(f"  📋 СПИСОК БЭКАПОВ ({len(backups)})")
    print("=" * 80)
    print(f"  Общий размер: {format_size(total_size)}")
    print()

    for i, b in enumerate(backups, start=1):
        print(f"  [{i:2}] {b['name']}")
        print(f"       📅 {b['date_str']}")
        print(f"       📦 {format_size(b['size'])}  ({b['format']})")
        print(f"       📁 {b['path'].name}")
        print()


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  СПИСОК БЭКАПОВ")
    print("=" * 80)

    backups = list_backups()
    print_backups(backups)

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
