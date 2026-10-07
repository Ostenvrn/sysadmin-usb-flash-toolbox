"""
Создание бэкапа.
- Автосканирование файлов перед бэкапом
- Проверка безопасности (права, симлинки)
- Проверка целостности архива
"""
import os
import tarfile
import zipfile
import yaml
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("backup-create")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
BACKUP_CONFIG = PROJECT_ROOT / "config" / "backup.yaml"


# =====================================================================
# Загрузка конфига
# =====================================================================

def load_backup_config() -> dict:
    if not BACKUP_CONFIG.exists():
        logger.error(f"Конфиг не найден: {BACKUP_CONFIG}")
        return {}
    with open(BACKUP_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# =====================================================================
# Вспомогательные
# =====================================================================

def expand_path(path: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(path))).resolve()


def is_root() -> bool:
    return os.geteuid() == 0 if hasattr(os, "geteuid") else False


def should_exclude(file_path: Path, exclude_patterns: list) -> bool:
    path_str = str(file_path).lower()
    name = file_path.name.lower()
    for pattern in exclude_patterns:
        pattern = pattern.lower()
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif pattern in path_str or pattern == name:
            return True
    return False


def format_size(size: int) -> str:
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


# =====================================================================
# АВТОСКАНИРОВАНИЕ
# =====================================================================

def scan_path(path: Path, exclude: list) -> dict:
    """
    Сканирует папку перед бэкапом.
    Возвращает статистику: файлы, папки, размер, проблемные.
    """
    stats = {
        "files": 0,
        "dirs": 0,
        "size": 0,
        "symlinks": 0,
        "no_read_access": 0,
        "large_files": [],   # файлы > 1 ГБ
        "errors": [],
    }

    try:
        for item in path.rglob("*"):
            if should_exclude(item, exclude):
                continue

            try:
                if item.is_symlink():
                    stats["symlinks"] += 1
                elif item.is_dir():
                    stats["dirs"] += 1
                elif item.is_file():
                    stats["files"] += 1
                    try:
                        size = item.stat().st_size
                        stats["size"] += size
                        if size > 1024**3:  # > 1 ГБ
                            stats["large_files"].append((str(item), size))
                    except OSError:
                        stats["no_read_access"] += 1
                else:
                    stats["files"] += 1
            except OSError as e:
                stats["errors"].append(f"{item}: {e}")
    except Exception as e:
        stats["errors"].append(f"Ошибка сканирования: {e}")

    return stats


def print_scan_results(name: str, stats: dict):
    """Выводит результаты сканирования."""
    print(f"     📊 Сканирование:")
    print(f"        Файлов:    {stats['files']}")
    print(f"        Папок:     {stats['dirs']}")
    print(f"        Размер:    {format_size(stats['size'])}")

    if stats["symlinks"]:
        print(f"        Симлинков: {stats['symlinks']}")

    if stats["no_read_access"]:
        print(f"        ⚠️  Нет доступа: {stats['no_read_access']}")

    if stats["large_files"]:
        print(f"        ⚠️  Больших файлов (>1 ГБ): {len(stats['large_files'])}")
        for f, size in stats["large_files"][:3]:
            print(f"           • {Path(f).name}: {format_size(size)}")

    if stats["errors"]:
        print(f"        ⚠️  Ошибок: {len(stats['errors'])}")
        for err in stats["errors"][:3]:
            print(f"           • {err}")


# =====================================================================
# ПРОВЕРКИ БЕЗОПАСНОСТИ
# =====================================================================

def check_security(path: Path) -> list:
    """
    Проверяет безопасность пути.
    Возвращает список предупреждений.
    """
    warnings = []

    # 1. Проверка на симлинки, ведущие наружу
    try:
        for item in path.rglob("*"):
            if item.is_symlink():
                try:
                    target = item.resolve()
                    if not str(target).startswith(str(path)):
                        warnings.append(
                            f"Симлинк ведёт наружу: {item.name} → {target}"
                        )
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Проверка на файлы с паролями
    sensitive_names = [
        ".env", "credentials", "secrets", "password", "passwd",
        "id_rsa", "id_ed25519", ".pgpass", ".netrc",
    ]
    sensitive_found = []
    try:
        for item in path.rglob("*"):
            if item.is_file():
                name_lower = item.name.lower()
                for sens in sensitive_names:
                    if sens in name_lower:
                        sensitive_found.append(str(item))
                        break
    except Exception:
        pass

    if sensitive_found:
        warnings.append(
            f"Найдено {len(sensitive_found)} файлов с секретами. "
            f"Убедись, что архив будет храниться безопасно."
        )

    return warnings


# =====================================================================
# Архивы
# =====================================================================

def create_tar_gz(source: Path, target: Path, exclude: list,
                  progress_callback=None) -> bool:
    try:
        file_count = 0
        with tarfile.open(target, "w:gz") as tar:
            if source.is_file():
                tar.add(source, arcname=source.name)
            else:
                for item in source.rglob("*"):
                    if should_exclude(item, exclude):
                        continue
                    try:
                        arcname = item.relative_to(source.parent)
                        tar.add(item, arcname=arcname, recursive=False)
                        file_count += 1
                        if progress_callback and file_count % 1000 == 0:
                            progress_callback(file_count)
                    except Exception:
                        pass
        return True
    except Exception as e:
        logger.error(f"Ошибка tar.gz: {e}")
        return False


def create_zip(source: Path, target: Path, exclude: list) -> bool:
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            if source.is_file():
                zf.write(source, source.name)
            else:
                for item in source.rglob("*"):
                    if should_exclude(item, exclude):
                        continue
                    if item.is_file():
                        try:
                            zf.write(item, item.relative_to(source.parent))
                        except Exception:
                            pass
        return True
    except Exception as e:
        logger.error(f"Ошибка zip: {e}")
        return False


# =====================================================================
# ПРОВЕРКА ЦЕЛОСТНОСТИ
# =====================================================================

def verify_archive(path: Path) -> dict:
    """
    Проверяет целостность архива.
    Возвращает: {ok, reason, file_count}
    """
    result = {"ok": False, "reason": "", "file_count": 0}

    try:
        if path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as tar:
                # 1. Проверяем, что архив читается
                members = tar.getmembers()
                result["file_count"] = len(members)

                if not members:
                    result["reason"] = "архив пустой"
                    return result

                # 2. Проверяем случайные файлы (не все — долго)
                import random
                sample = random.sample(members, min(10, len(members)))
                for member in sample:
                    if member.isfile():
                        try:
                            f = tar.extractfile(member)
                            if f:
                                f.read(1024)  # читаем первые 1 КБ
                        except Exception as e:
                            result["reason"] = f"повреждён файл {member.name}: {e}"
                            return result

                result["ok"] = True
                result["reason"] = f"проверено {len(sample)} файлов из {len(members)}"

        elif path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                bad = zf.testzip()
                if bad:
                    result["reason"] = f"повреждён файл: {bad}"
                    return result
                result["file_count"] = len(zf.namelist())
                result["ok"] = True
                result["reason"] = f"все {result['file_count']} файлов целые"
        else:
            result["reason"] = "неизвестный формат"
    except Exception as e:
        result["reason"] = f"ошибка проверки: {e}"

    return result


def rotate_backups(backup_dir: Path, target_name: str, keep_last: int):
    if keep_last <= 0:
        return
    files = sorted(
        list(backup_dir.glob(f"{target_name}_*.tar.gz")) +
        list(backup_dir.glob(f"{target_name}_*.zip")),
        reverse=True
    )
    for old_file in files[keep_last:]:
        try:
            old_file.unlink()
            logger.info(f"Удалён старый бэкап: {old_file.name}")
            print(f"     🗑️  Удалён: {old_file.name}")
        except Exception as e:
            logger.error(f"Ошибка удаления {old_file}: {e}")


# =====================================================================
# Бэкап одного target
# =====================================================================

def backup_target(target: dict, config: dict, profile: dict) -> dict:
    name = target.get("name", "unknown")
    source_path = expand_path(target.get("path", ""))
    exclude = profile.get("exclude", [])
    fmt = config.get("format", "tar.gz")
    keep_last = config.get("keep_last", 5)
    verify = config.get("verify_after_create", True)

    result = {
        "name": name,
        "source": str(source_path),
        "ok": False,
        "skipped": False,
        "archive": None,
        "size": 0,
        "error": None,
        "scan_stats": None,
        "security_warnings": [],
        "verify_result": None,
    }

    print(f"  📦 {name}")
    print(f"     Источник: {source_path}")

    if not source_path.exists():
        result["error"] = "не существует"
        result["skipped"] = True
        print(f"     ⚠️  Пропуск (не существует)")
        return result

    # === АВТОСКАНИРОВАНИЕ ===
    if source_path.is_dir():
        print(f"     📊 Сканирование...")
        stats = scan_path(source_path, exclude)
        result["scan_stats"] = stats
        print_scan_results(name, stats)

        if stats["files"] == 0:
            result["error"] = "нет файлов для бэкапа"
            print(f"     ⚠️  Пропуск (нет файлов)")
            return result

        src_size = stats["size"]
    else:
        src_size = source_path.stat().st_size
        print(f"     Размер: {format_size(src_size)}")

    # === ПРОВЕРКА БЕЗОПАСНОСТИ ===
    if source_path.is_dir():
        print(f"     🔒 Проверка безопасности...")
        sec_warnings = check_security(source_path)
        result["security_warnings"] = sec_warnings

        if sec_warnings:
            for w in sec_warnings:
                print(f"        ⚠️  {w}")
        else:
            print(f"        ✅ Проблем не найдено")

    # === СОЗДАНИЕ АРХИВА ===
    backup_dir = PROJECT_ROOT / config.get("backup_dir", "output/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")

    print(f"     📦 Создание архива...")

    def progress_cb(count):
        print(f"        ...{count} файлов")

    if fmt == "zip":
        archive_name = f"{safe_name}_{timestamp}.zip"
        archive_path = backup_dir / archive_name
        ok = create_zip(source_path, archive_path, exclude)
    else:
        archive_name = f"{safe_name}_{timestamp}.tar.gz"
        archive_path = backup_dir / archive_name
        ok = create_tar_gz(source_path, archive_path, exclude,
                           progress_callback=progress_cb)

    if not ok:
        result["error"] = "ошибка создания архива"
        print(f"     ❌ {result['error']}")
        return result

    archive_size = archive_path.stat().st_size
    ratio = (1 - archive_size / src_size) * 100 if src_size > 0 else 0

    print(f"     ✅ {archive_name}")
    print(f"     Размер архива: {format_size(archive_size)} (сжатие {ratio:.1f}%)")

    result["ok"] = True
    result["archive"] = str(archive_path)
    result["size"] = archive_size

    # === ПРОВЕРКА ЦЕЛОСТНОСТИ ===
    if verify:
        print(f"     🔍 Проверка целостности...")
        verify_result = verify_archive(archive_path)
        result["verify_result"] = verify_result

        if verify_result["ok"]:
            print(f"        ✅ {verify_result['reason']}")
            result["verified"] = True
        else:
            print(f"        ❌ {verify_result['reason']}")
            result["ok"] = False
            result["error"] = f"архив повреждён: {verify_result['reason']}"
            result["verified"] = False

    if result["ok"]:
        rotate_backups(backup_dir, safe_name, keep_last)

    return result


# =====================================================================
# Бэкап по профилю
# =====================================================================

def backup_profile(profile_key: str, config: dict) -> list:
    profile = config.get(profile_key, {})
    if not profile:
        print(f"  ❌ Профиль '{profile_key}' не найден")
        return []

    targets = [t for t in profile.get("targets", []) if t.get("enabled", True)]

    if not targets:
        print(f"  Нет включённых целей в профиле")
        return []

    print(f"  Профиль: {profile.get('name', profile_key)}")
    if profile.get("description"):
        print(f"  Описание: {profile['description']}")
    print(f"  Целей: {len(targets)}")
    print()

    results = []
    for target in targets:
        result = backup_target(target, config, profile)
        results.append(result)
        print()

    return results


# =====================================================================
# Точка входа
# =====================================================================

def run():
    print()
    print("=" * 70)
    print("  СОЗДАНИЕ БЭКАПА")
    print("=" * 70)
    print()

    config = load_backup_config()
    if not config:
        print("  ❌ Не удалось загрузить config/backup.yaml")
        input("  Нажми Enter...")
        return

    # Выбор профиля
    print("  Выбери профиль:")
    print("    [1] 💻 Рабочий компьютер (данные)")
    print("    [2] 🏠 Полный бэкап домашней папки (~)")
    print("    [3] 🖥️  Система (требует root)")
    print("    [4] 🖥️  Сервер (требует root)")
    print("    [0] ← Назад")
    print()

    choice = input("  Ваш выбор: ").strip()

    profiles = {
        "1": "workstation",
        "2": "full_home",
        "3": "system",
        "4": "server",
    }

    if choice == "0":
        return
    if choice not in profiles:
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    profile_key = profiles[choice]
    profile = config.get(profile_key, {})

    # Проверка root
    if profile.get("requires_root") and not is_root():
        print()
        print("  ⚠️  Этот профиль требует прав root!")
        print("  Запусти: sudo ./start.sh")
        print()
        input("  Нажми Enter...")
        return

    print()
    confirm = input("  Начать бэкап? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print()

    results = backup_profile(profile_key, config)

    if not results:
        input("  Нажми Enter для продолжения...")
        return

    # Итог
    print("=" * 70)
    print("  ИТОГ")
    print("=" * 70)

    ok_count = sum(1 for r in results if r["ok"])
    skip_count = sum(1 for r in results if r.get("skipped"))
    fail_count = len(results) - ok_count - skip_count
    total_size = sum(r["size"] for r in results)
    warnings_count = sum(len(r.get("security_warnings", [])) for r in results)

    for r in results:
        if r["ok"]:
            print(f"  ✅ {r['name']}: {format_size(r['size'])}")
        elif r.get("skipped"):
            print(f"  ⚠️  {r['name']}: пропущен")
        else:
            print(f"  ❌ {r['name']}: {r['error']}")

    print()
    print(f"  Успешно: {ok_count}/{len(results)} | Пропущено: {skip_count} | Ошибок: {fail_count}")
    print(f"  Всего: {format_size(total_size)}")
    if warnings_count:
        print(f"  ⚠️  Предупреждений безопасности: {warnings_count}")
    print("=" * 70)

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
