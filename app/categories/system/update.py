"""
Проверка обновлений системы.
Показывает список доступных обновлений.
Работает на Windows и Linux.
"""
import os
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("system-update")


def check_linux_updates() -> dict:
    """Проверяет обновления на Linux (apt)."""
    result = {"count": 0, "packages": [], "error": None}

    # Обновляем список пакетов
    print("  🔄 Обновление списка пакетов...")
    rc, _, err = os_detector.run_command(["sudo", "apt", "update"])
    if rc != 0:
        result["error"] = f"apt update ошибка: {err[:200]}"
        return result

    # Считаем обновления
    print("  🔍 Поиск обновлений...")
    rc, stdout, err = os_detector.run_command(
        ["apt", "list", "--upgradable"]
    )

    if rc != 0:
        result["error"] = f"apt list ошибка: {err[:200]}"
        return result

    for line in stdout.splitlines():
        if "/" in line and "upgradable" not in line.lower():
            pkg = line.split("/")[0]
            result["packages"].append(pkg)

    result["count"] = len(result["packages"])
    return result


def check_windows_updates() -> dict:
    """Проверяет обновления на Windows (PowerShell)."""
    result = {"count": 0, "packages": [], "error": None}

    # Используем Windows Update API через PowerShell
    ps_cmd = (
        "$session = New-Object -ComObject Microsoft.Update.Session; "
        "$searcher = $session.CreateUpdateSearcher(); "
        "$result = $searcher.Search('IsInstalled=0'); "
        "$result.Updates | Select-Object Title | ConvertTo-Json -Compress"
    )

    rc, stdout, err = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0:
        result["error"] = f"PowerShell ошибка: {err[:200]}"
        return result

    import json
    try:
        if stdout.strip():
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                result["packages"].append(item.get("Title", "unknown"))
        result["count"] = len(result["packages"])
    except Exception as e:
        result["error"] = f"Ошибка парсинга: {e}"

    return result


def run():
    """Точка входа."""
    print()
    print("=" * 60)
    print("  ПРОВЕРКА ОБНОВЛЕНИЙ")
    print("=" * 60)
    print()
    print(f"  ОС: {os_detector.system}")
    print()

    print("  ⚠️  Для Linux может потребоваться sudo.")
    print()

    confirm = input("  Продолжить? [y/N]: ").strip().lower()
    if confirm != "y":
        return

    print()

    if os_detector.is_linux:
        result = check_linux_updates()
    elif os_detector.is_windows:
        result = check_windows_updates()
    else:
        print(f"  ❌ ОС {os_detector.system} не поддерживается")
        input("  Нажми Enter для продолжения...")
        return

    print()

    if result["error"]:
        print(f"  ❌ Ошибка: {result['error']}")
    elif result["count"] == 0:
        print("  ✅ Система обновлена. Доступных обновлений нет.")
    else:
        print(f"  📦 Доступно обновлений: {result['count']}")
        print()
        for pkg in result["packages"][:20]:
            print(f"     • {pkg}")
        if result["count"] > 20:
            print(f"     ... и ещё {result['count'] - 20}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
