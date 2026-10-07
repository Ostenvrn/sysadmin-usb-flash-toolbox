"""
Проверка Wi-Fi.
- Linux: iwconfig, iw, nmcli
- Windows: netsh wlan show interfaces
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-wifi")


def check_wifi() -> dict:
    """Проверяет Wi-Fi."""
    result = {
        "category": "Wi-Fi",
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
    """Проверка Wi-Fi на Linux."""
    # 1. Есть ли Wi-Fi интерфейс
    rc, stdout, _ = os_detector.run_command(["iwconfig"])
    if rc != 0:
        result["details"]["note"] = "iwconfig не найден (sudo apt install wireless-tools)"
        return result

    wifi_ifaces = []
    for line in stdout.splitlines():
        if "IEEE 802.11" in line:
            iface = line.split()[0]
            wifi_ifaces.append(iface)

    if not wifi_ifaces:
        result["details"]["note"] = "Wi-Fi интерфейсы не найдены (стационарный ПК?)"
        return result

    result["details"]["interfaces"] = wifi_ifaces

    # 2. Для каждого интерфейса — детали
    for iface in wifi_ifaces:
        iface_info = {"name": iface}

        # Уровень сигнала
        rc, stdout, _ = os_detector.run_command(["iwconfig", iface])
        if rc == 0:
            for line in stdout.splitlines():
                if "Signal level" in line:
                    import re
                    m = re.search(r"Signal level[=:](-?\d+)", line)
                    if m:
                        iface_info["signal_dbm"] = int(m.group(1))
                if "ESSID" in line:
                    m = re.search(r'ESSID:"([^"]*)"', line)
                    if m:
                        iface_info["ssid"] = m.group(1)
                if "Bit Rate" in line:
                    m = re.search(r"Bit Rate[=:](\d+(?:\.\d+)?)", line)
                    if m:
                        iface_info["bitrate_mbps"] = float(m.group(1))

        result["details"].setdefault("wifi_info", []).append(iface_info)

        # Анализ сигнала
        signal = iface_info.get("signal_dbm")
        if signal is not None:
            if signal < -80:
                result["status"] = "critical"
                result["problems"].append(
                    f"🔴 Очень слабый сигнал Wi-Fi ({iface}): {signal} dBm"
                )
                result["recommendations"].append(
                    "Подойдите ближе к роутеру или используйте проводное "
                    "подключение. Слабый сигнал вызывает потерю пакетов "
                    "и медленную работу сети."
                )
            elif signal < -70:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Слабый сигнал Wi-Fi ({iface}): {signal} dBm"
                )
                result["recommendations"].append(
                    "Рекомендуется переместиться ближе к роутеру "
                    "или проверить наличие препятствий (стены, металл)."
                )

    return result


def _check_windows(result: dict) -> dict:
    """Проверка Wi-Fi на Windows."""
    rc, stdout, _ = os_detector.run_command(
        ["netsh", "wlan", "show", "interfaces"]
    )

    if rc != 0 or not stdout.strip():
        result["details"]["note"] = "Wi-Fi интерфейсы не найдены"
        return result

    iface_info = {}
    for line in stdout.splitlines():
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if "SSID" in key and "BSSID" not in key:
                iface_info["ssid"] = val
            elif "Signal" in key:
                # Формат: "80%"
                try:
                    iface_info["signal_percent"] = int(val.replace("%", ""))
                except ValueError:
                    pass
            elif "Radio type" in key:
                iface_info["radio_type"] = val
            elif "Channel" in key:
                try:
                    iface_info["channel"] = int(val)
                except ValueError:
                    pass

    if iface_info:
        result["details"]["wifi_info"] = [iface_info]

        signal = iface_info.get("signal_percent")
        if signal is not None:
            if signal < 30:
                result["status"] = "critical"
                result["problems"].append(
                    f"🔴 Очень слабый сигнал Wi-Fi: {signal}%"
                )
                result["recommendations"].append(
                    "Подойдите ближе к роутеру или используйте проводное подключение."
                )
            elif signal < 50:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Слабый сигнал Wi-Fi: {signal}%"
                )
                result["recommendations"].append(
                    "Рекомендуется переместиться ближе к роутеру."
                )

    return result
