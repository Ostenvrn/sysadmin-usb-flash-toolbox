"""
Карта сети — визуализация.
Читает результаты сканирования (output/scans/network_*.json)
и строит текстовую карту + HTML с интерактивностью.

Улучшенное распознавание устройств:
- hostname (reverse DNS)
- MAC + OUI (производитель)
- открытые порты (9100, 515, 631 → принтер; 22 → Linux; 3389 → Windows)
"""
import json
import socket
import shutil
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("network-map")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
SCANS_DIR = PROJECT_ROOT / "output" / "scans"
MAPS_DIR = PROJECT_ROOT / "output" / "maps"


# =====================================================================
# База OUI (производители MAC)
# Формат: первые 6 hex-символов MAC → производитель
# =====================================================================
OUI_DB = {
    # Apple
    "001B63": "Apple", "001EC2": "Apple", "3C0754": "Apple",
    "F4F5D8": "Apple", "0018E7": "Apple", "000D93": "Apple",
    "00248C": "Apple", "0026B0": "Apple", "28CFE9": "Apple",
    "40A6D9": "Apple", "6C709F": "Apple", "8C8590": "Apple",
    # Raspberry Pi
    "B827EB": "Raspberry Pi", "DCA632": "Raspberry Pi", "E45F01": "Raspberry Pi",
    # Xiaomi
    "286C07": "Xiaomi", "3C47D4": "Xiaomi", "64CC2E": "Xiaomi",
    "F8A45F": "Xiaomi", "78 11 DC": "Xiaomi",
    # Samsung
    "001632": "Samsung", "002454": "Samsung", "5C0A5B": "Samsung",
    "84 25 DB": "Samsung", "D0176A": "Samsung",
    # Huawei
    "00259E": "Huawei", "002568": "Huawei", "104780": "Huawei",
    "24DBAC": "Huawei", "4C1FCC": "Huawei",
    # TP-Link
    "001D0F": "TP-Link", "002127": "TP-Link", "14CC20": "TP-Link",
    "3C46D8": "TP-Link", "50C7BF": "TP-Link", "9C532D": "TP-Link",
    # D-Link
    "001195": "D-Link", "001CF0": "D-Link", "1CBDB9": "D-Link",
    "340804": "D-Link", "78542E": "D-Link",
    # Asus
    "001BFC": "Asus", "002215": "Asus", "08606E": "Asus",
    "1C872C": "Asus", "2C56DC": "Asus", "50465D": "Asus",
    # HP
    "001321": "HP", "001E0B": "HP", "002481": "HP",
    "3C4A92": "HP", "9457A5": "HP",
    # Canon
    "001E8F": "Canon", "00248C": "Canon", "888717": "Canon",
    # Epson
    "000048": "Epson", "44D244": "Epson", "A4EE57": "Epson",
    # Kyocera
    "0027 13": "Kyocera", "40 16 7E": "Kyocera",
    # Intel
    "001B21": "Intel", "3C970E": "Intel", "7C7A91": "Intel",
    # Realtek
    "00E04C": "Realtek", "52540 0": "Realtek",
    # Netgear
    "000FB5": "Netgear", "204E7F": "Netgear", "A00460": "Netgear",
    # Mikrotik
    "4C5E0C": "Mikrotik", "6C3B6B": "Mikrotik", "CC2DE0": "Mikrotik",
    # Ubiquiti
    "002722": "Ubiquiti", "0418D6": "Ubiquiti", "24A43C": "Ubiquiti",
    # VMware
    "000C29": "VMware", "005056": "VMware",
    # VirtualBox
    "080027": "VirtualBox",
    # QEMU/KVM
    "525400": "QEMU",
}


# =====================================================================
# Определение типа устройства
# =====================================================================

def guess_device_type(device: dict) -> str:
    """
    Определяет тип устройства по hostname, MAC, портам.
    Возвращает строку с иконкой и типом.
    """
    hostname = (device.get("hostname") or "").lower()
    mac = (device.get("mac") or "").upper().replace("-", ":").replace(".", "")
    ports = device.get("open_ports", []) or []

    # === 1. По hostname ===
    if any(x in hostname for x in ["router", "gateway", "gw", "роутер", "mikrotik"]):
        return "🌐 Роутер"
    if any(x in hostname for x in ["printer", "hp", "canon", "epson", "kyocera", "принтер", "mfp"]):
        return "🖨️ Принтер"
    if any(x in hostname for x in ["nas", "synology", "qnap", "freenas"]):
        return "💾 NAS"
    if any(x in hostname for x in ["server", "srv", "сервер"]):
        return "🖥️ Сервер"
    if any(x in hostname for x in ["phone", "iphone", "android", "телефон", "samsung", "xiaomi", "redmi", "huawei"]):
        return "📱 Телефон"
    if any(x in hostname for x in ["laptop", "notebook", "ноут", "lenovo", "asus", "acer"]):
        return "💻 Ноутбук"
    if any(x in hostname for x in ["desktop", "pc", "пк", "win-", "win "]):
        return "🖥️ ПК"
    if any(x in hostname for x in ["tv", "smarttv", "телевизор"]):
        return "📺 ТВ"

    # === 2. По открытым портам ===
    if ports:
        # Принтеры: 9100 (raw), 515 (LPD), 631 (IPP)
        if 9100 in ports or 515 in ports or 631 in ports:
            return "🖨️ Принтер"
        # NAS: 5000 (Synology), 8080+WebDAV, 21 (FTP)
        if 5000 in ports and 5001 in ports:
            return "💾 NAS"
        # Windows: 135, 139, 445
        if 445 in ports or 3389 in ports:
            return "🖥️ ПК (Windows)"
        # Linux сервер: 22 + 80/443
        if 22 in ports and (80 in ports or 443 in ports):
            return "🖥️ Сервер (Linux)"
        # Linux ПК: только 22
        if 22 in ports:
            return "🖥️ ПК (Linux)"
        # Веб-камера/устройство с 80/443
        if 80 in ports or 443 in ports:
            return "🌐 Устройство с веб-интерфейсом"

    # === 3. По MAC (OUI) ===
    if mac and len(mac) >= 6:
        oui = mac.replace(":", "")[:6].upper()
        if oui in OUI_DB:
            vendor = OUI_DB[oui]
            # По производителю угадываем тип
            if vendor == "Apple":
                return "📱 Apple"
            if vendor == "Raspberry Pi":
                return "🍓 Raspberry Pi"
            if vendor == "Xiaomi":
                return "📱 Xiaomi"
            if vendor == "Samsung":
                return "📱 Samsung"
            if vendor == "Huawei":
                return "📱 Huawei"
            if vendor in ("TP-Link", "D-Link", "Asus", "Netgear", "Mikrotik", "Ubiquiti"):
                return f"🌐 {vendor} (роутер?)"
            if vendor in ("HP", "Canon", "Epson", "Kyocera"):
                return f"🖨️ {vendor} (принтер?)"
            if vendor == "VMware":
                return "☁️ VMware VM"
            if vendor == "VirtualBox":
                return "☁️ VirtualBox VM"
            if vendor == "QEMU":
                return "☁️ QEMU VM"
            if vendor == "Intel":
                return "🖥️ ПК (Intel)"
            return f"❓ {vendor}"

    # === 4. Неизвестно ===
    return "❓ Неизвестно"


def get_gateway() -> str:
    """Определяет IP шлюза (роутера)."""
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
                    if gw:
                        return gw
    return ""


# =====================================================================
# Текстовая карта
# =====================================================================

def print_text_map(devices: list, subnet: str, local_ip: str, gateway: str):
    """Строит текстовую карту сети."""
    print()
    print("=" * 80)
    print("  КАРТА СЕТИ")
    print("=" * 80)
    print(f"  Подсеть: {subnet}")
    print(f"  Устройств: {len(devices)}")
    print()

    if gateway:
        print(f"  ┌─────────────────────────────────────────────────────┐")
        print(f"  │  🌐 РОУТЕР: {gateway:<20}                  │")
        print(f"  └─────────────────────────────────────────────────────┘")
        print()

    print(f"  ┌─────────────────────────────────────────────────────┐")
    print(f"  │  💻 ТЫ: {local_ip:<20}                      │")
    print(f"  └─────────────────────────────────────────────────────┘")
    print()

    if not devices:
        print("  Нет других устройств.")
        return

    devices_sorted = sorted(
        devices,
        key=lambda d: tuple(int(x) for x in d["ip"].split("."))
    )

    by_type = {}
    for d in devices_sorted:
        dtype = guess_device_type(d)
        by_type.setdefault(dtype, []).append(d)

    for dtype, devs in sorted(by_type.items()):
        print(f"  {dtype} ({len(devs)})")
        print("  " + "─" * 70)
        for d in devs:
            ip = d["ip"]
            hostname = d.get("hostname") or "—"
            mac = d.get("mac") or "—"
            marker = ""
            if ip == local_ip:
                marker = " ← (ты)"
            elif ip == gateway:
                marker = " ← (роутер)"
            print(f"     ├─ {ip:<16}{marker}")
            print(f"     │  Hostname: {hostname}")
            print(f"     │  MAC:      {mac}")
        print()


# =====================================================================
# Скачивание vis-network
# =====================================================================

def _download_vis_network(target: Path) -> bool:
    """Скачивает vis-network.min.js с unpkg.com."""
    import urllib.request
    url = "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sysadmin-usb/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
        with open(target, "wb") as f:
            f.write(data)
        logger.info(f"vis-network.min.js скачан: {target}")
        return True
    except Exception as e:
        logger.error(f"Ошибка скачивания vis-network.min.js: {e}")
        return False


# =====================================================================
# HTML-карта
# =====================================================================

def generate_html_map(devices: list, subnet: str, local_ip: str,
                      gateway: str) -> Path:
    """Генерирует HTML-карту с интерактивностью."""
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = MAPS_DIR / f"network_map_{timestamp}.html"

    # --- Копируем vis-network.min.js ---
    js_source = PROJECT_ROOT / "app" / "ui" / "web" / "static" / "js" / "vis-network.min.js"
    js_dest = MAPS_DIR / "vis-network.min.js"

    if not js_source.exists():
        print("  ⚠️  vis-network.min.js не найден, скачиваю...")
        js_source.parent.mkdir(parents=True, exist_ok=True)
        _download_vis_network(js_source)

    if js_source.exists():
        shutil.copy(js_source, js_dest)
        logger.info(f"vis-network.min.js скопирован в {js_dest}")
    else:
        print("  ❌ Не удалось получить vis-network.min.js")
        print("     Скачай вручную:")
        print(f"     curl -L -o {js_source} "
              "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js")

    # =================================================================
    # Формируем узлы и рёбра
    # =================================================================
    nodes = []
    edges = []

    # 1. Роутер
    if gateway:
        nodes.append({
            "id": gateway,
            "label": f"🌐 Роутер\n{gateway}",
            "group": "router",
            "title": f"Роутер (шлюз)\nIP: {gateway}",
            "size": 40,
        })

    # 2. Твой ПК
    nodes.append({
        "id": local_ip,
        "label": f"💻 ТЫ\n{local_ip}",
        "group": "you",
        "title": f"Твой ПК\nIP: {local_ip}",
        "size": 35,
    })

    # 3. Устройства
    for d in devices:
        ip = d["ip"]
        if ip == local_ip or ip == gateway:
            continue

        dtype = guess_device_type(d)
        hostname = d.get("hostname") or ip
        mac = d.get("mac") or "—"
        ports = d.get("open_ports", []) or []

        # Формируем tooltip
        tooltip_parts = [dtype, f"IP: {ip}"]
        if hostname and hostname != ip:
            tooltip_parts.append(f"Hostname: {hostname}")
        if mac and mac != "—":
            tooltip_parts.append(f"MAC: {mac}")
        if ports:
            tooltip_parts.append(f"Порты: {', '.join(map(str, ports[:10]))}")

        # Группа для цвета (первый символ emoji)
        group_key = dtype.split()[0] if dtype else "unknown"

        nodes.append({
            "id": ip,
            "label": f"{dtype}\n{ip}",
            "group": group_key,
            "title": "\n".join(tooltip_parts),
        })

    # 4. Рёбра
    if gateway:
        edges.append({"from": gateway, "to": local_ip})
        for d in devices:
            if d["ip"] != local_ip and d["ip"] != gateway:
                edges.append({"from": gateway, "to": d["ip"]})
    else:
        for d in devices:
            if d["ip"] != local_ip:
                edges.append({"from": local_ip, "to": d["ip"]})

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    edges_json = json.dumps(edges, ensure_ascii=False)
    gateway_json = json.dumps(gateway, ensure_ascii=False)
    local_ip_json = json.dumps(local_ip, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Карта сети — {subnet}</title>
    <script src="vis-network.min.js"></script>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }}
        header {{
            padding: 15px 20px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }}
        h1 {{
            margin: 0;
            font-size: 22px;
            color: #58a6ff;
        }}
        .info {{
            margin-top: 6px;
            font-size: 13px;
            color: #8b949e;
        }}
        .content {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}
        #network {{
            flex: 1;
            height: 100%;
        }}
        .sidebar {{
            width: 340px;
            background: #161b22;
            border-left: 1px solid #30363d;
            padding: 20px;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            margin: 0 0 15px 0;
            font-size: 16px;
            color: #58a6ff;
        }}
        .sidebar .hint {{
            color: #8b949e;
            font-size: 13px;
            font-style: italic;
        }}
        .device-item {{
            padding: 10px;
            background: #21262d;
            border-radius: 6px;
            margin-bottom: 8px;
            border-left: 3px solid #58a6ff;
        }}
        .device-item .name {{
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 4px;
        }}
        .device-item .ip {{
            font-family: monospace;
            color: #8b949e;
            font-size: 12px;
        }}
        .device-item .mac {{
            font-family: monospace;
            color: #6e7681;
            font-size: 11px;
            margin-top: 2px;
        }}
        .legend {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 12px 15px;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
        }}
        .legend h3 {{
            margin: 0 0 8px 0;
            font-size: 13px;
            color: #58a6ff;
        }}
        .legend div {{
            margin: 3px 0;
        }}
    </style>
</head>
<body>
    <header>
        <h1>🗺️ Карта сети</h1>
        <div class="info">
            Подсеть: <b>{subnet}</b> |
            Устройств: <b>{len(devices)}</b> |
            Шлюз: <b>{gateway or "не найден"}</b> |
            Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        </div>
    </header>
    <div class="content">
        <div id="network"></div>
        <div class="sidebar">
            <h2>📋 Информация</h2>
            <div id="info-panel">
                <p class="hint">Кликни по узлу на карте, чтобы увидеть подробности и подключённые устройства.</p>
            </div>
        </div>
    </div>
    <div class="legend">
        <h3>Легенда</h3>
        <div>🌐 Роутер</div>
        <div>💻 Твой ПК</div>
        <div>🖨️ Принтер</div>
        <div>🖥️ Сервер / ПК</div>
        <div>📱 Телефон / Apple / Samsung</div>
        <div>💾 NAS</div>
        <div>🍓 Raspberry Pi</div>
        <div>☁️ Виртуалка</div>
        <div>❓ Неизвестно</div>
    </div>

    <script>
        var allNodes = {nodes_json};
        var allEdges = {edges_json};
        var gateway = {gateway_json};
        var localIp = {local_ip_json};

        var nodes = new vis.DataSet(allNodes);
        var edges = new vis.DataSet(allEdges);
        var container = document.getElementById('network');
        var data = {{ nodes: nodes, edges: edges }};

        var options = {{
            nodes: {{
                shape: 'box',
                font: {{ color: '#c9d1d9', size: 13, face: 'Segoe UI' }},
                borderWidth: 2,
                margin: 12,
            }},
            edges: {{
                color: {{ color: '#30363d', highlight: '#58a6ff' }},
                width: 1,
                smooth: {{ type: 'continuous' }},
            }},
            groups: {{
                'router': {{ color: {{ background: '#238636', border: '#3fb950' }}, shape: 'hexagon' }},
                'you': {{ color: {{ background: '#1f6feb', border: '#58a6ff' }} }},
                '🌐': {{ color: {{ background: '#238636', border: '#3fb950' }} }},
                '🖨️': {{ color: {{ background: '#6e40c9', border: '#a371f7' }} }},
                '🖥️': {{ color: {{ background: '#9e6a03', border: '#d29922' }} }},
                '📱': {{ color: {{ background: '#1f6feb', border: '#58a6ff' }} }},
                '💾': {{ color: {{ background: '#0d419d', border: '#58a6ff' }} }},
                '🍓': {{ color: {{ background: '#bf3989', border: '#ff7b72' }} }},
                '☁️': {{ color: {{ background: '#484f58', border: '#8b949e' }} }},
                '❓': {{ color: {{ background: '#484f58', border: '#8b949e' }} }},
            }},
            physics: {{
                stabilization: {{ iterations: 200 }},
                barnesHut: {{ gravitationalConstant: -4000, springLength: 180 }},
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }},
        }};

        var network = new vis.Network(container, data, options);

        network.on('click', function(params) {{
            var infoPanel = document.getElementById('info-panel');

            if (params.nodes.length === 0) {{
                infoPanel.innerHTML = '<p class="hint">Кликни по узлу на карте, чтобы увидеть подробности и подключённые устройства.</p>';
                return;
            }}

            var clickedId = params.nodes[0];
            var clickedNode = nodes.get(clickedId);
            var connectedIds = network.getConnectedNodes(clickedId);

            var html = '';
            html += '<div class="device-item">';
            html += '<div class="name">' + clickedNode.label.replace('\\n', ' — ') + '</div>';
            html += '<div class="ip">IP: ' + clickedNode.id + '</div>';
            if (clickedNode.title) {{
                var titleParts = clickedNode.title.split('\\n');
                for (var i = 1; i < titleParts.length; i++) {{
                    html += '<div class="mac">' + titleParts[i] + '</div>';
                }}
            }}
            html += '</div>';

            if (clickedId === gateway) {{
                html += '<h2 style="margin-top:20px;">🔌 Подключено устройств: ' + connectedIds.length + '</h2>';
            }} else if (clickedId === localIp) {{
                html += '<h2 style="margin-top:20px;">🔌 Соседи в сети: ' + connectedIds.length + '</h2>';
            }} else {{
                html += '<h2 style="margin-top:20px;">🔗 Связано с:</h2>';
            }}

            connectedIds.forEach(function(id) {{
                var n = nodes.get(id);
                if (!n) return;
                html += '<div class="device-item">';
                html += '<div class="name">' + n.label.replace('\\n', ' — ') + '</div>';
                html += '<div class="ip">IP: ' + n.id + '</div>';
                html += '</div>';
            }});

            infoPanel.innerHTML = html;
        }});
    </script>
</body>
</html>
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML-карта сохранена: {filepath}")
    return filepath


# =====================================================================
# Загрузка последнего сканирования
# =====================================================================

def load_last_scan() -> dict:
    """Загружает последний результат сканирования."""
    if not SCANS_DIR.exists():
        return {}

    files = sorted(SCANS_DIR.glob("network_*.json"), reverse=True)
    if not files:
        return {}

    try:
        with open(files[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения {files[0]}: {e}")
        return {}


# =====================================================================
# Точка входа
# =====================================================================

def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  КАРТА СЕТИ")
    print("=" * 80)
    print()

    data = load_last_scan()

    if not data:
        print("  Нет данных сканирования.")
        print("  Сначала запусти «Сканирование подсети».")
        print()
        input("  Нажми Enter для продолжения...")
        return

    devices = data.get("devices", [])
    subnet = data.get("subnet", "unknown")
    scanned_at = data.get("scanned_at", "")

    print(f"  Данные из сканирования: {scanned_at}")
    print(f"  Подсеть: {subnet}")
    print(f"  Устройств: {len(devices)}")
    print()

    local_ip = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    gateway = get_gateway()
    print(f"  Твой IP: {local_ip}")
    print(f"  Шлюз (роутер): {gateway or 'не найден'}")
    print()

    print_text_map(devices, subnet, local_ip, gateway)

    print()
    save = input("  Сгенерировать HTML-карту для браузера? [Y/n]: ").strip().lower()
    if save != "n":
        html_path = generate_html_map(devices, subnet, local_ip, gateway)
        print()
        print(f"  ✅ HTML-карта: {html_path}")
        print()
        print(f"  Открой в браузере:")
        print(f"     xdg-open {html_path}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
