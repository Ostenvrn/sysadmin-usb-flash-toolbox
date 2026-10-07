"""
Сканирование подсети.
Находит все активные устройства в сети.
Использует ping + ARP + nmap (если доступен).
"""
import ipaddress
import socket
import subprocess
import concurrent.futures
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("network-scan")


def get_local_ip() -> str:
    """Определяет локальный IP."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def get_subnet(local_ip: str, prefix: int = 24) -> str:
    """IP → подсеть."""
    try:
        network = ipaddress.ip_network(f"{local_ip}/{prefix}", strict=False)
        return str(network)
    except Exception:
        return ""


def parse_subnet(subnet: str) -> list:
    """Список IP в подсети."""
    try:
        network = ipaddress.ip_network(subnet, strict=False)
        return [str(ip) for ip in network.hosts()]
    except Exception:
        return []


def ping_host(ip: str, timeout: int = 1) -> bool:
    """Пингует один IP."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), ip]

    rc, _, _ = os_detector.run_command(cmd)
    return rc == 0


def get_hostname(ip: str) -> str:
    """Пытается получить hostname по IP."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def get_mac(ip: str) -> str:
    """Пытается получить MAC-адрес по IP (из ARP-таблицы)."""
    try:
        if os_detector.is_windows:
            rc, stdout, _ = os_detector.run_command(["arp", "-a", ip])
        else:
            rc, stdout, _ = os_detector.run_command(["arp", "-n", ip])

        if rc != 0:
            return ""

        for line in stdout.splitlines():
            if ip in line:
                # Ищем MAC-адрес (формат: xx:xx:xx:xx:xx:xx)
                import re
                m = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", line)
                if m:
                    return m.group(0).upper()
    except Exception:
        pass
    return ""


def scan_subnet(subnet: str, timeout: int = 1) -> list:
    """Сканирует подсеть. Возвращает список активных устройств."""
    hosts = parse_subnet(subnet)
    total = len(hosts)
    logger.info(f"Сканирование {subnet} ({total} адресов)")

    print(f"  🔍 Сканирование {subnet}")
    print(f"  Всего адресов: {total}")
    print(f"  Параллельных потоков: 50")
    print()

    active = []

    def check_host(ip: str):
        if ping_host(ip, timeout=timeout):
            return {
                "ip": ip,
                "hostname": get_hostname(ip),
                "mac": get_mac(ip),
            }
        return None

    # Параллельный ping
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_host, ip): ip for ip in hosts}

        done = 0
        for future in concurrent.futures.as_completed(futures):
            done += 1
            if done % 30 == 0 or done == total:
                print(f"  Проверено: {done}/{total} | Найдено: {len(active)}")

            result = future.result()
            if result:
                active.append(result)
                hostname = result["hostname"] or "(без имени)"
                print(f"     ✅ {result['ip']} — {hostname}")

    return active


# =====================================================================
# Вывод
# =====================================================================

def print_report(devices: list, subnet: str):
    """Красивый вывод."""
    print()
    print("=" * 70)
    print("  РЕЗУЛЬТАТ СКАНИРОВАНИЯ")
    print("=" * 70)
    print(f"  Подсеть: {subnet}")
    print(f"  Активных устройств: {len(devices)}")
    print()

    if not devices:
        print("  Устройства не найдены.")
        return

    # Сортируем по IP
    devices_sorted = sorted(
        devices,
        key=lambda d: tuple(int(x) for x in d["ip"].split("."))
    )

    for d in devices_sorted:
        print(f"  🖥️  {d['ip']}")
        if d["hostname"]:
            print(f"     Hostname: {d['hostname']}")
        if d["mac"]:
            print(f"     MAC:      {d['mac']}")
        print()


def run():
    """Точка входа."""
    print()
    print("=" * 70)
    print("  СКАНИРОВАНИЕ ПОДСЕТИ")
    print("=" * 70)
    print()

    # Определяем подсеть
    local_ip = get_local_ip()
    if not local_ip:
        print("  ❌ Не удалось определить локальный IP")
        input("  Нажми Enter...")
        return

    print(f"  Твой IP: {local_ip}")
    subnet = get_subnet(local_ip, prefix=24)
    print(f"  Подсеть: {subnet}")
    print()

    # Спрашиваем
    answer = input(f"  Сканировать {subnet}? [Y/n]: ").strip().lower()
    if answer == "n":
        custom = input("  Введи свою подсеть (например, 192.168.1.0/24): ").strip()
        if not custom:
            return
        subnet = custom

    print()
    print("  ⚠️  Для /24 (~254 адреса) — 30-60 секунд.")
    print()
    confirm = input("  Начать? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print()

    # Сканируем
    devices = scan_subnet(subnet, timeout=1)
    print_report(devices, subnet)

    # Сохраняем
    if devices:
        import json
        from pathlib import Path
        output_dir = Path(__file__).parent.parent.parent.parent / "output" / "scans"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = output_dir / f"network_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "subnet": subnet,
                "scanned_at": datetime.now().isoformat(),
                "devices": devices,
            }, f, indent=2, ensure_ascii=False)

        print(f"  📄 Результат сохранён: {filepath}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
