"""
Проверка сети.
Кроссплатформенно: Linux + Windows.
"""
import socket
import re
import urllib.request
import urllib.error

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-network")


def check_network() -> dict:
    result = {
        "category": "Сеть",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    local_ip = _get_local_ip()
    result["details"]["local_ip"] = local_ip
    if not local_ip:
        result["status"] = "critical"
        result["problems"].append("🔴 Нет IP-адреса — сеть не подключена")
        result["recommendations"].append("Проверьте кабель/Wi-Fi.")
        return result

    gateway = _get_gateway()
    result["details"]["gateway"] = gateway
    if gateway:
        gw_ok = _ping(gateway, count=2)
        result["details"]["gateway_ping"] = gw_ok
        if not gw_ok:
            result["status"] = "critical"
            result["problems"].append(f"🔴 Шлюз {gateway} не отвечает")
            result["recommendations"].append("Проверьте настройки сети.")

    dns_ok = _resolve_dns("ya.ru")
    result["details"]["dns_ok"] = dns_ok

    http_ok = _check_http("http://ya.ru")
    result["details"]["internet_http"] = http_ok

    ping_ok = _ping("8.8.8.8", count=3)
    result["details"]["internet_ping"] = ping_ok

    internet_ok = http_ok or ping_ok

    if not internet_ok:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append("🟡 Нет доступа в интернет (ни HTTP, ни ping)")
        result["recommendations"].append("Проверьте подключение к роутеру.")
    elif not ping_ok and http_ok:
        result["details"]["note"] = "Ping заблокирован, но интернет работает (HTTP OK)"

    if not dns_ok:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append("🟡 DNS не работает")
        result["recommendations"].append("Проверьте DNS-серверы (8.8.8.8, 1.1.1.1).")

    if ping_ok:
        loss = _ping_loss("8.8.8.8", count=5)
        result["details"]["packet_loss"] = loss
        if loss is not None and loss > 10:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(f"🟡 Потеря пакетов: {loss}%")

    return result


def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def _get_gateway() -> str:
    if os_detector.is_windows:
        ps_cmd = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
            "Select-Object -First 1 -ExpandProperty NextHop)"
        )
        rc, stdout, _ = os_detector.run_command(
            ["powershell", "-NoProfile", "-Command", ps_cmd]
        )
        if rc == 0 and stdout.strip():
            gw = stdout.strip().splitlines()[0].strip()
            if gw:
                return gw
    else:
        rc, stdout, _ = os_detector.run_command(["ip", "route"])
        if rc == 0:
            for line in stdout.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
    return ""


def _ping(host: str, count: int = 3) -> bool:
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]
    rc, _, _ = os_detector.run_command(cmd)
    return rc == 0


def _ping_loss(host: str, count: int = 5) -> float:
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]

    rc, stdout, _ = os_detector.run_command(cmd)

    for line in stdout.splitlines():
        low = line.lower()
        if "packet loss" in low or "потерян" in low or "потеря" in low:
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                return float(m.group(1))
    return 0.0 if rc == 0 else 100.0


def _resolve_dns(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False


def _check_http(url: str, timeout: int = 5) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sysadmin-usb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False
