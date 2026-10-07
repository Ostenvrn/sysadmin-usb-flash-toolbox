"""
Проверка сети.
Ищет: нет IP, нет интернета, потеря пакетов, проблемы с DNS.
Интернет проверяется через HTTP (надёжнее, чем ping).
"""
import socket
import re

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

    # 2. Пинг шлюза
    gateway = _get_gateway()
    result["details"]["gateway"] = gateway

    if gateway:
        gw_ok = _ping(gateway, count=2)
        result["details"]["gateway_ping"] = gw_ok
        if not gw_ok:
            result["status"] = "critical"
            result["problems"].append(f"🔴 Шлюз {gateway} не отвечает")

    # 3. DNS — разрешается ли домен
    dns_ok = _resolve_dns("ya.ru")
    result["details"]["dns_ok"] = dns_ok

    # 4. Интернет — через HTTP (надёжнее ping)
    http_ok = _check_http("http://ya.ru")
    result["details"]["internet_http"] = http_ok

    # 5. Интернет — через ping (может быть заблокирован)
    ping_ok = _ping("8.8.8.8", count=3)
    result["details"]["internet_ping"] = ping_ok

    # Итоговая логика: интернет есть, если HTTP ИЛИ ping работает
    internet_ok = http_ok or ping_ok

    if not internet_ok:
        # Ни HTTP, ни ping — интернета нет
        if result["status"] == "ok":
            result["status"] = "warning"
        result["problems"].append(
            "🟡 Нет доступа в интернет (ни HTTP, ни ping не работают)"
        )
    elif not ping_ok and http_ok:
        # HTTP работает, ping — нет. Это нормально, но отметим.
        result["details"]["note"] = (
            "Ping заблокирован провайдером, но интернет работает (HTTP OK)"
        )

    # 6. Потеря пакетов (только если ping работает)
    if ping_ok:
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
    """Пингует хост."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]

    rc, _, _ = os_detector.run_command(cmd)
    return rc == 0


def _ping_loss(host: str, count: int = 5) -> float:
    """Процент потери пакетов."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]

    rc, stdout, _ = os_detector.run_command(cmd)

    for line in stdout.splitlines():
        if "packet loss" in line.lower() or "потерян" in line.lower():
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                return float(m.group(1))

    return 0.0 if rc == 0 else 100.0


def _resolve_dns(hostname: str) -> bool:
    """Проверяет DNS."""
    try:
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False


def _check_http(url: str, timeout: int = 5) -> bool:
    """
    Проверяет интернет через HTTP-запрос.
    Использует urllib (встроенный, без внешних зависимостей).
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "sysadmin-usb/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        # HTTP-ошибка (404 и т.п.) — но сервер ответил, значит интернет есть
        return True
    except Exception as e:
        logger.debug(f"HTTP-проверка {url}: {e}")
        return False
