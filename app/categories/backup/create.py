"""
Создание бэкапа.
Два профиля: "Рабочий компьютер" и "Сервер".
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


def get_dir_size(path: Path) -> int:
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
                except (OSError, FileNotFoundError):
                    pass
    except Exception:
        pass
    return total


def format_size(size: int) -> str:
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


# =====================================================================
# Архивы
# =====================================================================

def create_tar_gz(source: Path, target: Path, exclude: list) -> bool:
    try:
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


def verify_archive(path: Path) -> bool:
    try:
        if path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as tar:
                return len(tar.getmembers()) > 0
        elif path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                return zf.testzip() is None
    except Exception as e:
        logger.error(f"Ошибка проверки {path}: {e}")
    return False


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
            print(f"     🗑️  Удалён старый: {old_file.name}")
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
        "archive": None,
        "size": 0,
        "error": None,
    }

    print(f"  📦 {name}")
    print(f"     Источник: {source_path}")

    if not source_path.exists():
        result["error"] = f"Источник не найден"
        print(f"     ⚠️  Пропуск (не существует)")
        return result

    if source_path.is_dir():
        src_size = get_dir_size(source_path)
    else:
        src_size = source_path.stat().st_size

    print(f"     Размер: {format_size(src_size)}")

    backup_dir = PROJECT_ROOT / config.get("backup_dir", "output/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").replace("/", "_")

    if fmt == "zip":
        archive_name = f"{safe_name}_{timestamp}.zip"
        archive_path = backup_dir / archive_name
        ok = create_zip(source_path, archive_path, exclude)
    else:
        archive_name = f"{safe_name}_{timestamp}.tar.gz"
        archive_path = backup_dir / archive_name
        ok = create_tar_gz(source_path, archive_path, exclude)

    if not ok:
        result["error"] = "Ошибка создания архива"
        print(f"     ❌ {result['error']}")
        return result

    archive_size = archive_path.stat().st_size
    ratio = (1 - archive_size / src_size) * 100 if src_size > 0 else 0

    print(f"     ✅ {archive_name}")
    print(f"     Размер архива: {format_size(archive_size)} (сжатие {ratio:.1f}%)")

    result["ok"] = True
    result["archive"] = str(archive_path)
    result["size"] = archive_size

    if verify:
        if verify_archive(archive_path):
            print(f"     ✅ Архив целый")
            result["verified"] = True
        else:
            print(f"     ❌ Архив повреждён!")
            result["ok"] = False
            result["error"] = "Архив повреждён"
            result["verified"] = False

    if result["ok"]:
        rotate_backups(backup_dir, safe_name, keep_last)

    return result


# =====================================================================
# Бэкап по профилю
# =====================================================================

def backup_profile(profile_key: str, config: dict) -> list:
    """Делает бэкап всех включённых targets профиля."""
    profile = config.get(profile_key, {})
    if not profile:
        print(f"  ❌ Профиль '{profile_key}' не найден в конфиге")
        return []

    targets = [t for t in profile.get("targets", []) if t.get("enabled", True)]

    if not targets:
        print(f"  Нет включённых целей в профиле '{profile['name']}'")
        return []

    print(f"  Профиль: {profile['name']}")
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
    print("    [1] 💻 Рабочий компьютер")
    print("    [2] 🖥️  Сервер")
    print("    [0] ← Назад")
    print()

    choice = input("  Ваш выбор: ").strip()

    if choice == "0":
        return
    elif choice == "1":
        profile_key = "workstation"
    elif choice == "2":
        profile_key = "server"
    else:
        print("  Неверный выбор.")
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
    skip_count = sum(1 for r in results if not r["ok"] and "не существует" in (r.get("error") or ""))
    fail_count = len(results) - ok_count - skip_count
    total_size = sum(r["size"] for r in results)

    for r in results:
        if r["ok"]:
            print(f"  ✅ {r['name']}: {format_size(r['size'])}")
        elif "не существует" in (r.get("error") or ""):
            print(f"  ⚠️  {r['name']}: пропущен (не существует)")
        else:
            print(f"  ❌ {r['name']}: {r['error']}")

    print()
    print(f"  Успешно: {ok_count}/{len(results)} | Пропущено: {skip_count} | Ошибок: {fail_count}")
    print(f"  Всего размер: {format_size(total_size)}")
    print("=" * 70)

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
