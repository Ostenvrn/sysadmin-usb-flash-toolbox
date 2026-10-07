"""
Загрузка и поиск производителя по MAC (OUI).
Использует локальную базу IEEE OUI Master Database (config/oui/master_oui.txt).
Работает офлайн, без интернета.
"""
import re
from pathlib import Path

from app.core.logger import setup_logger

logger = setup_logger("oui")

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
OUI_FILE = PROJECT_ROOT / "config" / "oui" / "master_oui.txt"


# =====================================================================
# Загрузка базы (один раз, кэшируется)
# =====================================================================
_OUI_DB = None


def load_oui_db() -> dict:
    """
    Загружает базу OUI в память (один раз).
    Возвращает словарь: {MAC_PREFIX: vendor_name}.
    """
    global _OUI_DB

    if _OUI_DB is not None:
        return _OUI_DB

    _OUI_DB = {}

    if not OUI_FILE.exists():
        logger.warning(f"База OUI не найдена: {OUI_FILE}")
        logger.warning("Скачай: curl -L -o config/oui/master_oui.txt "
                       "https://raw.githubusercontent.com/Ringmast4r/OUI-Master-Database/master/LISTS/master_oui.txt")
        return _OUI_DB

    logger.info(f"Загрузка базы OUI: {OUI_FILE}")

    try:
        with open(OUI_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Формат master_oui.txt:
                # OUI\tVendor  (например: 00000C\tCisco Systems, Inc)
                # Или другие форматы — проверим.
                parts = line.split("\t")
                if len(parts) >= 2:
                    oui = parts[0].strip().upper().replace(":", "").replace("-", "")
                    vendor = parts[1].strip()
                    if len(oui) >= 6:
                        _OUI_DB[oui[:6]] = vendor
                else:
                    # Пробуем формат "OUI Vendor" (пробел)
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        oui = parts[0].strip().upper().replace(":", "").replace("-", "")
                        vendor = parts[1].strip()
                        if len(oui) >= 6:
                            _OUI_DB[oui[:6]] = vendor

        logger.info(f"Загружено OUI-записей: {len(_OUI_DB)}")
    except Exception as e:
        logger.error(f"Ошибка загрузки OUI: {e}")

    return _OUI_DB


def lookup_vendor(mac: str) -> str:
    """
    Ищет производителя по MAC-адресу.
    Возвращает название производителя или пустую строку.
    """
    if not mac:
        return ""

    # Нормализуем MAC: убираем разделители, приводим к верхнему регистру
    mac_clean = mac.upper().replace(":", "").replace("-", "").replace(".", "")

    if len(mac_clean) < 6:
        return ""

    prefix = mac_clean[:6]

    db = load_oui_db()
    return db.get(prefix, "")


def is_local_mac(mac: str) -> bool:
    """
    Проверяет, является ли MAC локально администрируемым (random).
    Признак: второй hex-символ — чётный (0,2,4,6,8,A,C,E).
    """
    if not mac:
        return False

    mac_clean = mac.upper().replace(":", "").replace("-", "").replace(".", "")
    if len(mac_clean) < 2:
        return False

    # Второй символ (индекс 1)
    second_char = mac_clean[1]
    if second_char in "02468ACE":
        return True
    return False
