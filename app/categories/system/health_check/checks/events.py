"""
Проверка событий (логов).
Кроссплатформенно: Linux (journalctl) + Windows (Event Log).
"""
import json
from datetime import datetime, timedelta

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-events")


def check_events() -> dict:
    result = {
        "category": "События (логи)",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    if os_detector.is_windows:
        result = _check_windows(result)
    elif os_detector.is_linux:
        result = _check_linux(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"ОС {os_detector.system} не поддерживается")

    return result


def _check_windows(result: dict) -> dict:
    """Event Log на Windows."""
    ps_cmd = (
        "$since = (Get-Date).AddHours(-24); "
        "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=$since} "
        "-MaxEvents 200 -ErrorAction SilentlyContinue | "
        "Group-Object ProviderName | "
        "Sort-Object Count -Descending | "
        "Select-Object -First 10 Name,Count | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip():
        result["details"]["errors_24h"] = 0
        return result

    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]

        total = sum(item.get("Count", 0) for item in data)
        result["details"]["errors_24h"] = total
        result["details"]["top_sources"] = [
            {"source": item.get("Name", "?"), "count": item.get("Count", 0)}
            for item in data[:5]
        ]

        if total > 50:
            result["status"] = "critical"
            result["problems"].append(f"🔴 {total} ошибок в Event Log за 24 часа")
            result["recommendations"].append(
                "Откройте «Просмотр событий» (eventvwr.msc). "
                "Проверьте System-лог."
            )
        elif total > 10:
            result["status"] = "warning"
            result["problems"].append(f"🟡 {total} ошибок в Event Log за 24 часа")

        if total > 0:
            for src in result["details"]["top_sources"][:3]:
                result["problems"].append(
                    f"   • {src['source']}: {src['count']}"
                )
    except Exception as e:
        logger.error(f"Ошибка парсинга Event Log: {e}")

    return result


def _check_linux(result: dict) -> dict:
    """journalctl на Linux."""
    rc, stdout, _ = os_detector.run_command(
        ["journalctl", "--since", "24 hours ago", "-p", "err", "--no-pager"]
    )

    if rc != 0:
        result["details"]["journal_errors"] = "недоступно"
        return result

    lines = [line for line in stdout.splitlines() if line.strip()]
    lines = [line for line in lines if "-- No entries" not in line]

    result["details"]["errors_24h"] = len(lines)

    if len(lines) > 100:
        result["status"] = "critical"
        result["problems"].append(f"🔴 {len(lines)} ошибок в journal за 24 часа")
    elif len(lines) > 20:
        result["status"] = "warning"
        result["problems"].append(f"🟡 {len(lines)} ошибок в journal за 24 часа")

    if lines:
        sources = {}
        for line in lines:
            parts = line.split()
            if len(parts) >= 5:
                svc = parts[4].split("[")[0]
                sources[svc] = sources.get(svc, 0) + 1

        top = sorted(sources.items(), key=lambda x: x[1], reverse=True)[:5]
        result["details"]["top_sources"] = [
            {"source": k, "count": v} for k, v in top
        ]
        for src, cnt in top[:3]:
            result["problems"].append(f"   • {src}: {cnt}")

    return result
