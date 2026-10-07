"""
Создание бэкапа.
- Файлы и папки (tar.gz / zip)
- Исключения (по маскам)
- Проверка целостности
- Ротация (keep_last)
"""
import os
import tarfile
import zipfile
import yaml
import shutil
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
    """Загружает config/backup.yaml."""
    if not BACKUP_CONFIG.exists():
        logger.error(f"Конфиг не найден: {BACKUP_CONFIG}")
        return {}

    with open(BACKUP_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# =====================================================================
# Вспомогательные функции
# =====================================================================

def expand_path(path: str) -> Path:
    """Раскрывает ~ и переменные окружения."""
    return Path(os.path.expanduser(os.path.expandvars(path))).resolve()


def should_exclude(file_path: Path, exclude_patterns: list) -> bool:
    """Проверяет, нужно ли исключить файл."""
    path_str = str(file_path).lower()
    name = file_path.name.lower()

    for pattern in exclude_patterns:
        pattern = pattern.lower()
        # Простая проверка: вхождение или fnmatch
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif pattern in path_str or pattern == name:
            return True

    return False


def get_dir_size(path: Path) -> int:
    """Размер папки в байтах."""
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
    """Человекочитаемый размер."""
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


# =====================================================================
# Создание архива
# =====================================================================

def create_tar_gz(source: Path, target: Path, exclude: list) -> bool:
    """Создаёт tar.gz архив с исключениями."""
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
                    except Exception as e:
                        logger.debug(f"Пропуск {item}: {e}")
        return True
    except Exception as e:
        logger.error(f"Ошибка tar.gz: {e}")
        return False


def create_zip(source: Path, target: Path, exclude: list) -> bool:
    """Создаёт zip архив с исключениями."""
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
                            arcname = item.relative_to(source.parent)
                            zf.write(item, arcname)
                        except Exception as e:
                            logger.debug(f"Пропуск {item}: {e}")
        return True
    except Exception as e:
        logger.error(f"Ошибка zip: {e}")
        return False


# =====================================================================
# Проверка целостности
# =====================================================================

def verify_archive(path: Path) -> bool:
    """Проверяет целостность архива."""
    try:
        if path.suffix == ".gz" or path.name.endswith(".tar.gz"):
            with tarfile.open(path, "r:gz") as tar:
                # Пробуем прочитать список файлов
                members = tar.getmembers()
                return len(members) > 0
        elif path.suffix == ".zip":
            with zipfile.ZipFile(path, "r") as zf:
                # Проверяем целостность
                bad = zf.testzip()
                return bad is None
    except Exception as e:
        logger.error(f"Ошибка проверки {path}: {e}")
        return False
    return False


# =====================================================================
# Ротация (удаление старых)
# =====================================================================

def rotate_backups(backup_dir: Path, target_name: str, keep_last: int):
    """Удаляет старые бэкапы, оставляя keep_last последних."""
    if keep_last <= 0:
        return

    # Ищем бэкапы этого target
    pattern = f"{target_name}_*.tar.gz"
    pattern_zip = f"{target_name}_*.zip"

    files = sorted(
        list(backup_dir.glob(pattern)) + list(backup_dir.glob(pattern_zip)),
        reverse=True
    )

    # Удаляем лишние
    for old_file in files[keep_last:]:
        try:
            old_file.unlink()
            logger.info(f"Удалён старый бэкап: {old_file.name}")
            print(f"     🗑️  Удалён старый: {old_file.name}")
        except Exception as e:
            logger.error(f"Ошибка удаления {old_file}: {e}")


# =====================================================================
# Основная функция
# =====================================================================

def backup_target(target: dict, config: dict) -> dict:
    """Делает бэкап одного target."""
    name = target.get("name", "unknown")
    source_path = expand_path(target.get("path", ""))
    exclude = config.get("exclude", [])
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

    print(f"  📦 Бэкап: {name}")
    print(f"     Источник: {source_path}")

    # Проверяем источник
    if not source_path.exists():
        result["error"] = f"Источник не найден: {source_path}"
        print(f"     ❌ {result['error']}")
        return result

    # Размер источника
    if source_path.is_dir():
        src_size = get_dir_size(source_path)
    else:
        src_size = source_path.stat().st_size
    print(f"     Размер источника: {format_size(src_size)}")

    # Папка для бэкапов
    backup_dir = PROJECT_ROOT / config.get("backup_dir", "output/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Имя архива
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_name = name.replace(" ", "_").replace("/", "_")

    if fmt == "zip":
        archive_name = f"{safe_name}_{timestamp}.zip"
        archive_path = backup_dir / archive_name
        print(f"     Создание ZIP...")
        ok = create_zip(source_path, archive_path, exclude)
    else:
        archive_name = f"{safe_name}_{timestamp}.tar.gz"
        archive_path = backup_dir / archive_name
        print(f"     Создание TAR.GZ...")
        ok = create_tar_gz(source_path, archive_path, exclude)

    if not ok:
        result["error"] = "Ошибка создания архива"
        print(f"     ❌ {result['error']}")
        return result

    # Размер архива
    archive_size = archive_path.stat().st_size
    compression_ratio = (1 - archive_size / src_size) * 100 if src_size > 0 else 0

    print(f"     ✅ Архив: {archive_name}")
    print(f"     Размер архива: {format_size(archive_size)}")
    print(f"     Сжатие: {compression_ratio:.1f}%")

    result["ok"] = True
    result["archive"] = str(archive_path)
    result["size"] = archive_size
    result["compression_ratio"] = compression_ratio

    # Проверка целостности
    if verify:
        print(f"     Проверка целостности...")
        if verify_archive(archive_path):
            print(f"     ✅ Архив целый")
            result["verified"] = True
        else:
            print(f"     ❌ Архив повреждён!")
            result["ok"] = False
            result["error"] = "Архив повреждён"
            result["verified"] = False

    # Ротация
    if result["ok"]:
        rotate_backups(backup_dir, safe_name, keep_last)

    return result


def run():
    """Точка входа."""
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

    targets = [t for t in config.get("targets", []) if t.get("enabled", True)]

    if not targets:
        print("  Нет включённых целей для бэкапа.")
        print("  Проверь config/backup.yaml (поле enabled)")
        print()
        input("  Нажми Enter...")
        return

    print(f"  Целей для бэкапа: {len(targets)}")
    print(f"  Формат: {config.get('format', 'tar.gz')}")
    print(f"  Папка: {config.get('backup_dir', 'output/backups')}")
    print()

    confirm = input("  Начать? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print()

    results = []
    for target in targets:
        result = backup_target(target, config)
        results.append(result)
        print()

    # Итог
    print("=" * 70)
    print("  ИТОГ")
    print("=" * 70)

    ok_count = sum(1 for r in results if r["ok"])
    total_size = sum(r["size"] for r in results)

    for r in results:
        icon = "✅" if r["ok"] else "❌"
        print(f"  {icon} {r['name']}: {format_size(r['size']) if r['ok'] else r['error']}")

    print()
    print(f"  Успешно: {ok_count}/{len(results)}")
    print(f"  Всего: {format_size(total_size)}")
    print("=" * 70)

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
