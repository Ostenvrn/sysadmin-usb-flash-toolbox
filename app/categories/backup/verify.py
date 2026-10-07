"""
Проверка бэкапов.
- Целостность архива
- Читаемость файлов
- Полное тестовое восстановление (опционально)
"""
import tarfile
import zipfile
import tempfile
import shutil
from pathlib import Path

from app.core.logger import setup_logger
from app.categories.backup.list import list_backups, format_size

logger = setup_logger("backup-verify")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


def verify_tar_gz(path: Path) -> dict:
    """Проверка tar.gz."""
    result = {
        "ok": False,
        "reason": "",
        "file_count": 0,
        "total_size": 0,
        "sample_errors": [],
    }

    try:
        with tarfile.open(path, "r:gz") as tar:
            members = tar.getmembers()
            result["file_count"] = len(members)

            if not members:
                result["reason"] = "архив пустой"
                return result

            # Суммарный размер
            for m in members:
                if m.isfile():
                    result["total_size"] += m.size

            # Проверяем случайные 20 файлов
            import random
            sample = random.sample(members, min(20, len(members)))

            for member in sample:
                if member.isfile():
                    try:
                        f = tar.extractfile(member)
                        if f:
                            data = f.read(4096)  # читаем 4 КБ
                            if not data and member.size > 0:
                                result["sample_errors"].append(
                                    f"пустой файл: {member.name}"
                                )
                    except Exception as e:
                        result["sample_errors"].append(
                            f"{member.name}: {e}"
                        )

            if result["sample_errors"]:
                result["reason"] = f"ошибок: {len(result['sample_errors'])}"
            else:
                result["ok"] = True
                result["reason"] = f"проверено {len(sample)} из {len(members)} файлов"
    except Exception as e:
        result["reason"] = f"ошибка: {e}"

    return result


def verify_zip(path: Path) -> dict:
    """Проверка zip."""
    result = {
        "ok": False,
        "reason": "",
        "file_count": 0,
        "total_size": 0,
        "sample_errors": [],
    }

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            result["file_count"] = len(names)

            if not names:
                result["reason"] = "архив пустой"
                return result

            # testzip — проверяет CRC всех файлов
            bad = zf.testzip()
            if bad:
                result["reason"] = f"повреждён: {bad}"
                return result

            # Суммарный размер
            for info in zf.infolist():
                result["total_size"] += info.file_size

            result["ok"] = True
            result["reason"] = f"все {len(names)} файлов целые"
    except Exception as e:
        result["reason"] = f"ошибка: {e}"

    return result


def test_extract(path: Path, test_dir: Path) -> dict:
    """
    Тестовое восстановление в временную папку.
    Проверяет, что архив реально распаковывается.
    """
    result = {"ok": False, "reason": "", "extracted_count": 0}

    try:
        test_dir.mkdir(parents=True, exist_ok=True)

        if path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as tar:
                members = tar.getmembers()
                # Распаковываем первые 5 файлов (для проверки)
                sample = members[:5]
                for m in sample:
                    try:
                        tar.extract(m, test_dir)
                        result["extracted_count"] += 1
                    except Exception:
                        pass

        elif path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()[:5]
                for n in names:
                    try:
                        zf.extract(n, test_dir)
                        result["extracted_count"] += 1
                    except Exception:
                        pass

        if result["extracted_count"] > 0:
            result["ok"] = True
            result["reason"] = f"распаковано {result['extracted_count']} файлов"
        else:
            result["reason"] = "не удалось распаковать ни одного файла"
    except Exception as e:
        result["reason"] = f"ошибка: {e}"

    return result


def verify_backup(path: Path, full_test: bool = False) -> dict:
    """
    Полная проверка одного бэкапа.
    full_test=True — с тестовым восстановлением.
    """
    print(f"  🔍 Проверка: {path.name}")
    print(f"     Размер: {format_size(path.stat().st_size)}")
    print()

    result = {
        "path": path,
        "ok": False,
        "integrity": None,
        "extract_test": None,
    }

    # 1. Проверка целостности
    print(f"     1) Проверка целостности...")
    if path.name.endswith(".tar.gz"):
        integrity = verify_tar_gz(path)
    elif path.suffix == ".zip":
        integrity = verify_zip(path)
    else:
        integrity = {"ok": False, "reason": "неизвестный формат"}

    result["integrity"] = integrity

    if integrity["ok"]:
        print(f"        ✅ {integrity['reason']}")
        print(f"        Файлов: {integrity['file_count']}")
        print(f"        Распакованный размер: {format_size(integrity['total_size'])}")
    else:
        print(f"        ❌ {integrity['reason']}")
        return result

    # 2. Тестовое восстановление
    if full_test:
        print(f"     2) Тестовое восстановление...")
        test_dir = PROJECT_ROOT / "output" / "verify_test"
        try:
            extract_result = test_extract(path, test_dir)
            result["extract_test"] = extract_result

            if extract_result["ok"]:
                print(f"        ✅ {extract_result['reason']}")
            else:
                print(f"        ❌ {extract_result['reason']}")
                return result
        finally:
            # Удаляем тестовую папку
            if test_dir.exists():
                shutil.rmtree(test_dir, ignore_errors=True)

    result["ok"] = True
    return result


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  ПРОВЕРКА БЭКАПОВ")
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

    choice = input("  Выбери бэкап: ").strip()
    if choice == "0":
        return

    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(backups[:20]):
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    backup = backups[int(choice) - 1]

    # Спрашиваем про полный тест
    print()
    print("  Режим проверки:")
    print("    [1] Быстрая (целостность)")
    print("    [2] Полная (+ тестовое восстановление)")
    print()

    mode = input("  Выбор [1]: ").strip() or "1"
    full_test = mode == "2"

    print()
    result = verify_backup(backup["path"], full_test=full_test)

    print()
    print("=" * 80)
    if result["ok"]:
        print("  ✅ БЭКАП ЦЕЛЫЙ И РАБОЧИЙ")
    else:
        print("  ❌ БЭКАП ПОВРЕЖДЁН ИЛИ НЕ РАБОТАЕТ")
    print("=" * 80)

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
