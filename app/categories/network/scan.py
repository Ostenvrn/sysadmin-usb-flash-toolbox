"""
Сканирование подсети.
Находит все активные устройства.
- nmap-режим (TCP SYN ping) — обходит блокировку ICMP
- MAC, производитель (из IEEE OUI базы), открытые порты
- Тип подключения: определяется только для СВОЕГО ПК (точно)
"""
import ipaddress
import socket
import re
import concurrent.futures
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger
from app.core.oui import lookup_vendor, is_local_mac

logger = setup_logger("network-scan")


# =====================================================================
# Вспомогательные функции
# =====================================================================

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
        return str(ipaddress.ip_network(f"{local_ip}/{prefix}", strict=False))
    except Exception:
        return ""


def parse_subnet(subnet: str) -> list:
    """Список IP в подсети."""
    try:
        network = ipaddress.ip_network(subnet, strict=False)
        return [str(ip) for ip in network.hosts()]
    except Exception:
        return []


def get_mac(ip: str) -> str:
    """Получает MAC-адрес через ARP."""
    if os_detector.is_windows:
        os_detector.run_command(["ping", "-n", "1", "-w", "500", ip])
    else:
        os_detector.run_command(["ping", "-c", "1", "-W", "1", ip])

    try:
        if os_detector.is_windows:
            rc, stdout, _ = os_detector.run_command(["arp", "-a", ip])
        else:
            rc, stdout, _ = os_detector.run_command(["arp", "-n", ip])

        if rc != 0:
            if os_detector.is_windows:
                rc, stdout, _ = os_detector.run_command(["arp", "-a"])
            else:
                rc, stdout, _ = os_detector.run_command(["ip", "neigh"])

        for line in stdout.splitlines():
            if ip in line:
                m = re.search(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", line)
                if m:
                    mac = m.group(0).upper().replace("-", ":")
                    if mac != "FF:FF:FF:FF:FF:FF" and not mac.startswith("01:"):
                        return mac
    except Exception:
        pass
    return ""


def get_hostname(ip: str) -> str:
    """Reverse DNS."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def ping_host(ip: str, timeout: int = 1) -> bool:
    """Пингует один IP."""
    if os_detector.is_windows:
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
    rc, _, _ = os_detector.run_command(cmd)
    return rc == 0


def get_open_ports(ip: str, timeout: float = 0.3) -> list:
    """Быстрое сканирование популярных портов."""
    ports_to_check = [22, 80, 135, 139, 443, 445, 515, 631, 3389, 9100]
    open_ports = []

    for port in ports_to_check:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            rc = sock.connect_ex((ip, port))
            sock.close()
            if rc == 0:
                open_ports.append(port)
        except Exception:
            pass

    return open_ports


def get_local_connection_type() -> str:
    """
    Определяет тип подключения СВОЕГО ПК (точно).
    По имени интерфейса: wl* = Wi-Fi, en* = провод.
    """
    if os_detector.is_windows:
        # Windows: проверяем через netsh
        rc, stdout, _ = os_detector.run_command(["netsh", "interface", "show", "interface"])
        if rc == 0:
            for line in stdout.splitlines():
                line_lower = line.lower()
                if "wi-fi" in line_lower or "wireless" in line_lower:
                    if "connected" in line_lower:
                        return "wifi"
                if "ethernet" in line_lower:
                    if "connected" in line_lower:
                        return "ethernet"
    else:
        # Linux: смотрим интерфейсы
        rc, stdout, _ = os_detector.run_command(["ip", "-br", "link"])
        if rc == 0:
            for line in stdout.splitlines():
                parts = line.split()
                if len(parts) < 2:
                    continue
                iface = parts[0]
                state = parts[1]
                if state.upper() != "UP":
                    continue
                if iface.startswith("wl"):
                    return "wifi"
                if iface.startswith("en"):
                    return "ethernet"

    return ""


# =====================================================================
# nmap-сканирование
# =====================================================================

def scan_with_nmap(subnet: str) -> list:
    """Сканирует подсеть через nmap (TCP SYN ping)."""
    try:
        import nmap
    except ImportError:
        logger.warning("python-nmap не установлен, fallback на ping")
        return []

    nm = nmap.PortScanner()
    arguments = "-sn -PS22,80,443,3389 -PA80,443 -PE --host-timeout 10s"

    print(f"  🚀 nmap-сканирование {subnet}...")

    try:
        nm.scan(hosts=subnet, arguments=arguments)
    except Exception as e:
        logger.error(f"Ошибка nmap: {e}")
        return []

    devices = []

    for host in nm.all_hosts():
        device = {
            "ip": host,
            "hostname": "",
            "mac": "",
            "vendor": "",
            "connection": "",
        }

        try:
            hostnames = nm[host].hostnames()
            if hostnames:
                device["hostname"] = hostnames[0].get("name", "")
        except Exception:
            pass

        try:
            addresses = nm[host].get("addresses", {})
            if "mac" in addresses:
                device["mac"] = addresses["mac"].upper()
        except Exception:
            pass

        devices.append(device)

    print(f"  ✅ nmap нашёл: {len(devices)} устройств")
    return devices


# =====================================================================
# Комбинированное сканирование
# =====================================================================

def scan_subnet(subnet: str, timeout: int = 1, use_nmap: bool = True) -> list:
    """Сканирует подсеть (nmap + ping)."""
    print(f"  🔍 Сканирование {subnet}")
    print()

    devices_by_ip = {}

    # === 1. nmap ===
    if use_nmap:
        nmap_devices = scan_with_nmap(subnet)
        for d in nmap_devices:
            devices_by_ip[d["ip"]] = d

    # === 2. Ping-скан ===
    hosts = parse_subnet(subnet)
    total = len(hosts)

    print(f"  🏓 Ping-сканирование ({total} адресов)...")
    print()

    def check_host(ip: str):
        if ip in devices_by_ip:
            return None

        if ping_host(ip, timeout=timeout):
            return {
                "ip": ip,
                "hostname": get_hostname(ip),
                "mac": get_mac(ip),
            }
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_host, ip): ip for ip in hosts}

        done = 0
        for future in concurrent.futures.as_completed(futures):
            done += 1
            if done % 30 == 0 or done == total:
                print(f"  Проверено: {done}/{total} | Найдено: {len(devices_by_ip)}")

            result = future.result()
            if result:
                devices_by_ip[result["ip"]] = result

    # === 3. Обогащаем данными ===
    print()
    print(f"  🔬 Обогащение данных ({len(devices_by_ip)} устройств)...")

    local_ip = get_local_ip()
    local_conn = get_local_connection_type()

    for ip, d in devices_by_ip.items():
        # MAC
        if not d.get("mac"):
            d["mac"] = get_mac(ip)

        # Производитель (из OUI базы)
        if not d.get("vendor"):
            d["vendor"] = lookup_vendor(d.get("mac", ""))

        # Hostname
        if not d.get("hostname"):
            d["hostname"] = get_hostname(ip)

        # Порты
        if not d.get("open_ports"):
            d["open_ports"] = get_open_ports(ip)

        # Тип подключения: точно только для СВОЕГО ПК
        if ip == local_ip:
            d["connection"] = local_conn
        else:
            # Для чужих — не гадаем, оставляем пустым
            d["connection"] = ""

        # Помечаем локальный MAC
        if d.get("mac") and is_local_mac(d["mac"]):
            d["is_local_mac"] = True

    return list(devices_by_ip.values())


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

    devices_sorted = sorted(
        devices,
        key=lambda d: tuple(int(x) for x in d["ip"].split("."))
    )

    for d in devices_sorted:
        conn = d.get("connection", "")
        conn_icon = {
            "wifi": "📶 Wi-Fi",
            "ethernet": "🔌 Провод",
        }.get(conn, "")

        print(f"  🖥️  {d['ip']}  {conn_icon}")
        if d.get("hostname"):
            print(f"     Hostname: {d['hostname']}")
        if d.get("vendor"):
            print(f"     Vendor:   {d['vendor']}")
        elif d.get("mac") and d.get("is_local_mac"):
            print(f"     Vendor:   (локальный MAC — random)")
        if d.get("mac"):
            print(f"     MAC:      {d['mac']}")
        if d.get("open_ports"):
            ports_str = ", ".join(map(str, d["open_ports"]))
            print(f"     Порты:    {ports_str}")
        print()


# =====================================================================
# Точка входа
# =====================================================================

def run():
    """Точка входа."""
    print()
    print("=" * 70)
    print("  СКАНИРОВАНИЕ ПОДСЕТИ")
    print("=" * 70)
    print()

    local_ip = get_local_ip()
    if not local_ip:
        print("  ❌ Не удалось определить локальный IP")
        input("  Нажми Enter...")
        return

    print(f"  Твой IP: {local_ip}")
    subnet = get_subnet(local_ip, prefix=24)
    print(f"  Подсеть: {subnet}")
    print()

    print("  Режим сканирования:")
    print("    [1] nmap + ping (обход блокировки ICMP)")
    print("    [2] только ping")
    print()

    mode = input("  Выбор [1]: ").strip() or "1"
    use_nmap = mode == "1"

    print()
    answer = input(f"  Сканировать {subnet}? [Y/n]: ").strip().lower()
    if answer == "n":
        custom = input("  Введи свою подсеть: ").strip()
        if not custom:
            return
        subnet = custom

    print()
    print("  ⚠️  Для /24 — 1-3 минуты (nmap) или 30-60 секунд (ping).")
    print()
    confirm = input("  Начать? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print()

    devices = scan_subnet(subnet, timeout=1, use_nmap=use_nmap)
    print_report(devices, subnet)

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
                "mode": "nmap+ping" if use_nmap else "ping",
                "devices": devices,
            }, f, indent=2, ensure_ascii=False)

        print(f"  📄 Результат сохранён: {filepath}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
