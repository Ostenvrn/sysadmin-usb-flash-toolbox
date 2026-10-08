"""
Проверка питания.
Кроссплатформенно: Linux (/sys/class/power_supply) + Windows (WMI).
"""
import os
import glob
import json

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-power")


def check_power() -> dict:
    result = {
        "category": "Питание",
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
    """Win32_Battery на Windows."""
    ps_cmd = (
        "$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; "
        "if ($bat) { $bat | Select-Object EstimatedChargeRemaining,BatteryStatus,"
        "DesignCapacity,FullChargeCapacity | ConvertTo-Json -Compress } "
        "else { 'none' }"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip() or stdout.strip() == "none":
        result["details"]["type"] = "desktop"
        result["details"]["battery"] = "нет (стационарный ПК)"
        return result

    result["details"]["type"] = "laptop"

    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            data = data[0]

        percent = data.get("EstimatedChargeRemaining", 0)
        status_code = data.get("BatteryStatus", 0)
        design = data.get("DesignCapacity", 0)
        full = data.get("FullChargeCapacity", 0)

        status_map = {1: "Разрядка", 2: "Питание от сети", 3: "Полностью заряжена"}
        status_text = status_map.get(status_code, f"Код {status_code}")

        health = None
        if design and design > 0 and full:
            health = round((full / design) * 100, 1)

        bat_info = {"percent": percent, "status": status_text}
        if health:
            bat_info["health_percent"] = health

        result["details"]["battery_info"] = bat_info

        if percent < 10 and status_code == 1:
            result["status"] = "critical"
            result["problems"].append(f"🔴 Батарея разряжена: {percent}%")
            result["recommendations"].append("Подключите зарядное устройство.")
        elif percent < 20 and status_code == 1:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(f"🟡 Низкий заряд: {percent}%")
            result["recommendations"].append("Подключите зарядное устройство.")

        if health is not None:
            if health < 50:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Батарея изношена: {health}%")
                result["recommendations"].append("Рекомендуется замена батареи.")
            elif health < 70:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Батарея изношена: {health}%")
                result["recommendations"].append("Рассмотрите замену батареи.")
    except Exception as e:
        logger.error(f"Ошибка парсинга батареи (Windows): {e}")

    return result


def _check_linux(result: dict) -> dict:
    """Батарея на Linux."""
    batteries = glob.glob("/sys/class/power_supply/BAT*")

    if not batteries:
        result["details"]["type"] = "desktop"
        result["details"]["battery"] = "нет (стационарный ПК)"
        return result

    result["details"]["type"] = "laptop"

    for bat_path in batteries:
        bat_info = {"path": bat_path}

        try:
            with open(f"{bat_path}/capacity", "r") as f:
                bat_info["percent"] = int(f.read().strip())
        except Exception:
            pass

        try:
            with open(f"{bat_path}/status", "r") as f:
                bat_info["status"] = f.read().strip()
        except Exception:
            pass

        # Здоровье
        try:
            with open(f"{bat_path}/energy_full", "r") as f:
                energy_full = int(f.read().strip())
            with open(f"{bat_path}/energy_full_design", "r") as f:
                energy_design = int(f.read().strip())
            if energy_design > 0:
                bat_info["health_percent"] = round((energy_full / energy_design) * 100, 1)
        except Exception:
            try:
                with open(f"{bat_path}/charge_full", "r") as f:
                    charge_full = int(f.read().strip())
                with open(f"{bat_path}/charge_full_design", "r") as f:
                    charge_design = int(f.read().strip())
                if charge_design > 0:
                    bat_info["health_percent"] = round((charge_full / charge_design) * 100, 1)
            except Exception:
                pass

        result["details"]["battery_info"] = bat_info

        percent = bat_info.get("percent")
        status = bat_info.get("status", "").lower()
        health = bat_info.get("health_percent")

        if percent is not None:
            if percent < 10 and "discharg" in status:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Батарея разряжена: {percent}%")
                result["recommendations"].append("Подключите зарядное устройство.")
            elif percent < 20 and "discharg" in status:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Низкий заряд: {percent}%")

        if health is not None:
            if health < 50:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Батарея изношена: {health}%")
            elif health < 70:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Батарея изношена: {health}%")

    return result
