"""
Проверка дисков.
Ищет: заполнение > 90%, ошибки, проблемы с SMART (если доступно).
Без дубликатов: одно устройство — одна запись.
"""
import os
import shutil
import string

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-disks")


def check_disks() -> dict:
    """Проверяет диски."""
    result = {
        "category": "Диски",
        "status": "ok",
        "problems": [],
        "details": {"disks": []},
    }

    disks = _get_disks()
    result["details"]["disks"] = disks

    if not disks:
        result["status"] = "warning"
        result["problems"].append("🟡 Не удалось получить информацию о дисках")
        return result

    for d in disks:
        percent = d.get("percent", 0)
        path = d.get("path", "?")

        if percent >= 95:
            result["status"] = "critical"
            result["problems"].append(
                f"🔴 Диск {path} заполнен на {percent}% "
                f"(свободно {d.get('free_gb')} ГБ)"
            )
        elif percent >= 85:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(
                f"🟡 Диск {path} заполнен на {percent}% "
                f"(свободно {d.get('free_gb')} ГБ)"
            )

    # SMART на Linux
    if os_detector.is_linux:
        smart_problems = _check_smart_linux()
        for p in smart_problems:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(p)

    return result


def _get_disks() -> list:
    """Собирает информацию о дисках (без дубликатов)."""
    disks = []
    seen_devices = set()

    if os_detector.is_windows:
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                try:
                    total, used, free = shutil.disk_usage(path)
                    disks.append({
                        "path": path,
                        "total_gb": round(total / 1024**3, 2),
                        "used_gb": round(used / 1024**3, 2),
                        "free_gb": round(free / 1024**3, 2),
                        "percent": round((used / total) * 100, 1) if total > 0 else 0,
                    })
                except Exception:
                    pass
    else:
        for path in ["/", "/home", "/var", "/boot"]:
            if not os.path.exists(path):
                continue
            try:
                st = os.stat(path)
                dev_id = st.st_dev
                if dev_id in seen_devices:
                    continue
                seen_devices.add(dev_id)

                total, used, free = shutil.disk_usage(path)
                disks.append({
                    "path": path,
                    "total_gb": round(total / 1024**3, 2),
                    "used_gb": round(used / 1024**3, 2),
                    "free_gb": round(free / 1024**3, 2),
                    "percent": round((used / total) * 100, 1) if total > 0 else 0,
                })
            except Exception:
                pass

    return disks


def _check_smart_linux() -> list:
    """Проверка SMART на Linux (требует smartctl)."""
    problems = []

    rc, _, _ = os_detector.run_command(["which", "smartctl"])
    if rc != 0:
        return []

    rc, stdout, _ = os_detector.run_command(["lsblk", "-ndo", "NAME"])
    if rc != 0:
        return []

    for disk in stdout.strip().split("\n"):
        if not disk:
            continue
        device = f"/dev/{disk}"

        rc, stdout, _ = os_detector.run_command(
            ["sudo", "smartctl", "-H", device]
        )
        if rc not in (0, 4):
            continue

        if "FAILED" in stdout.upper():
            problems.append(f"🔴 SMART диска {device}: FAILED (диск умирает)")
        elif "PASSED" not in stdout.upper():
            problems.append(f"🟡 SMART диска {device}: неизвестный статус")

    return problems
