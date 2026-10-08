"""
Сканер сети — поиск принтеров.
Работает на Linux (nmap) и Windows (только ping + порты).
"""
import ipaddress
import socket
import re
import shutil
import yaml
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger
from app.core.oui import lookup_vendor

logger = setup_logger("printer-scanner")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
AUTO_CONFIG = PROJECT_ROOT / "config" / "printers_auto.yaml"


def has_nmap() -> bool:
    return shutil.which("nmap") is not None


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def get_subnet(local_ip: str, prefix: int = 24) -> str:
    try:
        return str(ipaddress.ip_network(f"{local_ip}/{prefix}", strict=False))
    except Exception:
        return ""


def parse_subnet(subnet: str) -> list:
    try:
        network = ipaddress.ip_network(subnet, strict=False)
        return [str(ip) for ip in network.hosts()]
    except Exception:
        return []


def ping_host(ip: str, timeout: int = 1) -> bool:
    if os_detector.is_windows:
        cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
    rc, _, _ = os_detector.run_command(cmd)
    return rc == 0


def check_port(ip: str, port: int, timeout: float = 0.5) -> bool:
    """Проверяет открыт ли порт."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        rc = sock.connect_ex((ip, port))
        sock.close()
        return rc == 0
    except Exception:
        return False


def is_printer(ip: str) -> bool:
    """Проверяет, является ли устройство принтером (по портам)."""
    printer_ports = [9100, 515, 631]
    for port in printer_ports:
        if check_port(ip, port):
            return True
    return False


def get_mac(ip: str) -> str:
    if os_detector.is_windows:
        os_detector.run_command(["ping", "-n", "1", "-w", "500", ip])
        rc, stdout, _ = os_detector.run_command(["arp", "-a", ip])
        if rc != 0:
            rc, stdout, _ = os_detector.run_command(["arp", "-a"])
    else:
        os_detector.run_command(["ping", "-c", "1", "-W", "1", ip])
        rc, stdout, _ = os_detector.run_command(["arp", "-n", ip])
        if rc != 0:
            rc, stdout, _ = os_detector.run_command(["ip", "neigh"])

    try:
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


def query_snmp_printer(ip: str, community: str = "public", timeout: int = 2) -> dict:
    """SNMP-запрос модели принтера."""
    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData,
            UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity,
        )
    except ImportError:
        return None

    oid_model = "1.3.6.1.2.1.25.3.2.1.3.1"
    oid_status = "1.3.6.1.2.1.25.3.2.1.5.1"

    try:
        error_indication, error_status, _, var_binds = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ip, 161), timeout=timeout, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(oid_model)),
                ObjectType(ObjectIdentity(oid_status)),
            )
        )
        if error_indication or error_status:
            return None

        model = var_binds[0][1].prettyPrint()
        if not model or "No Such" in model:
            return None
        return {"ip": ip, "model": model}
    except Exception:
        return None


def scan_subnet(subnet: str, community: str = "public") -> list:
    """Сканирует подсеть на принтеры."""
    hosts = parse_subnet(subnet)
    total = len(hosts)
    print(f"  🔍 Сканирование {subnet} ({total} адресов)")
    print()

    printers = []

    for i, ip in enumerate(hosts, start=1):
        if i % 20 == 0 or i == total:
            print(f"  Проверено: {i}/{total} | Найдено: {len(printers)}")

        # Быстрая проверка — пингуем
        if not ping_host(ip, timeout=1):
            continue

        # Проверяем порты принтера
        if not is_printer(ip):
            continue

        # SNMP-запрос
        data = query_snmp_printer(ip, community=community)
        if not data:
            data = {"ip": ip, "model": "unknown (порты принтера открыты)"}

        # MAC
        mac = get_mac(ip)
        vendor = lookup_vendor(mac) if mac else ""

        data["mac"] = mac
        data["vendor"] = vendor
        printers.append(data)

        print(f"     ✅ {ip} — {data['model']}")

    return printers


def save_auto_config(printers: list) -> Path:
    data = {
        "generated_at": datetime.now().isoformat(),
        "printers": [
            {
                "name": f"Принтер {p['ip']}" + (f" ({p['vendor']})" if p.get("vendor") else ""),
                "ip": p["ip"],
                "model": p["model"],
                "location": "Авто-обнаружено",
                "snmp_community": "public",
                "mac": p.get("mac", ""),
                "vendor": p.get("vendor", ""),
                "enabled": True,
            }
            for p in printers
        ],
    }
    with open(AUTO_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    return AUTO_CONFIG


def run():
    print()
    print("=" * 60)
    print("  СКАНЕР СЕТИ — ПОИСК ПРИНТЕРОВ")
    print("=" * 60)
    print()

    local_ip = get_local_ip()
    if not local_ip:
        print("  ❌ Не удалось определить IP")
        input("  Нажми Enter...")
        return

    print(f"  Твой IP: {local_ip}")
    subnet = get_subnet(local_ip, prefix=24)
    print(f"  Подсеть: {subnet}")
    print()

    answer = input(f"  Сканировать {subnet}? [y/N]: ").strip().lower()
    if answer != "y":
        custom = input("  Введи свою подсеть: ").strip()
        if not custom:
            return
        subnet = custom

    print()
    print("  ⚠️  Может занять 1-5 минут.")
    confirm = input("  Начать? [y/N]: ").strip().lower()
    if confirm != "y":
        return

    print()

    try:
        printers = scan_subnet(subnet)
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        logger.exception("Сканер принтеров упал")
        input("  Нажми Enter...")
        return

    print()
    print("=" * 60)
    print(f"  НАЙДЕНО: {len(printers)}")
    print("=" * 60)

    if not printers:
        print("  Принтеры не найдены.")
        input("  Нажми Enter...")
        return

    for p in printers:
        vendor = f" [{p['vendor']}]" if p.get("vendor") else ""
        print(f"  🖨️  {p['ip']} — {p['model']}{vendor}")

    print()
    save = input("  Сохранить? [Y/n]: ").strip().lower()
    if save != "n":
        path = save_auto_config(printers)
        print(f"  ✅ Сохранено: {path}")

    print()
    input("  Нажми Enter...")


if __name__ == "__main__":
    run()
