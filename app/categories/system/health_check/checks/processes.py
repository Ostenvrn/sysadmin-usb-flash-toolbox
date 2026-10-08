"""
Проверка процессов.
Кроссплатформенно: Linux (ps aux) + Windows (tasklist + WMI).
"""
import json

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-processes")


def check_processes() -> dict:
    result = {
        "category": "Процессы",
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
    """Топ процессов на Windows через PowerShell."""
    ps_cmd = (
        "Get-Process | Sort-Object CPU -Descending | "
        "Select-Object -First 10 Name,Id,CPU,WS | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip():
        return result

    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]

        result["details"]["top_processes"] = len(data)

        top_list = []
        for p in data[:10]:
            name = p.get("Name", "?")
            pid = p.get("Id", 0)
            cpu = p.get("CPU", 0) or 0
            mem_mb = round((p.get("WS", 0) or 0) / 1024 / 1024, 1)

            top_list.append({
                "name": name,
                "pid": pid,
                "cpu": round(cpu, 1),
                "mem_mb": mem_mb,
            })

            if cpu >= 50:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 {name} (PID {pid}): CPU {cpu:.1f}%"
                )

        result["details"]["top_by_cpu"] = top_list

        if any(p.get("cpu", 0) >= 50 for p in top_list):
            result["recommendations"].append(
                "Высокая нагрузка CPU. Проверьте процессы в диспетчере задач."
            )
    except Exception as e:
        logger.error(f"Ошибка парсинга процессов: {e}")

    return result


def _check_linux(result: dict) -> dict:
    """Процессы на Linux через ps aux."""
    rc, stdout, _ = os_detector.run_command(["ps", "aux", "--no-headers"])
    if rc != 0:
        return result

    zombies = []
    high_cpu = []
    high_mem = []
    total = 0

    for line in stdout.splitlines():
        total += 1
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue

        user, pid, cpu, mem, vsz, rss, tty, stat, start, time, cmd = parts

        if "Z" in stat:
            zombies.append({"pid": pid, "cmd": cmd[:60]})

        try:
            cpu_f = float(cpu)
            if cpu_f >= 50:
                high_cpu.append({"pid": pid, "cpu": cpu_f, "cmd": cmd[:60]})
        except ValueError:
            pass

        try:
            mem_f = float(mem)
            if mem_f >= 20:
                high_mem.append({"pid": pid, "mem": mem_f, "cmd": cmd[:60]})
        except ValueError:
            pass

    result["details"]["total_processes"] = total
    result["details"]["zombies"] = len(zombies)
    result["details"]["high_cpu"] = len(high_cpu)
    result["details"]["high_mem"] = len(high_mem)

    if zombies:
        result["status"] = "warning"
        result["problems"].append(f"🟡 Зомби-процессов: {len(zombies)}")
        for z in zombies[:3]:
            result["problems"].append(f"   • PID {z['pid']}: {z['cmd']}")
        result["recommendations"].append(
            "Зомби-процессы: проверьте родительские процессы."
        )

    if high_cpu:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append(f"🟡 Процессов с CPU ≥ 50%: {len(high_cpu)}")
        for p in high_cpu[:3]:
            result["problems"].append(f"   • PID {p['pid']}: {p['cpu']}% — {p['cmd']}")

    if high_mem:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append(f"🟡 Процессов с RAM ≥ 20%: {len(high_mem)}")
        for p in high_mem[:3]:
            result["problems"].append(f"   • PID {p['pid']}: {p['mem']}% — {p['cmd']}")

    return result
