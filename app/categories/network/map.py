"""
Карта сети — визуализация.
Читает результаты сканирования (output/scans/network_*.json).
Группирует устройства по категориям (ПК, серверы, принтеры...).
Телефоны — в отдельной группе (мелкие, второстепенные).
"""
import json
import socket
import shutil
from pathlib import Path
from datetime import datetime

from app.os_detect import os_detector
from app.core.logger import setup_logger
from app.core.device_classifier import classify_device, CATEGORY_INFO

logger = setup_logger("network-map")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
SCANS_DIR = PROJECT_ROOT / "output" / "scans"
MAPS_DIR = PROJECT_ROOT / "output" / "maps"


def get_gateway() -> str:
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


def get_connection_icon(device: dict) -> str:
    conn = device.get("connection", "")
    if conn == "wifi":
        return "📶"
    if conn == "ethernet":
        return "🔌"
    return ""


# =====================================================================
# Текстовая карта
# =====================================================================

def print_text_map(devices: list, subnet: str, local_ip: str, gateway: str):
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

    # Группируем по категориям
    by_category = {}
    for d in devices:
        cat = d.get("classification", {}).get("category", "unknown")
        by_category.setdefault(cat, []).append(d)

    sorted_cats = sorted(
        by_category.keys(),
        key=lambda c: CATEGORY_INFO.get(c, {}).get("priority", 9)
    )

    for cat in sorted_cats:
        devs = by_category[cat]
        info = CATEGORY_INFO.get(cat, {})
        icon = info.get("icon", "❓")
        name = info.get("name", cat)

        print(f"  {icon} {name.upper()} ({len(devs)})")
        print("  " + "─" * 76)

        for d in sorted(devs, key=lambda x: tuple(int(i) for i in x["ip"].split("."))):
            ip = d["ip"]
            hostname = d.get("hostname") or "—"
            mac = d.get("mac") or "—"
            vendor = d.get("vendor") or ""
            conn_icon = get_connection_icon(d)

            marker = ""
            if ip == local_ip:
                marker = " ← (ты)"
            elif ip == gateway:
                marker = " ← (роутер)"

            print(f"     ├─ {ip:<16} {conn_icon}{marker}")
            if hostname != "—":
                print(f"     │  Hostname: {hostname}")
            if vendor:
                print(f"     │  Vendor:   {vendor}")
            print(f"     │  MAC:      {mac}")
        print()


# =====================================================================
# Скачивание vis-network
# =====================================================================

def _download_vis_network(target: Path) -> bool:
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
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = MAPS_DIR / f"network_map_{timestamp}.html"

    # Копируем vis-network
    js_source = PROJECT_ROOT / "app" / "ui" / "web" / "static" / "js" / "vis-network.min.js"
    js_dest = MAPS_DIR / "vis-network.min.js"

    if not js_source.exists():
        print("  ⚠️  vis-network.min.js не найден, скачиваю...")
        js_source.parent.mkdir(parents=True, exist_ok=True)
        _download_vis_network(js_source)

    if js_source.exists():
        shutil.copy(js_source, js_dest)

    nodes = []
    edges = []

    # 1. Роутер
    if gateway:
        nodes.append({
            "id": gateway,
            "label": f"🌐 Роутер\n{gateway}",
            "group": "router",
            "title": f"Роутер (шлюз)\nIP: {gateway}",
            "size": 45,
        })

    # 2. Твой ПК
    local_conn_icon = ""
    for d in devices:
        if d["ip"] == local_ip:
            local_conn_icon = get_connection_icon(d)
            break

    nodes.append({
        "id": local_ip,
        "label": f"💻 ТЫ\n{local_conn_icon} {local_ip}",
        "group": "you",
        "title": f"Твой ПК\nIP: {local_ip}",
        "size": 40,
    })

    # 3. Устройства
    for d in devices:
        ip = d["ip"]
        if ip == local_ip or ip == gateway:
            continue

        classification = d.get("classification", classify_device(d))
        cat = classification.get("category", "unknown")
        cat_icon = classification.get("icon", "❓")
        cat_name = classification.get("name", "Неизвестно")

        hostname = d.get("hostname") or ip
        mac = d.get("mac") or "—"
        vendor = d.get("vendor") or ""
        ports = d.get("open_ports", []) or []
        conn_icon = get_connection_icon(d)

        # Tooltip
        tooltip_parts = [f"{cat_icon} {cat_name}", f"IP: {ip}"]
        if hostname and hostname != ip:
            tooltip_parts.append(f"Hostname: {hostname}")
        if vendor:
            tooltip_parts.append(f"Vendor: {vendor}")
        if mac and mac != "—":
            tooltip_parts.append(f"MAC: {mac}")
        if ports:
            tooltip_parts.append(f"Порты: {', '.join(map(str, ports[:10]))}")
        if classification.get("reason"):
            tooltip_parts.append(f"Причина: {classification['reason']}")

        # Размер: ПК и серверы — крупнее, телефоны — мельче
        size = 30
        if cat in ("pc", "server"):
            size = 35
        elif cat == "printer":
            size = 30
        elif cat == "phone":
            size = 18
        elif cat == "unknown":
            size = 20

        label = f"{cat_icon} {cat_name}\n{conn_icon} {ip}" if conn_icon else f"{cat_icon} {cat_name}\n{ip}"

        nodes.append({
            "id": ip,
            "label": label,
            "group": cat,
            "title": "\n".join(tooltip_parts),
            "size": size,
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
        body {{ margin: 0; font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #c9d1d9; display: flex; flex-direction: column; height: 100vh; }}
        header {{ padding: 15px 20px; background: #161b22; border-bottom: 1px solid #30363d; }}
        h1 {{ margin: 0; font-size: 22px; color: #58a6ff; }}
        .info {{ margin-top: 6px; font-size: 13px; color: #8b949e; }}
        .content {{ display: flex; flex: 1; overflow: hidden; }}
        #network {{ flex: 1; height: 100%; }}
        .sidebar {{ width: 360px; background: #161b22; border-left: 1px solid #30363d; padding: 20px; overflow-y: auto; }}
        .sidebar h2 {{ margin: 0 0 15px 0; font-size: 16px; color: #58a6ff; }}
        .sidebar .hint {{ color: #8b949e; font-size: 13px; font-style: italic; }}
        .device-item {{ padding: 10px; background: #21262d; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #58a6ff; }}
        .device-item .name {{ font-weight: bold; font-size: 14px; margin-bottom: 4px; }}
        .device-item .ip {{ font-family: monospace; color: #8b949e; font-size: 12px; }}
        .device-item .mac {{ font-family: monospace; color: #6e7681; font-size: 11px; margin-top: 2px; }}
        .legend {{ position: absolute; bottom: 20px; left: 20px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 15px; font-size: 12px; max-height: 400px; overflow-y: auto; }}
        .legend h3 {{ margin: 0 0 8px 0; font-size: 13px; color: #58a6ff; }}
        .legend div {{ margin: 3px 0; }}
    </style>
</head>
<body>
    <header>
        <h1>🗺️ Карта сети</h1>
        <div class="info">
            Подсеть: <b>{subnet}</b> | Устройств: <b>{len(devices)}</b> | Шлюз: <b>{gateway or "не найден"}</b> | {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        </div>
    </header>
    <div class="content">
        <div id="network"></div>
        <div class="sidebar">
            <h2>📋 Информация</h2>
            <div id="info-panel">
                <p class="hint">Кликни по узлу — увидишь подробности.</p>
            </div>
        </div>
    </div>
    <div class="legend">
        <h3>Категории</h3>
        <div>🖥️ ПК / Сервер</div>
        <div>🖨️ Принтер</div>
        <div>🌐 Роутер</div>
        <div>💾 NAS</div>
        <div>☁️ Виртуалка</div>
        <div>📺 ТВ</div>
        <div>📱 Телефон</div>
        <div>📟 IoT</div>
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
            nodes: {{ shape: 'box', font: {{ color: '#c9d1d9', size: 13 }}, borderWidth: 2, margin: 12 }},
            edges: {{ color: {{ color: '#30363d', highlight: '#58a6ff' }}, width: 1, smooth: {{ type: 'continuous' }} }},
            groups: {{
                'router': {{ color: {{ background: '#238636', border: '#3fb950' }}, shape: 'hexagon' }},
                'you': {{ color: {{ background: '#1f6feb', border: '#58a6ff' }} }},
                'pc': {{ color: {{ background: '#1f6feb', border: '#58a6ff' }} }},
                'server': {{ color: {{ background: '#a371f7', border: '#d2a8ff' }} }},
                'printer': {{ color: {{ background: '#6e40c9', border: '#a371f7' }} }},
                'router': {{ color: {{ background: '#238636', border: '#3fb950' }}, shape: 'hexagon' }},
                'nas': {{ color: {{ background: '#0d419d', border: '#58a6ff' }} }},
                'vm': {{ color: {{ background: '#484f58', border: '#8b949e' }} }},
                'tv': {{ color: {{ background: '#9e6a03', border: '#d29922' }} }},
                'phone': {{ color: {{ background: '#6e7681', border: '#8b949e' }} }},
                'iot': {{ color: {{ background: '#6e7681', border: '#8b949e' }} }},
                'unknown': {{ color: {{ background: '#484f58', border: '#8b949e' }} }},
            }},
            physics: {{ stabilization: {{ iterations: 200 }}, barnesHut: {{ gravitationalConstant: -4000, springLength: 180 }} }},
            interaction: {{ hover: true, tooltipDelay: 100 }},
        }};

        var network = new vis.Network(container, data, options);

        network.on('click', function(params) {{
            var infoPanel = document.getElementById('info-panel');
            if (params.nodes.length === 0) {{
                infoPanel.innerHTML = '<p class="hint">Кликни по узлу — увидишь подробности.</p>';
                return;
            }}
            var id = params.nodes[0];
            var node = nodes.get(id);
            var connected = network.getConnectedNodes(id);

            var html = '<div class="device-item">';
            html += '<div class="name">' + node.label.replace('\\n', ' — ') + '</div>';
            html += '<div class="ip">IP: ' + node.id + '</div>';
            if (node.title) {{
                var parts = node.title.split('\\n');
                for (var i = 1; i < parts.length; i++) {{
                    html += '<div class="mac">' + parts[i] + '</div>';
                }}
            }}
            html += '</div>';

            if (connected.length > 0) {{
                html += '<h2 style="margin-top:20px;">🔗 Связано с (' + connected.length + '):</h2>';
                connected.forEach(function(cid) {{
                    var n = nodes.get(cid);
                    if (!n) return;
                    html += '<div class="device-item">';
                    html += '<div class="name">' + n.label.replace('\\n', ' — ') + '</div>';
                    html += '<div class="ip">IP: ' + n.id + '</div>';
                    html += '</div>';
                }});
            }}
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
