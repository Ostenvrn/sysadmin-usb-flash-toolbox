"""
Сканер сети — автоматический поиск принтеров.
Сканирует подсеть на порт 161 (SNMP), проверяет SNMP-ответ,
сохраняет найденные принтеры в config/printers_auto.yaml.
"""
import ipaddress
import socket
import yaml
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("printer-scanner")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
AUTO_CONFIG = PROJECT_ROOT / "config" / "printers_auto.yaml"


# =====================================================================
# Вспомогательные функции
# =====================================================================

def get_local_ip() -> str:
    """
    Определяет IP-адрес текущего ПК в локальной сети.
    Использует трюк: подключается к 8.8.8.8 (UDP), смотрит свой адрес.
    Пакеты не отправляются — только определяется интерфейс.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Не удалось определить локальный IP: {e}")
        return ""


def get_subnet(local_ip: str, prefix: int = 24) -> str:
    """
    Превращает IP в подсеть.
    Например: 192.168.1.55 + 24 → 192.168.1.0/24
    """
    try:
        network = ipaddress.ip_network(f"{local_ip}/{prefix}", strict=False)
        return str(network)
    except Exception as e:
        logger.error(f"Не удалось определить подсеть: {e}")
        return ""


def parse_subnet(subnet: str) -> list:
    """
    Возвращает список IP-адресов в подсети.
    Для /24 это 254 адреса (без .0 и .255).
    """
    try:
        network = ipaddress.ip_network(subnet, strict=False)
        # Исключаем адрес сети и broadcast
        hosts = [str(ip) for ip in network.hosts()]
        return hosts
    except Exception as e:
        logger.error(f"Ошибка парсинга подсети {subnet}: {e}")
        return []


# =====================================================================
# Сканирование
# =====================================================================

def scan_host_snmp(ip: str, timeout: int = 2) -> bool:
    """
    Проверяет, отвечает ли хост по SNMP (порт 161).
    Возвращает True, если SNMP доступен.
    """
    try:
        # Сначала быстрая проверка порта 161
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        # Отправляем пустой пакет — если порт открыт, ответа не будет,
        # но ошибка "connection refused" не придёт (UDP).
        # Поэтому используем отдельную проверку через nmap.
        sock.close()
    except Exception:
        pass

    # Используем nmap для проверки порта 161
    try:
        import nmap
        nm = nmap.PortScanner()
        nm.scan(hosts=ip, ports="161", arguments="-sU -Pn --host-timeout 5s")
        if ip in nm.all_hosts():
            if "udp" in nm[ip] and 161 in nm[ip]["udp"]:
                state = nm[ip]["udp"][161]["state"]
                return state in ("open", "open|filtered")
    except ImportError:
        logger.error("python-nmap не установлен")
        return False
    except Exception as e:
        logger.debug(f"nmap ошибка для {ip}: {e}")

    return False


def query_snmp_printer(ip: str, community: str = "public", timeout: int = 2) -> dict:
    """
    Пробует SNMP-запрос к хосту. Если отвечает с моделью принтера —
    возвращает данные, иначе None.
    """
    try:
        from pysnmp.hlapi import (
            getCmd, SnmpEngine, CommunityData,
            UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity,
        )
    except ImportError:
        return None

    # OID модели принтера (стандарт Printer MIB)
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
        status_code = var_binds[1][1].prettyPrint()

        # Если модель пустая или "No Such Object" — это не принтер
        if not model or "No Such" in model:
            return None

        return {
            "ip": ip,
            "model": model,
            "status_code": status_code,
        }
    except Exception as e:
        logger.debug(f"SNMP ошибка для {ip}: {e}")
        return None


def scan_subnet(subnet: str, community: str = "public") -> list:
    """
    Сканирует подсеть, возвращает список найденных принтеров.
    """
    hosts = parse_subnet(subnet)
    total = len(hosts)
    logger.info(f"Сканирование подсети {subnet} ({total} адресов)")

    print(f"  🔍 Сканирование подсети {subnet}")
    print(f"  Всего адресов: {total}")
    print()

    printers = []
    for i, ip in enumerate(hosts, start=1):
        # Прогресс каждые 20 адресов
        if i % 20 == 0 or i == total:
            print(f"  Проверено: {i}/{total} | Найдено: {len(printers)}")

        # Шаг 1: проверяем SNMP-порт
        if not scan_host_snmp(ip):
            continue

        # Шаг 2: пробуем SNMP-запрос
        data = query_snmp_printer(ip, community=community)
        if data:
            printers.append(data)
            print(f"     ✅ Найден принтер: {ip} — {data['model']}")

    return printers


# =====================================================================
# Сохранение
# =====================================================================

def save_auto_config(printers: list) -> Path:
    """Сохраняет найденные принтеры в config/printers_auto.yaml."""
    data = {
        "generated_at": datetime.now().isoformat(),
        "printers": [
            {
                "name": f"Принтер {p['ip']}",
                "ip": p["ip"],
                "model": p["model"],
                "location": "Авто-обнаружено",
                "snmp_community": "public",
                "enabled": True,
            }
            for p in printers
        ],
    }

    with open(AUTO_CONFIG, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    logger.info(f"Автоконфиг сохранён: {AUTO_CONFIG}")
    return AUTO_CONFIG


# =====================================================================
# Точка входа
# =====================================================================

def run():
    """Точка входа для сканера сети."""
    print()
    print("=" * 60)
    print("  СКАНЕР СЕТИ — ПОИСК ПРИНТЕРОВ")
    print("=" * 60)
    print()

    # Определяем подсеть
    local_ip = get_local_ip()
    if not local_ip:
        print("  ❌ Не удалось определить IP. Проверь сеть.")
        return

    print(f"  Твой IP: {local_ip}")

    subnet = get_subnet(local_ip, prefix=24)
    print(f"  Подсеть: {subnet}")
    print()

    # Спрашиваем, сканировать ли эту подсеть
    answer = input(f"  Сканировать {subnet}? [y/N]: ").strip().lower()
    if answer != "y":
        custom = input("  Введи свою подсеть (например, 192.168.1.0/24): ").strip()
        if not custom:
            print("  Отмена.")
            return
        subnet = custom

    print()
    print("  ⚠️  Сканирование может занять 3-10 минут (254 адреса).")
    print("  ⚠️  Для /16 или /8 — очень долго! Используй /24.")
    print()

    confirm = input("  Начать? [y/N]: ").strip().lower()
    if confirm != "y":
        print("  Отмена.")
        return

    print()

    # Сканируем
    printers = scan_subnet(subnet, community="public")

    print()
    print("=" * 60)
    print(f"  НАЙДЕНО ПРИНТЕРОВ: {len(printers)}")
    print("=" * 60)
    print()

    if not printers:
        print("  Принтеры не найдены.")
        print("  Возможные причины:")
        print("    - SNMP выключен на принтерах")
        print("    - Другой SNMP community (не 'public')")
        print("    - Принтеры в другой подсети")
        return

    for p in printers:
        print(f"  🖨️  {p['ip']} — {p['model']}")

    print()

    # Сохраняем
    save = input("  Сохранить в config/printers_auto.yaml? [Y/n]: ").strip().lower()
    if save != "n":
        path = save_auto_config(printers)
        print()
        print(f"  ✅ Сохранено: {path}")
        print(f"  Теперь запусти «Мониторинг» — он подхватит эти принтеры.")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
