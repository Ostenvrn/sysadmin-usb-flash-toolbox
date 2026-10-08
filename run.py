# run.py
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

# Запускаем основной скрипт
from app.main import main

if __name__ == "__main__":
    main()
