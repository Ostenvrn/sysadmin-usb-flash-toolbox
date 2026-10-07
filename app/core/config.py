"""
Загрузка конфигурации из config.yaml и переменных окружения .env.
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def load_config() -> dict:
    """Загружает config.yaml и .env, возвращает объединённый словарь."""
    # Загружаем .env (если есть)
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Загружаем config.yaml
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Конфиг не найден: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Добавляем переменные окружения в секцию env
    config["env"] = dict(os.environ)

    return config
