"""
Настройка логирования: пишет в logs/app.log и в консоль.
"""
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def setup_logger(name: str = "sysadmin-usb") -> logging.Logger:
    """Создаёт и настраивает логгер."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Если уже настроен — не дублируем
    if logger.handlers:
        return logger

    # Формат
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Файл
    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
