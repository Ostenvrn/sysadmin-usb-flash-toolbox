"""
Проверка температуры (все датчики).
- Linux: /sys/class/thermal, sensors
- Windows: WMI (не всегда доступно)
"""
import glob

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-temperature")


def check_temperature() -> dict:
    """Проверяет температуру."""
    result = {
        "category": "Температура",
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
    """Проверка температуры на Linux через /sys/class/thermal."""
    sensors = []

    for zone in glob.glob("/sys/class/thermal/thermal_zone*"):
        try:
            with open(f"{zone}/type", "r") as f:
                zone_type = f.read().strip()
            with open(f"{zone}/temp", "r") as f:
                temp_c = int(f.read().strip()) / 1000

            sensors.append({
                "name": zone_type,
                "temp_c": round(temp_c, 1),
            })

            # Анализ
            if temp_c >= 90:
                result["status"] = "critical"
                result["problems"].append(
                    f"🔴 Критическая температура ({zone_type}): {temp_c:.1f}°C"
                )
                result["recommendations"].append(
                    f"Срочно проверьте охлаждение ({zone_type}). "
                    "Возможные причины: пыль в кулерах, неисправный вентилятор, "
                    "высохшая термопаста. Не работайте под нагрузкой до устранения."
                )
            elif temp_c >= 75:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Высокая температура ({zone_type}): {temp_c:.1f}°C"
                )
                result["recommendations"].append(
                    f"Проверьте охлаждение ({zone_type}). Рекомендуется "
                    "почистить кулеры от пыли и проверить работу вентиляторов."
                )
        except Exception:
            continue

    result["details"]["sensors"] = sensors
    result["details"]["total_sensors"] = len(sensors)

    if not sensors:
        result["details"]["note"] = "Датчики температуры не найдены"

    return result


def _check_windows(result: dict) -> dict:
    """Проверка температуры на Windows (WMI)."""
    ps_cmd = (
        "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
        "-ErrorAction SilentlyContinue | "
        "Select-Object InstanceName,CurrentTemperature | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip():
        result["details"]["note"] = (
            "Датчики температуры недоступны (требуются права администратора "
            "или поддержка WMI)"
        )
        return result

    import json
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data = [data]

        sensors = []
        for item in data:
            # CurrentTemperature в десятых долях Кельвина
            temp_k = item.get("CurrentTemperature", 0) / 10
            temp_c = temp_k - 273.15 if temp_k > 0 else 0
            sensors.append({
                "name": item.get("InstanceName", "unknown"),
                "temp_c": round(temp_c, 1),
            })

            if temp_c >= 90:
                result["status"] = "critical"
                result["problems"].append(
                    f"🔴 Критическая температура: {temp_c:.1f}°C"
                )
                result["recommendations"].append(
                    "Проверьте охлаждение: пыль в кулерах, вентиляторы, термопаста."
                )
            elif temp_c >= 75:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Высокая температура: {temp_c:.1f}°C"
                )

        result["details"]["sensors"] = sensors
    except Exception as e:
        logger.error(f"Ошибка парсинга температуры (Windows): {e}")

    return result
