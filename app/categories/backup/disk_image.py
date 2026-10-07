"""
ПОЛНЫЙ БЭКАП ДИСКА (ОБРАЗ).
⚠️ ОПАСНАЯ ОПЕРАЦИЯ! Требует root и внешний диск.
⚠️ Может занять часы и создать образ на сотни гигабайт.
"""
import os
import subprocess
import shutil
import json
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("backup-disk-image")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


# =====================================================================
# Вспомогательные
# =====================================================================

def is_root() -> bool:
    return os.geteuid() == 0 if hasattr(os, "geteuid") else False


def get_disks() -> list:
    """Возвращает список дисков (lsblk -J)."""
    try:
        rc, stdout, _ = os_detector.run_command(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL"]
        )
        if rc != 0:
            return []

        data = json.loads(stdout)
        disks = []

        for dev in data.get("blockdevices", []):
            if dev.get("type") == "disk":
                disks.append({
                    "name": dev.get("name"),
                    "path": f"/dev/{dev.get('name')}",
                    "size": dev.get("size", "?"),
                    "model": dev.get("model") or "unknown",
                    "mountpoint": dev.get("mountpoint"),
                })
        return disks
    except Exception as e:
        logger.error(f"Ошибка определения дисков: {e}")
        return []


def get_free_space(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except Exception:
        return 0


def format_size(size: int) -> str:
    for unit in ["Б", "КБ", "МБ", "ГБ", "ТБ"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ПБ"


def parse_size_to_bytes(size_str: str) -> int:
    """Парсит '465.8G' в байты."""
    size_str = size_str.strip().upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return int(float(size_str[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(size_str)
    except ValueError:
        return 0


def is_mounted(disk_path: str) -> bool:
    """Проверяет, смонтирован ли диск (бэкапить смонтированный системный диск — плохо)."""
    try:
        rc, stdout, _ = os_detector.run_command(["mount"])
        if rc == 0:
            return disk_path in stdout
    except Exception:
        pass
    return False


# =====================================================================
# Создание образа
# =====================================================================

def create_disk_image(disk_path: str, output_path: Path) -> bool:
    """Создаёт сжатый образ через dd | gzip."""
    try:
        cmd = (
            f"dd if={disk_path} bs=4M status=progress | "
            f"gzip > {output_path}"
        )

        process = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in process.stdout:
            print(f"  {line.rstrip()}")

        process.wait()

        if process.returncode == 0:
            size = output_path.stat().st_size
            print()
            print(f"  ✅ Образ создан: {format_size(size)}")
            return True
        else:
            print(f"  ❌ Ошибка dd (код {process.returncode})")
            return False
    except Exception as e:
        logger.error(f"Ошибка dd: {e}")
        print(f"  ❌ {e}")
        return False


# =====================================================================
# Меню с предупреждениями
# =====================================================================

def show_warning_banner():
    """Показывает красный баннер предупреждения."""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  🔴🔴🔴  ВНИМАНИЕ! ОПАСНАЯ ОПЕРАЦИЯ!  🔴🔴🔴".center(60) + "  ║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    print("  ⚠️  Это ПОЛНЫЙ ОБРАЗ ДИСКА (побитовая копия).")
    print()
    print("  ЧТО ПРОИЗОЙДЁТ:")
    print("     • Будет скопирован ВЕСЬ диск сектор за сектором")
    print("     • Размер образа ~ размеру диска (сжатие 30-50%)")
    print("     • Время: от 1 до 5 ЧАСОВ (зависит от объёма)")
    print()
    print("  🔴 КРИТИЧНО ВАЖНО:")
    print("     • Образ НЕЛЬЗЯ сохранять на тот же диск, что бэкапите!")
    print("     • Нужен ВНЕШНИЙ диск (USB-HDD, сетевое хранилище)")
    print("     • Свободного места нужно БОЛЬШЕ, чем размер диска")
    print("     • Требуются права root (sudo)")
    print()
    print("  ⚠️  Если что-то пойдёт не так — система может стать")
    print("     неработоспособной. НЕ выключайте ПК во время процесса.")
    print()
    print("=" * 70)
    print()


def run():
    """Точка входа."""
    print()
    print("=" * 70)
    print("  💿 ПОЛНЫЙ БЭКАП ДИСКА (ОБРАЗ)")
    print("=" * 70)

    show_warning_banner()

    # Проверка root
    if not is_root():
        print("  🔴 Требуются права root!")
        print("  Запусти: sudo ./start.sh")
        print()
        input("  Нажми Enter...")
        return

    # Явное согласие
    print("  Введи 'Я ПОНИМАЮ РИСКИ' заглавными буквами для продолжения:")
    confirm = input("  > ").strip()

    if confirm != "Я ПОНИМАЮ РИСКИ":
        print()
        print("  ❌ Отмена. Введено: " + repr(confirm))
        print()
        input("  Нажми Enter...")
        return

    print()
    print("  ✅ Согласие получено. Продолжаем.")
    print()

    # Список дисков
    disks = get_disks()
    if not disks:
        print("  ❌ Не удалось определить диски")
        input("  Нажми Enter...")
        return

    print("  Доступные диски:")
    print()
    for i, d in enumerate(disks, start=1):
        mounted = "🔴 СМОНТИРОВАН" if is_mounted(d["path"]) else "✅ не смонтирован"
        print(f"    [{i}] {d['path']:<12} {d['size']:<10} {d['model'][:30]:<30} {mounted}")

    print("    [0] ← Назад")
    print()

    choice = input("  Выбери диск для бэкапа: ").strip()
    if choice == "0":
        return

    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(disks):
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    disk = disks[int(choice) - 1]

    # Предупреждение про смонтированный диск
    if is_mounted(disk["path"]):
        print()
        print(f"  🔴 ВНИМАНИЕ! Диск {disk['path']} СМОНТИРОВАН!")
        print("     Бэкапить смонтированный системный диск можно,")
        print("     но образ может быть несогласованным.")
        print("     Лучше загрузиться с Live-USB и сделать образ оттуда.")
        print()
        cont = input("  Продолжить? [y/N]: ").strip().lower()
        if cont != "y":
            return

    print()
    print(f"  Выбран диск: {disk['path']} ({disk['size']})")
    print()

    # Куда сохранять
    print("  🔴 Куда сохранить образ?")
    print("     Это должен быть ВНЕШНИЙ диск!")
    print()
    output_dir = input("  Папка (например, /media/usb): ").strip()

    if not output_dir or not os.path.isdir(output_dir):
        print("  ❌ Папка не найдена.")
        input("  Нажми Enter...")
        return

    # Проверка: не тот же ли диск
    if output_dir.startswith("/home") or output_dir.startswith("/root"):
        print()
        print("  🔴 ВНИМАНИЕ! Папка находится на системном диске.")
        print("     Если ты бэкапишь системный диск — образ НЕЛЬЗЯ")
        print("     сохранять на него же!")
        print()
        cont = input("  Продолжить? [y/N]: ").strip().lower()
        if cont != "y":
            return

    # Проверка свободного места
    free = get_free_space(output_dir)
    disk_size_bytes = parse_size_to_bytes(disk["size"])
    estimated_image_size = disk_size_bytes * 0.6  # ~60% от размера диска

    print()
    print(f"  Свободно на диске: {format_size(free)}")
    print(f"  Размер диска:      {disk['size']} ({format_size(disk_size_bytes)})")
    print(f"  Ожидаемый образ:   ~{format_size(int(estimated_image_size))}")
    print()

    if free < estimated_image_size:
        print("  🔴 НЕДОСТАТОЧНО МЕСТА!")
        print(f"     Нужно минимум {format_size(int(estimated_image_size))},")
        print(f"     а свободно только {format_size(free)}.")
        print()
        input("  Нажми Enter...")
        return

    # Финальное подтверждение
    print("=" * 70)
    print("  🔴 ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ")
    print("=" * 70)
    print()
    print(f"  Диск:      {disk['path']}")
    print(f"  Размер:    {disk['size']}")
    print(f"  Сохранить: {output_dir}")
    print(f"  Время:     от 1 до 5 часов")
    print()
    print("  Введи 'ЗАПУСКАЙ' заглавными буквами:")
    final = input("  > ").strip()

    if final != "ЗАПУСКАЙ":
        print("  ❌ Отмена.")
        input("  Нажми Enter...")
        return

    # Создание образа
    print()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    disk_name = disk["name"]
    output_path = Path(output_dir) / f"disk_{disk_name}_{timestamp}.img.gz"

    print(f"  💿 Создание образа: {disk['path']}")
    print(f"  💾 Вывод: {output_path}")
    print()

    success = create_disk_image(disk["path"], output_path)

    if success:
        print()
        print(f"  ✅ Образ: {output_path}")
        print()
        print("  📌 Для восстановления:")
        print(f"     sudo gunzip -c {output_path} | sudo dd of={disk['path']} bs=4M")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
