"""
Очистка системы.
Удаляет временные файлы, кэш, логи.
Работает на Windows и Linux.
"""
import os
import shutil
import tempfile
from pathlib import Path

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("system-cleanup")


def get_temp_paths() -> list:
    """Возвращает список путей для очистки."""
    paths = []

    if os_detector.is_windows:
        paths = [
            os.environ.get("TEMP", "C:\\Windows\\Temp"),
            os.environ.get("TMP", "C:\\Windows\\Temp"),
            "C:\\Windows\\Temp",
        ]
    else:
        paths = [
            "/tmp",
            os.path.expanduser("~/.cache"),
            "/var/tmp",
        ]

    # Убираем дубликаты и несуществующие
    result = []
    for p in paths:
        if p and os.path.exists(p) and p not in result:
            result.append(p)

    return result


def get_dir_size(path: str) -> int:
    """Считает размер папки в байтах."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    pass
    except Exception:
        pass
    return total


def clean_path(path: str) -> tuple:
    """
    Очищает папку.
    Возвращает (удалено_файлов, освобождено_байт, ошибок).
    """
    deleted = 0
    freed = 0
    errors = 0

    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    size = os.path.getsize(item_path)
                    os.unlink(item_path)
                    deleted += 1
                    freed += size
                elif os.path.isdir(item_path):
                    size = get_dir_size(item_path)
                    shutil.rmtree(item_path, ignore_errors=True)
                    deleted += 1
                    freed += size
            except (OSError, PermissionError):
                errors += 1
    except Exception as e:
        logger.error(f"Ошибка очистки {path}: {e}")

    return deleted, freed, errors


def format_size(size: int) -> str:
    """Форматирует размер в человекочитаемый вид."""
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def print_menu():
    """Меню очистки."""
    print()
    print("=" * 60)
    print("  ОЧИСТКА СИСТЕМЫ")
    print("=" * 60)
    print()
    print(f"  ОС: {os_detector.system}")
    print()

    paths = get_temp_paths()

    print("  Папки для очистки:")
    for i, p in enumerate(paths, start=1):
        size = get_dir_size(p)
        print(f"    [{i}] {p}  ({format_size(size)})")

    print()
    print("    [a] Очистить все")
    print("    [0] ← Назад")
    print()

    return paths


def run():
    """Точка входа."""
    paths = print_menu()

    if not paths:
        print("  Нет папок для очистки.")
        input("  Нажми Enter для продолжения...")
        return

    choice = input("  Ваш выбор: ").strip().lower()

    if choice == "0":
        return

    if choice == "a":
        targets = paths
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(paths):
            targets = [paths[idx]]
        else:
            print("  Неверный выбор.")
            input("  Нажми Enter для продолжения...")
            return
    else:
        print("  Неверный выбор.")
        input("  Нажми Enter для продолжения...")
        return

    print()
    print("  🧹 Очистка...")
    print()

    total_deleted = 0
    total_freed = 0
    total_errors = 0

    for p in targets:
        print(f"  📁 {p}")
        deleted, freed, errors = clean_path(p)
        print(f"     Удалено: {deleted} объектов")
        print(f"     Освобождено: {format_size(freed)}")
        if errors:
            print(f"     ⚠️  Ошибок доступа: {errors}")
        print()

        total_deleted += deleted
        total_freed += freed
        total_errors += errors

    print("=" * 60)
    print(f"  ИТОГО: удалено {total_deleted} объектов, "
          f"освобождено {format_size(total_freed)}")
    if total_errors:
        print(f"  ⚠️  Ошибок доступа: {total_errors} (возможно, нужны права root)")
    print("=" * 60)
    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
