"""
Проверка памяти (RAM, swap).
Кроссплатформенно: Linux (/proc/meminfo) + Windows (WMI).
"""
import os
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-memory")


def check_memory() -> dict:
    result = {
        "category": "Память (RAM)",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    if os_detector.is_windows:
        result["details"] = _check_windows()
    elif os_detector.is_linux:
        result["details"] = _check_linux()
    else:
        result["status"] = "warning"
        result["problems"].append(f"ОС {os_detector.system} не поддерживается")
        return result

    percent = result["details"].get("percent")
    if percent is not None:
        if percent >= 95:
            result["status"] = "critical"
            result["problems"].append(f"🔴 Критическое использование RAM: {percent}%")
            result["recommendations"].append("Закройте лишние программы.")
        elif percent >= 85:
            result["status"] = "warning"
            result["problems"].append(f"🟡 Высокое использование RAM: {percent}%")
            result["recommendations"].append("Рекомендуется закрыть неиспользуемые программы.")

    swap_percent = result["details"].get("swap_percent")
    if swap_percent is not None and swap_percent >= 50:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append(f"🟡 Активно используется swap: {swap_percent}%")

    return result


def _check_linux() -> dict:
    details = {
        "total_gb": None, "used_gb": None, "percent": None,
        "swap_total_gb": None, "swap_used_gb": None, "swap_percent": None,
    }
    try:
        with open("/proc/meminfo", "r") as f:
            mem = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    try:
                        mem[key] = int(val)
                    except ValueError:
                        pass

            total_kb = mem.get("MemTotal", 0)
            available_kb = mem.get("MemAvailable", 0)
            used_kb = total_kb - available_kb

            details["total_gb"] = round(total_kb / 1024 / 1024, 2)
            details["used_gb"] = round(used_kb / 1024 / 1024, 2)
            if total_kb > 0:
                details["percent"] = round((used_kb / total_kb) * 100, 1)

            swap_total_kb = mem.get("SwapTotal", 0)
            swap_free_kb = mem.get("SwapFree", 0)
            swap_used_kb = swap_total_kb - swap_free_kb

            details["swap_total_gb"] = round(swap_total_kb / 1024 / 1024, 2)
            details["swap_used_gb"] = round(swap_used_kb / 1024 / 1024, 2)
            if swap_total_kb > 0:
                details["swap_percent"] = round((swap_used_kb / swap_total_kb) * 100, 1)
    except Exception as e:
        logger.error(f"Ошибка чтения /proc/meminfo: {e}")
    return details


def _check_windows() -> dict:
    """RAM на Windows через PowerShell."""
    details = {
        "total_gb": None, "used_gb": None, "percent": None,
        "swap_total_gb": None, "swap_used_gb": None, "swap_percent": None,
    }

    ps_cmd = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "$total = [int]$os.TotalVisibleMemorySize; "
        "$free = [int]$os.FreePhysicalMemory; "
        "$swapTotal = [int]$os.TotalVirtualMemorySize; "
        "$swapFree = [int]$os.FreeVirtualMemory; "
        "Write-Output \"$total|$free|$swapTotal|$swapFree\""
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip():
        return details

    try:
        parts = stdout.strip().split("|")
        if len(parts) != 4:
            return details
        total_kb = int(parts[0])
        free_kb = int(parts[1])
        swap_total_kb = int(parts[2])
        swap_free_kb = int(parts[3])

        used_kb = total_kb - free_kb
        swap_used_kb = swap_total_kb - swap_free_kb

        details["total_gb"] = round(total_kb / 1024 / 1024, 2)
        details["used_gb"] = round(used_kb / 1024 / 1024, 2)
        if total_kb > 0:
            details["percent"] = round((used_kb / total_kb) * 100, 1)

        details["swap_total_gb"] = round(swap_total_kb / 1024 / 1024, 2)
        details["swap_used_gb"] = round(swap_used_kb / 1024 / 1024, 2)
        if swap_total_kb > 0:
            details["swap_percent"] = round((swap_used_kb / swap_total_kb) * 100, 1)
    except Exception as e:
        logger.error(f"Ошибка парсинга RAM (Windows): {e}")

    return details
