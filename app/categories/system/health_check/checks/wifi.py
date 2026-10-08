"""
Проверка Wi-Fi.
Кроссплатформенно: Linux (iwconfig) + Windows (netsh wlan).
"""
import re

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-wifi")


def check_wifi() -> dict:
    result = {
        "category": "Wi-Fi",
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
    """Wi-Fi на Windows через PowerShell + netsh."""
    ps_cmd = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$wifi = Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and "
        "($_.InterfaceDescription -like '*Wi-Fi*' -or $_.InterfaceDescription -like '*Wireless*')}; "
        "if (-not $wifi) { Write-Output 'none' } else { "
        "$netsh = netsh wlan show interfaces; Write-Output $netsh }"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc != 0 or not stdout.strip() or stdout.strip() == "none":
        result["details"]["note"] = "Wi-Fi интерфейсы не найдены"
        return result

    iface_info = {}
    for line in stdout.splitlines():
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip()

            if key == "ssid":
                iface_info["ssid"] = val
            elif "bssid" in key:
                iface_info["bssid"] = val
            elif "signal" in key:
                try:
                    iface_info["signal_percent"] = int(val.replace("%", "").strip())
                except ValueError:
                    pass
            elif "channel" in key or "канал" in key:
                try:
                    iface_info["channel"] = int(val)
                except ValueError:
                    pass
            elif "state" in key or "состояние" in key:
                iface_info["state"] = val

    if iface_info:
        result["details"]["wifi_info"] = [iface_info]
        signal = iface_info.get("signal_percent")
        if signal is not None:
            if signal < 30:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Очень слабый сигнал Wi-Fi: {signal}%")
                result["recommendations"].append("Подойдите ближе к роутеру.")
            elif signal < 50:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Слабый сигнал Wi-Fi: {signal}%")
    else:
        result["details"]["note"] = "Wi-Fi адаптер есть, но netsh не вернул данные"

    return result


def _check_linux(result: dict) -> dict:
    """Wi-Fi на Linux через iwconfig."""
    rc, stdout, _ = os_detector.run_command(["iwconfig"])
    if rc != 0:
        result["details"]["note"] = "iwconfig не найден"
        return result

    wifi_ifaces = []
    for line in stdout.splitlines():
        if "IEEE 802.11" in line:
            iface = line.split()[0]
            wifi_ifaces.append(iface)

    if not wifi_ifaces:
        result["details"]["note"] = "Wi-Fi интерфейсы не найдены"
        return result

    result["details"]["interfaces"] = wifi_ifaces

    for iface in wifi_ifaces:
        iface_info = {"name": iface}
        rc, stdout, _ = os_detector.run_command(["iwconfig", iface])
        if rc == 0:
            for line in stdout.splitlines():
                if "Signal level" in line:
                    m = re.search(r"Signal level[=:](-?\d+)", line)
                    if m:
                        iface_info["signal_dbm"] = int(m.group(1))
                if "ESSID" in line:
                    m = re.search(r'ESSID:"([^"]*)"', line)
                    if m:
                        iface_info["ssid"] = m.group(1)

        result["details"].setdefault("wifi_info", []).append(iface_info)

        signal = iface_info.get("signal_dbm")
        if signal is not None:
            if signal < -80:
                result["status"] = "critical"
                result["problems"].append(f"🔴 Очень слабый Wi-Fi: {signal} dBm")
            elif signal < -70:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(f"🟡 Слабый Wi-Fi: {signal} dBm")

    return result
