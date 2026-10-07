"""
Генерация общего отчёта.
Собирает данные из всех категорий:
- Система (info, health check)
- Принтеры
- Сеть
- Бэкапы
"""
import os
import json
import platform
import socket
import shutil
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("reports-generate")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
REPORTS_DIR = PROJECT_ROOT / "output" / "reports"


# =====================================================================
# Сбор данных
# =====================================================================

def collect_system_info() -> dict:
    """Информация о ПК."""
    info = {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "release": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "cpu_cores": os.cpu_count(),
    }

    # RAM
    if os_detector.is_linux:
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

                info["ram_total_gb"] = round(total_kb / 1024 / 1024, 2)
                info["ram_used_gb"] = round(used_kb / 1024 / 1024, 2)
                if total_kb > 0:
                    info["ram_percent"] = round((used_kb / total_kb) * 100, 1)
        except Exception:
            pass

    # Диски
    disks = []
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
    info["disks"] = disks

    return info


def collect_health_check() -> dict:
    """Запускает health check и возвращает результат."""
    try:
        from app.categories.system.health_check import runner
        results = runner.run_all_checks()
        summary = runner.summarize(results)
        return {
            "summary": summary,
            "results": results,
        }
    except Exception as e:
        logger.error(f"Ошибка health check: {e}")
        return {"summary": {}, "results": []}


def collect_printers() -> dict:
    """Собирает информацию о принтерах."""
    try:
        import yaml
        config_path = PROJECT_ROOT / "config" / "printers.yaml"
        auto_config = PROJECT_ROOT / "config" / "printers_auto.yaml"

        printers = []
        for cfg in [config_path, auto_config]:
            if cfg.exists():
                with open(cfg, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                printers.extend(data.get("printers", []))

        return {"count": len(printers), "printers": printers}
    except Exception as e:
        logger.error(f"Ошибка принтеров: {e}")
        return {"count": 0, "printers": []}


def collect_backups() -> dict:
    """Собирает информацию о бэкапах."""
    try:
        from app.categories.backup.list import list_backups, format_size
        backups = list_backups()
        total_size = sum(b["size"] for b in backups)
        return {
            "count": len(backups),
            "total_size": format_size(total_size),
            "backups": [
                {
                    "name": b["name"],
                    "date": b["date_str"],
                    "size": format_size(b["size"]),
                }
                for b in backups[:20]
            ],
        }
    except Exception as e:
        logger.error(f"Ошибка бэкапов: {e}")
        return {"count": 0, "total_size": "0 Б", "backups": []}


def collect_network_scan() -> dict:
    """Последнее сканирование сети."""
    try:
        scans_dir = PROJECT_ROOT / "output" / "scans"
        if not scans_dir.exists():
            return {"count": 0, "devices": []}

        files = sorted(scans_dir.glob("network_*.json"), reverse=True)
        if not files:
            return {"count": 0, "devices": []}

        with open(files[0], "r", encoding="utf-8") as f:
            data = json.load(f)

        devices = data.get("devices", [])
        return {
            "count": len(devices),
            "scanned_at": data.get("scanned_at", ""),
            "devices": devices,
        }
    except Exception as e:
        logger.error(f"Ошибка сети: {e}")
        return {"count": 0, "devices": []}


# =====================================================================
# Генерация Markdown
# =====================================================================

def generate_markdown(data: dict) -> str:
    """Генерирует Markdown-отчёт."""
    lines = []
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    lines.append(f"# 📊 Отчёт sysadmin-usb")
    lines.append(f"")
    lines.append(f"**Дата:** {now}")
    lines.append(f"**ПК:** {data['system']['hostname']}")
    lines.append(f"**ОС:** {data['system']['os']} {data['system']['release']}")
    lines.append(f"")

    # === Система ===
    sys_info = data["system"]
    lines.append(f"## 🖥️ Система")
    lines.append(f"")
    lines.append(f"- **Hostname:** {sys_info['hostname']}")
    lines.append(f"- **ОС:** {sys_info['os']} {sys_info['release']} ({sys_info['architecture']})")
    lines.append(f"- **Python:** {sys_info['python']}")
    lines.append(f"- **CPU:** {sys_info['cpu_cores']} ядер")
    if sys_info.get("ram_total_gb"):
        lines.append(f"- **RAM:** {sys_info['ram_used_gb']} / {sys_info['ram_total_gb']} ГБ ({sys_info['ram_percent']}%)")
    lines.append(f"")

    if sys_info.get("disks"):
        lines.append(f"### 💿 Диски")
        lines.append(f"")
        lines.append(f"| Путь | Всего | Использовано | Свободно | % |")
        lines.append(f"|------|-------|--------------|----------|---|")
        for d in sys_info["disks"]:
            lines.append(
                f"| {d['path']} | {d['total_gb']} ГБ | {d['used_gb']} ГБ | {d['free_gb']} ГБ | {d['percent']}% |"
            )
        lines.append(f"")

    # === Health Check ===
    hc = data["health_check"]
    if hc.get("summary"):
        summary = hc["summary"]
        lines.append(f"## 🏥 Диагностика ПК (Health Check)")
        lines.append(f"")
        lines.append(
            f"**Всего:** {summary.get('total', 0)} | "
            f"🟢 OK: {summary.get('ok', 0)} | "
            f"🟡 Warning: {summary.get('warning', 0)} | "
            f"🔴 Critical: {summary.get('critical', 0)}"
        )
        lines.append(f"")

        problems = [r for r in hc["results"] if r.get("status") in ("warning", "critical")]
        if problems:
            lines.append(f"### ⚠️ Проблемы")
            lines.append(f"")
            for p in problems:
                icon = "🟡" if p["status"] == "warning" else "🔴"
                lines.append(f"**{icon} {p['category']}**")
                for prob in p.get("problems", []):
                    lines.append(f"- {prob}")
                for rec in p.get("recommendations", []):
                    lines.append(f"  - 💡 {rec}")
                lines.append(f"")

    # === Принтеры ===
    printers = data["printers"]
    lines.append(f"## 🖨️ Принтеры")
    lines.append(f"")
    lines.append(f"**Найдено:** {printers['count']}")
    lines.append(f"")
    if printers["printers"]:
        for p in printers["printers"][:20]:
            lines.append(f"- {p.get('name', '?')} ({p.get('ip', '?')}) — {p.get('model', '?')}")
        lines.append(f"")

    # === Бэкапы ===
    backups = data["backups"]
    lines.append(f"## 💾 Бэкапы")
    lines.append(f"")
    lines.append(f"**Всего:** {backups['count']} | **Размер:** {backups['total_size']}")
    lines.append(f"")
    if backups["backups"]:
        lines.append(f"| Имя | Дата | Размер |")
        lines.append(f"|-----|------|--------|")
        for b in backups["backups"]:
            lines.append(f"| {b['name']} | {b['date']} | {b['size']} |")
        lines.append(f"")

    # === Сеть ===
    network = data["network"]
    lines.append(f"## 🌐 Сеть")
    lines.append(f"")
    lines.append(f"**Устройств:** {network['count']}")
    if network.get("scanned_at"):
        lines.append(f"**Сканировано:** {network['scanned_at']}")
    lines.append(f"")
    if network["devices"]:
        lines.append(f"| IP | Hostname | Vendor | MAC |")
        lines.append(f"|----|----------|--------|-----|")
        for d in network["devices"][:30]:
            lines.append(
                f"| {d.get('ip', '?')} | {d.get('hostname', '') or '—'} | "
                f"{d.get('vendor', '') or '—'} | {d.get('mac', '') or '—'} |"
            )
        lines.append(f"")

    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*Сгенерировано sysadmin-usb*")

    return "\n".join(lines)


# =====================================================================
# Точка входа
# =====================================================================

def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  ГЕНЕРАЦИЯ ОТЧЁТА")
    print("=" * 80)
    print()
    print("  Сбор данных...")
    print()

    data = {}

    # 1. Система
    print("  🖥️  Система...")
    data["system"] = collect_system_info()
    print(f"     ✅ {data['system']['hostname']}")

    # 2. Health Check
    print("  🏥 Health Check...")
    data["health_check"] = collect_health_check()
    summary = data["health_check"].get("summary", {})
    print(f"     ✅ Проверок: {summary.get('total', 0)} (проблем: {summary.get('warning', 0) + summary.get('critical', 0)})")

    # 3. Принтеры
    print("  🖨️  Принтеры...")
    data["printers"] = collect_printers()
    print(f"     ✅ Найдено: {data['printers']['count']}")

    # 4. Бэкапы
    print("  💾 Бэкапы...")
    data["backups"] = collect_backups()
    print(f"     ✅ Найдено: {data['backups']['count']}")

    # 5. Сеть
    print("  🌐 Сеть...")
    data["network"] = collect_network_scan()
    print(f"     ✅ Устройств: {data['network']['count']}")

    print()

    # Генерируем отчёт
    markdown = generate_markdown(data)

    # Сохраняем
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    md_path = REPORTS_DIR / f"report_{timestamp}.md"
    json_path = REPORTS_DIR / f"report_{timestamp}.json"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    print("=" * 80)
    print("  ✅ ОТЧЁТ ГОТОВ")
    print("=" * 80)
    print()
    print(f"  📄 Markdown: {md_path}")
    print(f"  📄 JSON:     {json_path}")
    print()
    print(f"  Открой Markdown в браузере или редакторе.")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
