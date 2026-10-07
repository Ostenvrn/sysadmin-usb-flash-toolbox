"""
Восстановление из бэкапа.
- Распаковка в выбранную папку
- Проверка свободного места
- Подтверждение перед перезаписью
"""
import os
import tarfile
import zipfile
import shutil
from pathlib import Path

from app.core.logger import setup_logger
from app.categories.backup.list import list_backups, format_size

logger = setup_logger("backup-restore")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


def get_free_space(path: Path) -> int:
    """Свободное место."""
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return 0


def get_archive_size(path: Path) -> int:
    """Размер архива после распаковки."""
    try:
        if path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as tar:
                return sum(m.size for m in tar.getmembers() if m.isfile())
        elif path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                return sum(i.file_size for i in zf.infolist())
    except Exception:
        pass
    return 0


def restore_archive(archive: Path, target_dir: Path) -> dict:
    """Распаковывает архив в target_dir."""
    result = {"ok": False, "extracted": 0, "errors": []}

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if archive.name.endswith(".tar.gz"):
            with tarfile.open(archive, "r:gz") as tar:
                members = tar.getmembers()
                total = len(members)

                for i, m in enumerate(members, start=1):
                    try:
                        tar.extract(m, target_dir)
                        result["extracted"] += 1

                        if i % 500 == 0:
                            print(f"       ...{i}/{total} файлов")
                    except Exception as e:
                        result["errors"].append(f"{m.name}: {e}")

        elif archive.suffix == ".zip":
            with zipfile.ZipFile(archive, "r") as zf:
                names = zf.namelist()
                total = len(names)

                for i, name in enumerate(names, start=1):
                    try:
                        zf.extract(name, target_dir)
                        result["extracted"] += 1

                        if i % 500 == 0:
                            print(f"       ...{i}/{total} файлов")
                    except Exception as e:
                        result["errors"].append(f"{name}: {e}")

        else:
            result["errors"].append("неизвестный формат архива")
            return result

        if result["extracted"] > 0:
            result["ok"] = True
    except Exception as e:
        result["errors"].append(f"ошибка распаковки: {e}")

    return result


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  ВОССТАНОВЛЕНИЕ ИЗ БЭКАПА")
    print("=" * 80)
    print()

    backups = list_backups()

    if not backups:
        print("  📭 Бэкапов не найдено.")
        print()
        input("  Нажми Enter...")
        return

    # Выбор бэкапа
    print(f"  Доступно бэкапов: {len(backups)}")
    print()
    for i, b in enumerate(backups[:20], start=1):
        print(f"    [{i:2}] {b['name']} — {b['date_str']} ({format_size(b['size'])})")

    print("    [0] ← Назад")
    print()

    choice = input("  Выбери бэкап для восстановления: ").strip()
    if choice == "0":
        return

    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(backups[:20]):
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    backup = backups[int(choice) - 1]
    archive_path = backup["path"]

    # Куда восстанавливать
    print()
    print(f"  Выбран: {archive_path.name}")
    print()
    print("  Куда восстановить?")
    print("    [1] В папку output/restored/ (безопасно)")
    print("    [2] В свою папку")
    print("    [0] ← Назад")
    print()

    target_choice = input("  Выбор [1]: ").strip() or "1"

    if target_choice == "0":
        return
    elif target_choice == "1":
        target_dir = PROJECT_ROOT / "output" / "restored" / archive_path.stem
    elif target_choice == "2":
        custom = input("  Путь для восстановления: ").strip()
        if not custom:
            return
        target_dir = Path(os.path.expanduser(custom)).resolve()
    else:
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    # Проверка свободного места
    archive_size = get_archive_size(archive_path)
    free = get_free_space(target_dir.parent if target_dir.parent.exists() else Path("/"))

    print()
    print(f"  📁 Куда:        {target_dir}")
    print(f"  📦 В архиве:    {format_size(archive_size)}")
    print(f"  💾 Свободно:    {format_size(free)}")

    if free < archive_size:
        print()
        print("  🔴 НЕДОСТАТОЧНО МЕСТА!")
        print()
        input("  Нажми Enter...")
        return

    # Предупреждение если папка существует
    if target_dir.exists() and any(target_dir.iterdir()):
        print()
        print(f"  ⚠️  Папка {target_dir} уже существует и не пуста!")
        print(f"     Файлы с одинаковыми именами будут ПЕРЕЗАПИСАНЫ.")
        print()
        confirm = input("  Продолжить? [y/N]: ").strip().lower()
        if confirm != "y":
            return

    # Подтверждение
    print()
    print("=" * 80)
    print("  ⚠️  ВОССТАНОВЛЕНИЕ")
    print("=" * 80)
    print()
    print(f"  Архив:   {archive_path.name}")
    print(f"  Куда:    {target_dir}")
    print(f"  Размер:  {format_size(archive_size)}")
    print()

    confirm = input("  Начать восстановление? [y/N]: ").strip().lower()
    if confirm != "y":
        return

    print()
    print("  📦 Распаковка...")
    print()

    result = restore_archive(archive_path, target_dir)

    print()
    print("=" * 80)
    if result["ok"]:
        print(f"  ✅ ВОССТАНОВЛЕНО: {result['extracted']} файлов")
        print(f"  📁 Папка: {target_dir}")

        if result["errors"]:
            print()
            print(f"  ⚠️  Ошибок: {len(result['errors'])}")
            for err in result["errors"][:5]:
                print(f"     • {err}")
    else:
        print("  ❌ ОШИБКА ВОССТАНОВЛЕНИЯ")
        for err in result["errors"][:5]:
            print(f"     • {err}")
    print("=" * 80)

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
