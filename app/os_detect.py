"""
Автоопределение операционной системы.
Возвращает объект с информацией о текущей ОС и путями.
"""
import os
import sys
import platform
import subprocess
from pathlib import Path


class OSDetector:
    """Определяет ОС и предоставляет платформо-зависимые пути и команды."""

    def __init__(self):
        self.system = platform.system()  # 'Windows', 'Linux', 'Darwin'
        self.release = platform.release()
        self.version = platform.version()
        self.architecture = platform.machine()  # 'x86_64', 'AMD64'
        self.is_windows = self.system == "Windows"
        self.is_linux = self.system == "Linux"
        self.is_macos = self.system == "Darwin"

        # Корень проекта (папка, где лежит app/)
        self.project_root = Path(__file__).parent.parent.resolve()

    def get_python_executable(self) -> str:
        """Возвращает путь к Python для текущей ОС."""
        if self.is_windows:
            # Портативный Python на Windows
            portable = self.project_root / "python" / "python.exe"
            if portable.exists():
                return str(portable)
            return sys.executable  # fallback
        else:
            # На Linux — системный Python
            return sys.executable

    def get_libs_path(self) -> Path:
        """Путь к папке с зависимостями."""
        return self.project_root / "libs"

    def get_config_path(self) -> Path:
        """Путь к папке с конфигами."""
        return self.project_root / "config"

    def get_logs_path(self) -> Path:
        """Путь к папке с логами."""
        return self.project_root / "logs"

    def get_output_path(self) -> Path:
        """Путь к папке с результатами."""
        return self.project_root / "output"

    def get_system_info(self) -> dict:
        """Собирает информацию о системе."""
        info = {
            "system": self.system,
            "release": self.release,
            "version": self.version,
            "architecture": self.architecture,
            "hostname": platform.node(),
            "python_version": platform.python_version(),
        }

        if self.is_windows:
            info["spooler_service"] = "Spooler"
            info["ping_cmd"] = "ping -n 4"
            info["tracert_cmd"] = "tracert"
            info["ipconfig_cmd"] = "ipconfig /all"
        elif self.is_linux:
            info["spooler_service"] = "cups"
            info["ping_cmd"] = "ping -c 4"
            info["tracert_cmd"] = "traceroute"
            info["ipconfig_cmd"] = "ip a"
        else:
            info["spooler_service"] = "unknown"
            info["ping_cmd"] = "ping -c 4"
            info["tracert_cmd"] = "traceroute"
            info["ipconfig_cmd"] = "ifconfig"

        return info

    def run_command(self, cmd: list) -> tuple:
        """
        Запускает команду с учётом ОС.
        Возвращает (returncode, stdout, stderr).
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                shell=self.is_windows,
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)


# Глобальный экземпляр
os_detector = OSDetector()


if __name__ == "__main__":
    # Для отладки: запускаем и смотрим, что определилось
    import json
    print(json.dumps(os_detector.get_system_info(), indent=2, ensure_ascii=False))
