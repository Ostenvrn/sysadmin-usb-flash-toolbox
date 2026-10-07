"""
Карта сети — визуализация.
Читает результаты сканирования (output/scans/network_*.json)
и строит текстовую карту сети + генерирует HTML для браузера.
"""
import json
import socket
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("network-map")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
SCANS_DIR = PROJECT_ROOT / "output" / "scans"
MAPS_DIR = PROJECT_ROOT / "output" / "maps"


# =====================================================================
# Определение типа устройства
# =====================================================================

def guess_device_type(device: dict) -> str:
    """Пытается определить тип устройства по hostname и MAC."""
    hostname = (device.get("hostname") or "").lower()
    mac = (device.get("mac") or "").upper()

    # По hostname
    if any(x in hostname for x in ["router", "gateway", "gw", "роутер"]):
        return "🌐 Роутер"
    if any(x in hostname for x in ["printer", "hp", "canon", "epson", "kyocera", "принтер"]):
        return "🖨️ Принтер"
    if any(x in hostname for x in ["nas", "synology", "qnap"]):
        return "💾 NAS"
    if any(x in hostname for x in ["server", "srv", "сервер"]):
        return "🖥️ Сервер"
    if any(x in hostname for x in ["phone", "iphone", "android", "телефон"]):
        return "📱 Телефон"
    if any(x in hostname for x in ["laptop", "notebook", "ноут"]):
        return "💻 Ноутбук"
    if any(x in hostname for x in ["desktop", "pc", "пк"]):
        return "🖥️ ПК"

    # По MAC (производитель)
    if mac:
        # Первые 3 байта MAC = OUI (производитель)
        oui = mac.replace(":", "").replace("-", "")[:6].upper()

        # Известные производители
        known_oui = {
            "001B63": "Apple",
            "001E C2": "Apple",
            "3C0754": "Apple",
            "F4F5D8": "Apple",
            "0018E7": "Apple",
            "000D93": "Apple",
            "00248C": "Apple",
            "B827EB": "Raspberry Pi",
            "DCA632": "Raspberry Pi",
        }
        if oui in known_oui:
            return f"📱 {known_oui[oui]}"

    return "❓ Неизвестно"


# =====================================================================
# Текстовая карта
# =====================================================================

def print_text_map(devices: list, subnet: str, local_ip: str):
    """Строит текстовую карту сети."""
    print()
    print("=" * 80)
    print("  КАРТА СЕТИ")
    print("=" * 80)
    print(f"  Подсеть: {subnet}")
    print(f"  Устройств: {len(devices)}")
    print()

    # Центральный узел — твой ПК
    print(f"  ┌─────────────────────────────────────────────────────┐")
    print(f"  │  💻 ТЫ: {local_ip:<20}                     │")
    print(f"  └─────────────────────────────────────────────────────┘")
    print()

    if not devices:
        print("  Нет других устройств.")
        return

    # Сортируем
    devices_sorted = sorted(
        devices,
        key=lambda d: tuple(int(x) for x in d["ip"].split("."))
    )

    # Группируем по типу
    by_type = {}
    for d in devices_sorted:
        dtype = guess_device_type(d)
        by_type.setdefault(dtype, []).append(d)

    # Выводим по группам
    for dtype, devs in sorted(by_type.items()):
        print(f"  {dtype} ({len(devs)})")
        print("  " + "─" * 70)
        for d in devs:
            ip = d["ip"]
            hostname = d.get("hostname") or "—"
            mac = d.get("mac") or "—"
            marker = " ← (ты)" if ip == local_ip else ""
            print(f"     ├─ {ip:<16}{marker}")
            print(f"     │  Hostname: {hostname}")
            print(f"     │  MAC:      {mac}")
        print()


# =====================================================================
# HTML-карта (визуализация)
# =====================================================================

def generate_html_map(devices: list, subnet: str, local_ip: str) -> Path:
    """Генерирует HTML-карту сети (можно открыть в браузере)."""
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = MAPS_DIR / f"network_map_{timestamp}.html"

    # Формируем список устройств для JS
    nodes = []

    # Твой ПК — центр
    nodes.append({
        "id": local_ip,
        "label": f"💻 ТЫ\n{local_ip}",
        "group": "you",
        "title": f"Твой ПК\nIP: {local_ip}",
    })

    for d in devices:
        if d["ip"] == local_ip:
            continue
        dtype = guess_device_type(d)
        hostname = d.get("hostname") or d["ip"]
        mac = d.get("mac") or "—"

        nodes.append({
            "id": d["ip"],
            "label": f"{dtype}\n{d['ip']}",
            "group": dtype.split()[0] if dtype else "unknown",
            "title": f"{dtype}\nIP: {d['ip']}\nHostname: {hostname}\nMAC: {mac}",
        })

    # Рёбра: все к центральному узлу (звезда)
    edges = []
    for d in devices:
        if d["ip"] != local_ip:
            edges.append({"from": local_ip, "to": d["ip"]})

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Карта сети — {subnet}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{
            margin: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
        }}
        header {{
            padding: 20px;
            background: #161b22;
            border-bottom: 1px solid #30363d;
        }}
        h1 {{
            margin: 0;
            font-size: 24px;
            color: #58a6ff;
        }}
        .info {{
            margin-top: 8px;
            font-size: 14px;
            color: #8b949e;
        }}
        #network {{
            width: 100%;
            height: calc(100vh - 100px);
        }}
        .legend {{
            position: absolute;
            top: 120px;
            right: 20px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 15px;
            font-size: 13px;
        }}
        .legend h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #58a6ff;
        }}
        .legend div {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <header>
        <h1>🗺️ Карта сети</h1>
        <div class="info">
            Подсеть: <b>{subnet}</b> |
            Устройств: <b>{len(devices)}</b> |
            Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        </div>
    </header>
    <div id="network"></div>
    <div class="legend">
        <h3>Легенда</h3>
        <div>💻 Твой ПК</div>
        <div>🌐 Роутер</div>
        <div>🖨️ Принтер</div>
        <div>🖥️ Сервер / ПК</div>
        <div>📱 Телефон</div>
        <div>💾 NAS</div>
        <div>❓ Неизвестно</div>
    </div>
    <script>
        var nodes = new vis.DataSet({json.dumps(nodes, ensure_ascii=False)});
        var edges = new vis.DataSet({json.dumps(edges, ensure_ascii=False)});
        var container = document.getElementById('network');
        var data = {{ nodes: nodes, edges: edges }};

        var options = {{
            nodes: {{
                shape: 'box',
                font: {{ color: '#c9d1d9', size: 13, face: 'Segoe UI' }},
                borderWidth: 2,
                margin: 10,
            }},
            edges: {{
                color: {{ color: '#30363d', highlight: '#58a6ff' }},
                width: 1,
                smooth: {{ type: 'continuous' }},
            }},
            groups: {{
                'you': {{ color: {{ background: '#1f6feb', border: '#58a6ff' }} }},
                '🌐': {{ color: {{ background: '#238636', border: '#3fb950' }} }},
                '🖨️': {{ color: {{ background: '#6e40c9', border: '#a371f7' }} }},
                '🖥️': {{ color: {{ background: '#9e6a03', border: '#d29922' }} }},
                '📱': {{ color: {{ background: '#1f6feb', border: '#58a6ff' }} }},
                '💾': {{ color: {{ background: '#0d419d', border: '#58a6ff' }} }},
                '❓': {{ color: {{ background: '#484f58', border: '#8b949e' }} }},
            }},
            physics: {{
                stabilization: {{ iterations: 200 }},
                barnesHut: {{ gravitationalConstant: -3000, springLength: 150 }},
            }},
            interaction: {{ hover: true, tooltipDelay: 100 }},
        }};

        var network = new vis.Network(container, data, options);
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

    # Загружаем последнее сканирование
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

    # Определяем локальный IP
    local_ip = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    # Текстовая карта
    print_text_map(devices, subnet, local_ip)

    # HTML-карта
    print()
    save = input("  Сгенерировать HTML-карту для браузера? [Y/n]: ").strip().lower()
    if save != "n":
        html_path = generate_html_map(devices, subnet, local_ip)
        print()
        print(f"  ✅ HTML-карта: {html_path}")
        print()
        print(f"  Открой в браузере:")
        print(f"     xdg-open {html_path}     # Linux")
        print(f"     start {html_path}        # Windows")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
