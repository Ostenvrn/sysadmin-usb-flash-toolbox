"""
Диагностика сети.
- Ping, tracert, DNS, проверка портов
- HTTP-проверка сайтов
"""
import socket
import subprocess
import re

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("network-diagnostics")


def ping_host(host: str, count: int = 4) -> dict:
    """Пингует хост."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", host]

    rc, stdout, stderr = os_detector.run_command(cmd)

    result = {
        "host": host,
        "ok": rc == 0,
        "output": stdout,
    }

    # Парсим потери и среднее время
    loss = None
    avg_ms = None

    for line in stdout.splitlines():
        if "packet loss" in line.lower() or "потерян" in line.lower():
            m = re.search(r"(\d+(?:\.\d+)?)%", line)
            if m:
                loss = float(m.group(1))
        if "avg" in line.lower() or "среднее" in line.lower():
            m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)", line)
            if m:
                avg_ms = float(m.group(2))

    result["loss_percent"] = loss
    result["avg_ms"] = avg_ms

    return result


def traceroute_host(host: str, max_hops: int = 15) -> dict:
    """Трассировка маршрута."""
    if os_detector.is_windows:
        cmd = ["tracert", "-h", str(max_hops), host]
    else:
        cmd = ["traceroute", "-m", str(max_hops), host]

    rc, stdout, stderr = os_detector.run_command(cmd)

    return {
        "host": host,
        "ok": rc == 0,
        "output": stdout,
    }


def check_dns(hostname: str) -> dict:
    """Проверяет DNS."""
    result = {"hostname": hostname, "ok": False, "ip": None, "error": None}

    try:
        ip = socket.gethostbyname(hostname)
        result["ok"] = True
        result["ip"] = ip
    except Exception as e:
        result["error"] = str(e)

    return result


def check_port(host: str, port: int, timeout: int = 3) -> bool:
    """Проверяет, открыт ли порт."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        rc = sock.connect_ex((host, port))
        sock.close()
        return rc == 0
    except Exception:
        return False


def check_http(url: str, timeout: int = 5) -> dict:
    """Проверяет HTTP-доступность."""
    import urllib.request
    import urllib.error
    import time

    result = {"url": url, "ok": False, "status": None, "time_ms": None, "error": None}

    try:
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "sysadmin-usb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result["ok"] = response.status == 200
            result["status"] = response.status
            result["time_ms"] = round((time.time() - start) * 1000, 1)
    except urllib.error.HTTPError as e:
        result["status"] = e.code
        result["ok"] = True  # сервер ответил — значит, доступен
        result["error"] = f"HTTP {e.code}"
    except Exception as e:
        result["error"] = str(e)

    return result


# =====================================================================
# Меню
# =====================================================================

def menu_ping():
    """Меню ping."""
    print()
    print("=" * 60)
    print("  PING")
    print("=" * 60)
    print()
    host = input("  Введи хост (IP или домен): ").strip()
    if not host:
        return

    print()
    print(f"  Пингую {host}...")
    print()
    result = ping_host(host)

    if result["ok"]:
        print(f"  🟢 {host}: доступен")
        if result["avg_ms"] is not None:
            print(f"     Среднее время: {result['avg_ms']} мс")
        if result["loss_percent"] is not None:
            print(f"     Потери: {result['loss_percent']}%")
    else:
        print(f"  🔴 {host}: недоступен")
        print()
        print("  Возможные причины:")
        print("    • Хост выключен или не в сети")
        print("    • Блокировка ICMP (ping) на хосте")
        print("    • Проблемы с сетью")
        print("    • Неправильный IP или домен")

    print()
    input("  Нажми Enter для продолжения...")


def menu_tracert():
    """Меню tracert."""
    print()
    print("=" * 60)
    print("  ТРАССИРОВКА МАРШРУТА")
    print("=" * 60)
    print()
    host = input("  Введи хост (IP или домен): ").strip()
    if not host:
        return

    print()
    print(f"  Трассировка до {host}...")
    print()

    result = traceroute_host(host)
    if result["ok"]:
        print(result["output"])
    else:
        print(f"  ❌ Ошибка трассировки")
        print(f"  {result['output']}")

    print()
    input("  Нажми Enter для продолжения...")


def menu_dns():
    """Меню DNS."""
    print()
    print("=" * 60)
    print("  ПРОВЕРКА DNS")
    print("=" * 60)
    print()
    hostname = input("  Введи домен (например, ya.ru): ").strip()
    if not hostname:
        return

    print()
    result = check_dns(hostname)

    if result["ok"]:
        print(f"  🟢 {hostname} → {result['ip']}")
    else:
        print(f"  🔴 {hostname} не разрешается")
        print(f"     Ошибка: {result['error']}")
        print()
        print("  Возможные причины:")
        print("    • DNS-сервер недоступен")
        print("    • Домен не существует")
        print("    • Проблемы с сетью")

    print()
    input("  Нажми Enter для продолжения...")


def menu_port():
    """Меню проверки портов."""
    print()
    print("=" * 60)
    print("  ПРОВЕРКА ПОРТА")
    print("=" * 60)
    print()
    host = input("  IP или домен: ").strip()
    if not host:
        return

    port_str = input("  Порт (например, 80, 443, 22): ").strip()
    if not port_str.isdigit():
        print("  ❌ Порт должен быть числом")
        input("  Нажми Enter...")
        return

    port = int(port_str)
    print()
    print(f"  Проверяю {host}:{port}...")

    if check_port(host, port):
        print(f"  🟢 Порт {port} открыт")
    else:
        print(f"  🔴 Порт {port} закрыт или недоступен")

    print()
    input("  Нажми Enter для продолжения...")


def menu_http():
    """Меню HTTP-проверки."""
    print()
    print("=" * 60)
    print("  HTTP-ПРОВЕРКА")
    print("=" * 60)
    print()
    url = input("  Введи URL (например, https://ya.ru): ").strip()
    if not url:
        return
    if not url.startswith("http"):
        url = "https://" + url

    print()
    print(f"  Проверяю {url}...")
    result = check_http(url)

    if result["ok"]:
        print(f"  🟢 {url}: доступен")
        if result["status"]:
            print(f"     HTTP статус: {result['status']}")
        if result["time_ms"] is not None:
            print(f"     Время ответа: {result['time_ms']} мс")
    else:
        print(f"  🔴 {url}: недоступен")
        if result["error"]:
            print(f"     Ошибка: {result['error']}")

    print()
    input("  Нажми Enter для продолжения...")


def run():
    """Точка входа для диагностики."""
    while True:
        print()
        print("=" * 60)
        print("  🌐 ДИАГНОСТИКА СЕТИ")
        print("=" * 60)
        print()
        print("  [1] Ping — проверить доступность хоста")
        print("  [2] Tracert — трассировка маршрута")
        print("  [3] DNS — проверка разрешения домена")
        print("  [4] Порт — проверить открыт ли порт")
        print("  [5] HTTP — проверить доступность сайта")
        print("  [0] ← Назад")
        print()

        choice = input("  Ваш выбор: ").strip()

        if choice == "0":
            break
        elif choice == "1":
            menu_ping()
        elif choice == "2":
            menu_tracert()
        elif choice == "3":
            menu_dns()
        elif choice == "4":
            menu_port()
        elif choice == "5":
            menu_http()
        else:
            print("  Неверный выбор.")


if __name__ == "__main__":
    run()
