"""
Проверка питания.
- Ноутбук: батарея, заряд, износ, режим питания
- ПК: режим питания, электропитание
"""
import os
import glob

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-power")


def check_power() -> dict:
    """Проверяет питание."""
    result = {
        "category": "Питание",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    if os_detector.is_linux:
        result = _check_linux(result)
    elif os_detector.is_windows:
        result = _check_windows(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"🟡 ОС {os_detector.system} не поддерживается")

    return result


def _check_linux(result: dict) -> dict:
    """Проверка питания на Linux."""
    # Ищем батареи
    batteries = glob.glob("/sys/class/power_supply/BAT*")

    if not batteries:
        # Это стационарный ПК — проверяем только режим питания
        result["details"]["type"] = "desktop"
        result["details"]["battery"] = "нет (стационарный ПК)"
        return result

    result["details"]["type"] = "laptop"

    for bat_path in batteries:
        bat_info = {"path": bat_path}

        # Заряд (%)
        try:
            with open(f"{bat_path}/capacity", "r") as f:
                bat_info["percent"] = int(f.read().strip())
        except Exception:
            pass

        # Статус (Charging/Discharging/Full)
        try:
            with open(f"{bat_path}/status", "r") as f:
                bat_info["status"] = f.read().strip()
        except Exception:
            pass

        # Здоровье (energy_full / energy_full_design)
        try:
            with open(f"{bat_path}/energy_full", "r") as f:
                energy_full = int(f.read().strip())
            with open(f"{bat_path}/energy_full_design", "r") as f:
                energy_design = int(f.read().strip())
            if energy_design > 0:
                health = round((energy_full / energy_design) * 100, 1)
                bat_info["health_percent"] = health
        except Exception:
            # Иногда используются charge_full вместо energy_full
            try:
                with open(f"{bat_path}/charge_full", "r") as f:
                    charge_full = int(f.read().strip())
                with open(f"{bat_path}/charge_full_design", "r") as f:
                    charge_design = int(f.read().strip())
                if charge_design > 0:
                    health = round((charge_full / charge_design) * 100, 1)
                    bat_info["health_percent"] = health
            except Exception:
                pass

        # Напряжение и ток
        try:
            with open(f"{bat_path}/voltage_now", "r") as f:
                bat_info["voltage_v"] = round(int(f.read().strip()) / 1_000_000, 2)
        except Exception:
            pass

        result["details"]["battery_info"] = bat_info

        # Анализ
        percent = bat_info.get("percent")
        status = bat_info.get("status", "").lower()
        health = bat_info.get("health_percent")

        # Низкий заряд
        if percent is not None:
            if percent < 10 and "discharg" in status:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Батарея разряжена: {percent}%")
                result["recommendations"].append(
                    "Подключите зарядное устройство немедленно. "
                    "При разряде ниже 5% возможна потеря данных."
                )
            elif percent < 20 and "discharg" in status:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Низкий заряд батареи: {percent}%")
                result["recommendations"].append(
                    "Подключите зарядное устройство. "
                    "Рекомендуется не разряжать батарею ниже 20%."
                )

        # Износ батареи
        if health is not None:
            if health < 50:
                result["status"] = "critical"
                result["problems"].append(
                    f"🔴 Батарея сильно изношена: здоровье {health}%"
                )
                result["recommendations"].append(
                    "Батарея потеряла более 50% ёмкости. "
                    "Рекомендуется замена батареи."
                )
            elif health < 70:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Батарея изношена: здоровье {health}%"
                )
                result["recommendations"].append(
                    "Батарея потеряла более 30% ёмкости. "
                    "Рассмотрите замену в ближайшие месяцы."
                )

    return result


def _check_windows(result: dict) -> dict:
    """Проверка питания на Windows."""
    # Информация о батарее
    ps_cmd = (
        "$bat = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; "
        "if ($bat) { "
        "$bat | Select-Object EstimatedChargeRemaining,BatteryStatus,"
        "DesignCapacity,FullChargeCapacity | ConvertTo-Json -Compress "
        "} else { 'none' }"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip() or stdout.strip() == "none":
        result["details"]["type"] = "desktop"
        result["details"]["battery"] = "нет (стационарный ПК)"
        return result

    result["details"]["type"] = "laptop"

    import json
    try:
        data = json.loads(stdout)
        if isinstance(data, list):
            data = data[0]

        percent = data.get("EstimatedChargeRemaining", 0)
        status_code = data.get("BatteryStatus", 0)
        design = data.get("DesignCapacity", 0)
        full = data.get("FullChargeCapacity", 0)

        # BatteryStatus: 1 = discharging, 2 = AC power, 3 = fully charged
        status_map = {1: "Разрядка", 2: "Питание от сети", 3: "Полностью заряжена"}
        status_text = status_map.get(status_code, f"Код {status_code}")

        health = None
        if design and design > 0 and full:
            health = round((full / design) * 100, 1)

        bat_info = {
            "percent": percent,
            "status": status_text,
        }
        if health:
            bat_info["health_percent"] = health

        result["details"]["battery_info"] = bat_info

        # Анализ
        if percent < 10 and status_code == 1:
            result["status"] = "critical"
            result["problems"].append(f"🔴 Батарея разряжена: {percent}%")
            result["recommendations"].append(
                "Подключите зарядное устройство немедленно."
            )
        elif percent < 20 and status_code == 1:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(f"🟡 Низкий заряд батареи: {percent}%")
            result["recommendations"].append(
                "Подключите зарядное устройство."
            )

        if health is not None:
            if health < 50:
                result["status"] = "critical"
                result["problems"].append(
                    f"🔴 Батарея сильно изношена: здоровье {health}%"
                )
                result["recommendations"].append(
                    "Рекомендуется замена батареи."
                )
            elif health < 70:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Батарея изношена: здоровье {health}%"
                )
                result["recommendations"].append(
                    "Рассмотрите замену батареи в ближайшие месяцы."
                )
    except Exception as e:
        logger.error(f"Ошибка парсинга батареи (Windows): {e}")

    return result
