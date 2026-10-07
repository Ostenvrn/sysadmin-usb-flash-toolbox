"""
Классификация сетевых устройств.
Определяет: ПК, сервер, принтер, роутер, телефон, NAS, виртуалка.
Приоритет — ПК и серверы (для компании).
"""
from app.core.oui import is_local_mac


# =====================================================================
# Категории устройств
# =====================================================================
CATEGORY_PC = "pc"
CATEGORY_SERVER = "server"
CATEGORY_PRINTER = "printer"
CATEGORY_ROUTER = "router"
CATEGORY_PHONE = "phone"
CATEGORY_NAS = "nas"
CATEGORY_VM = "vm"
CATEGORY_TV = "tv"
CATEGORY_IOT = "iot"
CATEGORY_UNKNOWN = "unknown"


# Иконки и названия
CATEGORY_INFO = {
    CATEGORY_PC:      {"icon": "🖥️", "name": "ПК",              "priority": 1},
    CATEGORY_SERVER:  {"icon": "🖥️", "name": "Сервер",          "priority": 1},
    CATEGORY_PRINTER: {"icon": "🖨️", "name": "Принтер",         "priority": 2},
    CATEGORY_ROUTER:  {"icon": "🌐", "name": "Роутер",          "priority": 2},
    CATEGORY_NAS:     {"icon": "💾", "name": "NAS",             "priority": 2},
    CATEGORY_VM:      {"icon": "☁️", "name": "Виртуалка",       "priority": 3},
    CATEGORY_TV:      {"icon": "📺", "name": "ТВ",              "priority": 4},
    CATEGORY_PHONE:   {"icon": "📱", "name": "Телефон",         "priority": 5},
    CATEGORY_IOT:     {"icon": "📟", "name": "IoT-устройство",  "priority": 5},
    CATEGORY_UNKNOWN: {"icon": "❓", "name": "Неизвестно",      "priority": 9},
}


# =====================================================================
# Списки производителей по категориям
# =====================================================================

# Производители ПК (материнские платы, ноутбуки, брендовые ПК)
PC_VENDORS = [
    "intel", "realtek", "dell", "lenovo", "hp", "hewlett",
    "asus", "gigabyte", "msi", "asrock", "acer", "toshiba",
    "fujitsu", "clevo", "compal", "quantum", "pegatron",
    "biostar", "foxconn", "supermicro",
]

# Производители серверов
SERVER_VENDORS = [
    "supermicro", "dell emc", "hpe", "hewlett packard enterprise",
    "ibm", "oracle", "fujitsu", "lenovo enterprise",
    "intel corporation", "quanta", "wiwynn", "inspur",
]

# Производители принтеров
PRINTER_VENDORS = [
    "hp", "hewlett-packard", "canon", "epson", "kyocera",
    "brother", "xerox", "ricoh", "lexmark", "samsung electronics",
    "konica minolta", "sharp",
]

# Производители роутеров/сетевого оборудования
ROUTER_VENDORS = [
    "tp-link", "d-link", "netgear", "asus", "mikrotik",
    "ubiquiti", "cisco", "linksys", "zyxel", "tenda",
    "huawei technologies", "aruba", "juniper", "fortinet",
]

# Производители телефонов
PHONE_VENDORS = [
    "apple", "samsung", "xiaomi", "huawei", "honor",
    "oppo", "vivo", "oneplus", "realme", "motorola",
    "nokia", "sony", "lg electronics", "google",
    "tecno", "infinix", "itel",
]

# Производители NAS
NAS_VENDORS = [
    "synology", "qnap", "buffalo", "western digital",
    "seagate", "drobo", "asustor", "terramaster",
]

# Производители виртуалок
VM_VENDORS = [
    "vmware", "virtualbox", "qemu", "xensource", "parallels",
    "microsoft corporation", "amazon", "google cloud",
]


# =====================================================================
# Определение категории
# =====================================================================

def classify_device(device: dict) -> dict:
    """
    Классифицирует устройство.
    Возвращает: {category, icon, name, confidence, reason}
    """
    hostname = (device.get("hostname") or "").lower()
    vendor = (device.get("vendor") or "").lower()
    mac = device.get("mac", "")
    ports = device.get("open_ports", []) or []

    # === 1. Проверка по hostname (самое надёжное) ===

    # Серверы
    if any(x in hostname for x in ["srv-", "server-", "dc-", "web-", "db-",
                                    "mail-", "proxy-", "backup-", "srv_", "srv."]):
        return _result(CATEGORY_SERVER, "high", "hostname содержит серверный префикс")

    # ПК (Windows)
    if any(x in hostname for x in ["desktop-", "win-", "pc-", "pc_", "pc.",
                                    "workstation", "notebook", "laptop"]):
        return _result(CATEGORY_PC, "high", "hostname содержит ПК-префикс")

    # Принтеры
    if any(x in hostname for x in ["printer", "hp-", "canon-", "epson-",
                                    "kyocera-", "brother-", "xerox-", "mfp-"]):
        return _result(CATEGORY_PRINTER, "high", "hostname содержит принтер")

    # Роутеры
    if any(x in hostname for x in ["router", "gateway", "gw-", "mikrotik",
                                    "ubiquiti", "cisco", "switch", "ap-"]):
        return _result(CATEGORY_ROUTER, "high", "hostname содержит роутер")

    # NAS
    if any(x in hostname for x in ["nas", "synology", "qnap", "freenas"]):
        return _result(CATEGORY_NAS, "high", "hostname содержит NAS")

    # Телефоны
    if any(x in hostname for x in ["iphone", "ipad", "android", "phone",
                                    "redmi", "xiaomi", "huawei", "honor",
                                    "samsung-galaxy", "galaxy-"]):
        return _result(CATEGORY_PHONE, "high", "hostname содержит телефон")

    # ТВ
    if any(x in hostname for x in ["tv", "smarttv", "androidtv", "bravia", "webos"]):
        return _result(CATEGORY_TV, "high", "hostname содержит ТВ")

    # === 2. Проверка по открытым портам (очень надёжно) ===

    # ПК Windows: 135, 139, 445
    if 445 in ports or 139 in ports or 135 in ports:
        return _result(CATEGORY_PC, "high", "открыты порты Windows (135/139/445)")

    # Принтеры: 9100 (raw), 515 (LPD), 631 (IPP)
    if 9100 in ports or 515 in ports or 631 in ports:
        return _result(CATEGORY_PRINTER, "high", "открыты порты принтера (9100/515/631)")

    # NAS: 5000/5001 (Synology), 8080+WebDAV
    if 5000 in ports and 5001 in ports:
        return _result(CATEGORY_NAS, "high", "открыты порты Synology (5000/5001)")

    # Сервер Linux: 22 + 80/443
    if 22 in ports and (80 in ports or 443 in ports):
        return _result(CATEGORY_SERVER, "medium", "открыты порты 22 + веб")

    # ПК Linux: только 22
    if 22 in ports:
        return _result(CATEGORY_PC, "medium", "открыт только порт 22 (Linux)")

    # RDP Windows
    if 3389 in ports:
        return _result(CATEGORY_PC, "high", "открыт RDP (3389) — Windows")

    # === 3. Проверка по производителю (OUI) ===

    if vendor:
        # Серверы
        if any(x in vendor for x in SERVER_VENDORS):
            return _result(CATEGORY_SERVER, "high", f"производитель сервера: {vendor}")

        # NAS
        if any(x in vendor for x in NAS_VENDORS):
            return _result(CATEGORY_NAS, "high", f"производитель NAS: {vendor}")

        # Виртуалки
        if any(x in vendor for x in VM_VENDORS):
            return _result(CATEGORY_VM, "high", f"производитель VM: {vendor}")

        # Принтеры
        if any(x in vendor for x in PRINTER_VENDORS):
            return _result(CATEGORY_PRINTER, "high", f"производитель принтера: {vendor}")

        # Роутеры
        if any(x in vendor for x in ROUTER_VENDORS):
            return _result(CATEGORY_ROUTER, "high", f"производитель роутера: {vendor}")

        # ПК
        if any(x in vendor for x in PC_VENDORS):
            return _result(CATEGORY_PC, "medium", f"производитель ПК: {vendor}")

        # Телефоны
        if any(x in vendor for x in PHONE_VENDORS):
            return _result(CATEGORY_PHONE, "high", f"производитель телефона: {vendor}")

    # === 4. Локальный MAC (random) — обычно телефоны ===
    if mac and is_local_mac(mac):
        return _result(CATEGORY_PHONE, "low", "локальный MAC (random) — обычно телефон")

    # === 5. Неизвестно ===
    return _result(CATEGORY_UNKNOWN, "low", "не удалось определить")


def _result(category: str, confidence: str, reason: str) -> dict:
    """Формирует результат классификации."""
    info = CATEGORY_INFO.get(category, CATEGORY_INFO[CATEGORY_UNKNOWN])
    return {
        "category": category,
        "icon": info["icon"],
        "name": info["name"],
        "priority": info["priority"],
        "confidence": confidence,
        "reason": reason,
    }


def get_device_label(device: dict) -> str:
    """Возвращает красивую метку для устройства."""
    classification = classify_device(device)
    return f"{classification['icon']} {classification['name']}"
