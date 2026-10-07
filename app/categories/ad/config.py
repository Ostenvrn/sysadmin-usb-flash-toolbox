"""
Конфигурация AD.
Читает настройки из .env (AD_DOMAIN, AD_USER, AD_PASSWORD).
"""
import os
from pathlib import Path

from app.core.logger import setup_logger

logger = setup_logger("ad-config")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


def load_ad_config() -> dict:
    """Загружает конфиг AD из .env."""
    # Пробуем загрузить .env
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            logger.warning("python-dotenv не установлен")

    config = {
        "domain": os.environ.get("AD_DOMAIN", ""),
        "user": os.environ.get("AD_USER", ""),
        "password": os.environ.get("AD_PASSWORD", ""),
        "server": os.environ.get("AD_SERVER", ""),  # контроллер домена
        "base_dn": os.environ.get("AD_BASE_DN", ""),  # DC=company,DC=local
    }

    # Если base_dn не указан — строим из domain
    if not config["base_dn"] and config["domain"]:
        parts = config["domain"].split(".")
        config["base_dn"] = ",".join(f"DC={p}" for p in parts)

    return config


def is_ad_configured(config: dict) -> bool:
    """Проверяет, что AD настроен."""
    return bool(config.get("domain") and config.get("user") and config.get("password"))


def show_ad_setup_help():
    """Показывает инструкцию по настройке AD."""
    print()
    print("=" * 70)
    print("  ⚠️  AD НЕ НАСТРОЕН")
    print("=" * 70)
    print()
    print("  Для работы с Active Directory нужно:")
    print()
    print("  1. Создать файл .env в корне проекта (если нет):")
    print("     cp .env.example .env")
    print()
    print("  2. Добавить в .env:")
    print()
    print("     AD_DOMAIN=company.local")
    print("     AD_USER=admin")
    print("     AD_PASSWORD=your_password")
    print("     AD_SERVER=dc01.company.local")
    print("     AD_BASE_DN=DC=company,DC=local")
    print()
    print("  3. Установить зависимости:")
    print("     pip install --target=libs/ ldap3")
    print("     # или для Windows:")
    print("     pip install --target=libs/ pyad")
    print()
    print("=" * 70)
    print()
