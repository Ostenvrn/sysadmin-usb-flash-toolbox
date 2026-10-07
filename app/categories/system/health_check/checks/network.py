"""
Проверка сети.
Ищет: нет IP, нет интернета, потеря пакетов, проблемы с DNS.
"""
import socket
import subprocess

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-network")


def check_network() -> dict:
    """Проверяет сеть."""
    result = {
        "category": "Сеть",
        "status": "ok",
        "problems": [],
        "details": {},
    }

    # 1. Есть ли IP
    local_ip = _get_local_ip()
    result["details"]["local_ip"] = local_ip

    if not local_ip:
        result["status"] = "critical"
        result["problems"].append("🔴 Нет IP-адреса — сеть не подключена")
        return result

    # 2. Пинг шлюза (если можем определить)
    gateway = _get_gateway()
    result["details"]["gateway"] = gateway

    if gateway:
        gw_ok = _ping(gateway, count=2)
        result["details"]["gateway_ping"] = gw_ok
        if not gw_ok:
            result["status"] = "critical"
            result["problems"].append(f"🔴 Шлюз {gateway} не отвечает")

    # 3. Пинг 8.8.8.8 (интернет)
    inet_ok = _ping("8.8.8.8", count=3)
    result["details"]["internet_ping"] = inet_ok
    if not inet_ok:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append("🟡 Нет доступа в интернет (8.8.8.8 не отвечает)")

    # 4. DNS
    dns_ok = _resolve_dns("ya.ru")
    result["details"]["dns_ok"] = dns_ok
    if not dns_ok:
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append("🟡 DNS не работает (ya.ru не разрешается)")

    # 5. Потеря пакетов
    if inet_ok:
        loss = _ping_loss("8.8.8.8", count=5)
        result["details"]["packet_loss"] = loss
        if loss is not None and loss > 10:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(f"🟡 Потеря пакетов: {loss}%")

    return result


def _get_local_ip() -> str:
    """Возвращает локальный IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def _get_gateway() -> str:
    """Определяет шлюз."""
    if os_detector.is_linux:
        rc, stdout, _ = os_detector.run_command(["ip", "route"])
        if rc == 0:
            for line in stdout.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
    elif os_detector.is_windows:
        rc, stdout, _ = os_detector.run_command(["ipconfig"])
        if rc == 0:
            for line in stdout.splitlines():
                if "Default Gateway" in line or "Основной шлюз" in line:
                    gw = line.split(":")[-1].strip()
                    if gw and gw != "":
                        return gw
    return ""


def _ping(host: str, count: int = 3) -> bool:
    """Пингует хост. Возвращает True, если отвечает."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]

    rc, _, _ = os_detector.run_command(cmd)
    return rc == 0


def _ping_loss(host: str, count: int = 5) -> float:
    """Возвращает процент потери пакетов."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]

    rc, stdout, _ = os_detector.run_command(cmd)

    # Парсим вывод
    for line in stdout.splitlines():
        if "packet loss" in line.lower() or "потерян" in line.lower():
            # Linux: "5 packets transmitted, 5 received, 0% packet loss"
            # Windows: "(0% loss)"
            import re
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                return float(m.group(1))

    return 0.0 if rc == 0 else 100.0


def _resolve_dns(hostname: str) -> bool:
    """Проверяет, работает ли DNS."""
    try:
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False
