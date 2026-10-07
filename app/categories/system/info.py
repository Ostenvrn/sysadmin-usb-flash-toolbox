"""
Информация о ПК.
Собирает: ОС, CPU, RAM, диски, сеть, uptime, пользователи.
Работает на Windows и Linux.
"""
import os
import platform
import socket
import shutil
from datetime import datetime, timedelta

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("system-info")


# =====================================================================
# Сбор информации
# =====================================================================

def get_os_info() -> dict:
    """Информация об ОС."""
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "hostname": socket.gethostname(),
        "python": platform.python_version(),
    }


def get_cpu_info() -> dict:
    """Информация о CPU."""
    info = {
        "cores": os.cpu_count(),
    }

    if os_detector.is_linux:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        info["model"] = line.split(":")[1].strip()
                        break
        except Exception:
            info["model"] = "unknown"
    elif os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor).Name"]
        )
        if rc == 0:
            info["model"] = stdout.strip()

    return info


def get_memory_info() -> dict:
    """Информация о RAM."""
    info = {"total_gb": None, "used_gb": None, "percent": None}

    if os_detector.is_linux:
        try:
            with open("/proc/meminfo", "r") as f:
                mem = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem[key] = int(val)

                total_kb = mem.get("MemTotal", 0)
                available_kb = mem.get("MemAvailable", 0)
                used_kb = total_kb - available_kb

                info["total_gb"] = round(total_kb / 1024 / 1024, 2)
                info["used_gb"] = round(used_kb / 1024 / 1024, 2)
                if total_kb > 0:
                    info["percent"] = round((used_kb / total_kb) * 100, 1)
        except Exception as e:
            logger.error(f"Ошибка чтения RAM: {e}")
    elif os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(
            ["powershell", "-NoProfile", "-Command",
             "$os = Get-CimInstance Win32_OperatingSystem; "
             "$total = $os.TotalVisibleMemorySize; "
             "$free = $os.FreePhysicalMemory; "
             "Write-Output \"$total $free\""]
        )
        if rc == 0:
            try:
                total_kb, free_kb = stdout.strip().split()
                total_kb = int(total_kb)
                free_kb = int(free_kb)
                used_kb = total_kb - free_kb
                info["total_gb"] = round(total_kb / 1024 / 1024, 2)
                info["used_gb"] = round(used_kb / 1024 / 1024, 2)
                if total_kb > 0:
                    info["percent"] = round((used_kb / total_kb) * 100, 1)
            except Exception as e:
                logger.error(f"Ошибка парсинга RAM (Windows): {e}")

    return info


def get_disk_info() -> list:
    """Информация о дисках."""
    disks = []

    if os_detector.is_windows:
        # Windows: перебираем буквы дисков
        import string
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
        # Linux: корень и /home (если отдельно)
        for path in ["/", "/home"]:
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

    return disks


def get_network_info() -> list:
    """Информация о сетевых интерфейсах."""
    interfaces = []

    if os_detector.is_linux:
        try:
            import socket
            hostname = socket.gethostname()
            # Простой способ: получить IP через socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            interfaces.append({
                "name": "default",
                "ip": local_ip,
                "hostname": hostname,
            })
        except Exception as e:
            logger.error(f"Ошибка сети: {e}")
    elif os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(["ipconfig"])
        if rc == 0:
            current = None
            for line in stdout.splitlines():
                if "adapter" in line.lower():
                    current = {"name": line.strip(), "ip": None}
                    interfaces.append(current)
                elif "IPv4" in line and current:
                    ip = line.split(":")[-1].strip()
                    current["ip"] = ip

    return interfaces


def get_uptime() -> str:
    """Время работы системы."""
    if os_detector.is_linux:
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
            delta = timedelta(seconds=int(uptime_seconds))
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            return f"{days} д {hours} ч {minutes} мин"
        except Exception:
            return "unknown"
    elif os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"]
        )
        if rc == 0:
            return stdout.strip()
    return "unknown"


# =====================================================================
# Вывод
# =====================================================================

def collect_all() -> dict:
    """Собирает всю информацию."""
    return {
        "os": get_os_info(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "disks": get_disk_info(),
        "network": get_network_info(),
        "uptime": get_uptime(),
        "collected_at": datetime.now().isoformat(),
    }


def print_report(info: dict):
    """Красивый вывод."""
    print()
    print("=" * 70)
    print("  ИНФОРМАЦИЯ О ПК")
    print("=" * 70)
    print()

    # ОС
    os_info = info["os"]
    print(f"  🖥️  ОС:       {os_info['system']} {os_info['release']}")
    print(f"     Версия:   {os_info['version']}")
    print(f"     Архитектура: {os_info['architecture']}")
    print(f"     Hostname: {os_info['hostname']}")
    print(f"     Python:   {os_info['python']}")
    print()

    # Uptime
    print(f"  ⏱️  Uptime:   {info['uptime']}")
    print()

    # CPU
    cpu = info["cpu"]
    print(f"  🧠 CPU:      {cpu.get('model', 'unknown')}")
    print(f"     Ядер:     {cpu['cores']}")
    print()

    # RAM
    mem = info["memory"]
    if mem.get("total_gb"):
        print(f"  💾 RAM:      {mem['used_gb']} / {mem['total_gb']} ГБ ({mem['percent']}%)")
    else:
        print("  💾 RAM:      unknown")
    print()

    # Диски
    print("  💿 ДИСКИ:")
    for d in info["disks"]:
        bar = "█" * int(d["percent"] / 5) + "░" * (20 - int(d["percent"] / 5))
        icon = "🔴" if d["percent"] > 90 else "🟡" if d["percent"] > 75 else "🟢"
        print(f"     {icon} {d['path']:6} [{bar}] {d['percent']}% "
              f"({d['used_gb']} / {d['total_gb']} ГБ)")
    print()

    # Сеть
    print("  🌐 СЕТЬ:")
    for iface in info["network"]:
        print(f"     {iface.get('name', '?')}: {iface.get('ip', '?')}")
    print()

    print("=" * 70)


def run():
    """Точка входа."""
    print()
    print("Сбор информации о ПК...")

    info = collect_all()
    print_report(info)

    print()
    input("Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
