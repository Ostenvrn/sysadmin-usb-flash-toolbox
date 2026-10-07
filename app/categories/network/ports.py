"""
Сканирование портов.
Проверяет, какие порты открыты на хосте.
Использует socket (без nmap).
"""
import socket
import concurrent.futures
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("network-ports")


# =====================================================================
# Список популярных портов с описанием
# =====================================================================
POPULAR_PORTS = {
    20: "FTP (данные)",
    21: "FTP (управление)",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    465: "SMTPS",
    587: "SMTP (submission)",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8080: "HTTP-alt",
    8443: "HTTPS-alt",
    27017: "MongoDB",
}


# Диапазоны портов для быстрого сканирования
PORT_RANGES = {
    "1": ("Популярные (25 портов)", list(POPULAR_PORTS.keys())),
    "2": ("Веб-порты (80, 443, 8080, 8443)", [80, 443, 8080, 8443]),
    "3": ("Только важные (22, 80, 443, 3389)", [22, 80, 443, 3389]),
    "4": ("1-1024 (стандартные)", list(range(1, 1025))),
    "5": ("1-10000 (расширенные)", list(range(1, 10001))),
}


# =====================================================================
# Сканирование
# =====================================================================

def check_port(host: str, port: int, timeout: float = 0.5) -> bool:
    """Проверяет, открыт ли порт."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        rc = sock.connect_ex((host, port))
        sock.close()
        return rc == 0
    except Exception:
        return False


def scan_ports(host: str, ports: list, timeout: float = 0.5,
               max_workers: int = 100) -> list:
    """Сканирует список портов. Возвращает открытые."""
    open_ports = []

    print(f"  🔍 Сканирование {len(ports)} портов на {host}...")
    print(f"  Параллельных потоков: {max_workers}")
    print()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_port, host, port, timeout): port for port in ports}

        done = 0
        total = len(ports)

        for future in concurrent.futures.as_completed(futures):
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  Проверено: {done}/{total} | Открыто: {len(open_ports)}")

            port = futures[future]
            if future.result():
                open_ports.append(port)

    return sorted(open_ports)


def get_service_name(port: int) -> str:
    """Возвращает имя сервиса для порта."""
    if port in POPULAR_PORTS:
        return POPULAR_PORTS[port]
    try:
        return socket.getservbyport(port)
    except Exception:
        return "unknown"


# =====================================================================
# Оценка безопасности
# =====================================================================

def analyze_security(open_ports: list) -> list:
    """Анализирует открытые порты на предмет рисков."""
    warnings = []

    dangerous = {
        21: "FTP — передача данных без шифрования",
        23: "Telnet — передача данных без шифрования",
        135: "RPC — часто используется для атак",
        139: "NetBIOS — устаревший, небезопасный",
        445: "SMB — уязвим к EternalBlue и др.",
        1433: "MSSQL — база данных, должна быть закрыта",
        3306: "MySQL — база данных, должна быть закрыта",
        3389: "RDP — цель для брутфорса",
        5432: "PostgreSQL — база данных, должна быть закрыта",
        5900: "VNC — часто без пароля",
        6379: "Redis — часто без пароля",
        27017: "MongoDB — часто без пароля",
    }

    for port in open_ports:
        if port in dangerous:
            warnings.append(f"🔴 Порт {port}: {dangerous[port]}")

    return warnings


# =====================================================================
# Вывод
# =====================================================================

def print_report(host: str, open_ports: list, warnings: list):
    """Красивый вывод результата."""
    print()
    print("=" * 70)
    print("  РЕЗУЛЬТАТ СКАНИРОВАНИЯ ПОРТОВ")
    print("=" * 70)
    print(f"  Хост: {host}")
    print(f"  Открытых портов: {len(open_ports)}")
    print()

    if not open_ports:
        print("  Открытых портов не найдено.")
        return

    for port in open_ports:
        service = get_service_name(port)
        print(f"  🟢 Порт {port:<6} — {service}")

    # Оценка безопасности
    if warnings:
        print()
        print("-" * 70)
        print("  ⚠️  ВНИМАНИЕ (безопасность):")
        print("-" * 70)
        for w in warnings:
            print(f"  {w}")
        print()
        print("  💡 РЕКОМЕНДАЦИИ:")
        print("     • Закройте ненужные порты через firewall")
        print("     • Используйте SSH вместо Telnet")
        print("     • Ограничьте доступ к базам данных по IP")
        print("     • Не используйте RDP без VPN")


# =====================================================================
# Точка входа
# =====================================================================

def run():
    """Точка входа."""
    print()
    print("=" * 70)
    print("  СКАНИРОВАНИЕ ПОРТОВ")
    print("=" * 70)
    print()

    # Хост
    host = input("  Хост (IP или домен, Enter = localhost): ").strip()
    if not host:
        host = "127.0.0.1"

    print()
    print(f"  Цель: {host}")
    print()

    # Выбор диапазона
    print("  Выбери диапазон портов:")
    for key, (name, _) in PORT_RANGES.items():
        print(f"    [{key}] {name} ({len(PORT_RANGES[key][1])} портов)")
    print("    [0] ← Назад")
    print()

    choice = input("  Ваш выбор: ").strip()

    if choice == "0":
        return

    if choice not in PORT_RANGES:
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    range_name, ports = PORT_RANGES[choice]

    print()
    print(f"  Диапазон: {range_name}")
    print()

    # Предупреждение для больших диапазонов
    if len(ports) > 1000:
        print(f"  ⚠️  {len(ports)} портов — может занять несколько минут.")
        confirm = input("  Продолжить? [Y/n]: ").strip().lower()
        if confirm == "n":
            return
        print()

    # Сканируем
    open_ports = scan_ports(host, ports, timeout=0.5)

    # Анализ безопасности
    warnings = analyze_security(open_ports)

    # Вывод
    print_report(host, open_ports, warnings)

    # Сохранение
    if open_ports:
        import json
        from pathlib import Path
        output_dir = Path(__file__).parent.parent.parent.parent / "output" / "scans"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = output_dir / f"ports_{host.replace('.', '_')}_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "host": host,
                "scanned_at": datetime.now().isoformat(),
                "range": range_name,
                "open_ports": [
                    {"port": p, "service": get_service_name(p)} for p in open_ports
                ],
                "warnings": warnings,
            }, f, indent=2, ensure_ascii=False)

        print()
        print(f"  📄 Результат сохранён: {filepath}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
