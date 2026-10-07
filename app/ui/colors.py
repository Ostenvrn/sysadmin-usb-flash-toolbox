"""
Цвета и стили для консоли (ANSI).
Работает на Linux/macOS. На Windows — отключается.
"""
import os
import sys


def _supports_color() -> bool:
    """Проверяет, поддерживает ли терминал цвета."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return True


COLOR = _supports_color()


# =====================================================================
# ANSI-коды
# =====================================================================
class C:
    RESET = "\033[0m" if COLOR else ""

    # Стили
    BOLD = "\033[1m" if COLOR else ""
    DIM = "\033[2m" if COLOR else ""
    ITALIC = "\033[3m" if COLOR else ""
    UNDERLINE = "\033[4m" if COLOR else ""
    BLINK = "\033[5m" if COLOR else ""
    REVERSE = "\033[7m" if COLOR else ""

    # Обычные цвета
    BLACK = "\033[30m" if COLOR else ""
    RED = "\033[31m" if COLOR else ""
    GREEN = "\033[32m" if COLOR else ""
    YELLOW = "\033[33m" if COLOR else ""
    BLUE = "\033[34m" if COLOR else ""
    MAGENTA = "\033[35m" if COLOR else ""
    CYAN = "\033[36m" if COLOR else ""
    WHITE = "\033[37m" if COLOR else ""

    # Яркие цвета
    BRIGHT_BLACK = "\033[90m" if COLOR else ""
    BRIGHT_RED = "\033[91m" if COLOR else ""
    BRIGHT_GREEN = "\033[92m" if COLOR else ""
    BRIGHT_YELLOW = "\033[93m" if COLOR else ""
    BRIGHT_BLUE = "\033[94m" if COLOR else ""
    BRIGHT_MAGENTA = "\033[95m" if COLOR else ""
    BRIGHT_CYAN = "\033[96m" if COLOR else ""
    BRIGHT_WHITE = "\033[97m" if COLOR else ""

    # Фоны
    BG_BLACK = "\033[40m" if COLOR else ""
    BG_RED = "\033[41m" if COLOR else ""
    BG_GREEN = "\033[42m" if COLOR else ""
    BG_YELLOW = "\033[43m" if COLOR else ""
    BG_BLUE = "\033[44m" if COLOR else ""
    BG_MAGENTA = "\033[45m" if COLOR else ""
    BG_CYAN = "\033[46m" if COLOR else ""
    BG_WHITE = "\033[47m" if COLOR else ""


# =====================================================================
# Функции-обёртки
# =====================================================================

def red(text: str) -> str:
    return f"{C.RED}{text}{C.RESET}"


def green(text: str) -> str:
    return f"{C.GREEN}{text}{C.RESET}"


def yellow(text: str) -> str:
    return f"{C.YELLOW}{text}{C.RESET}"


def blue(text: str) -> str:
    return f"{C.BLUE}{text}{C.RESET}"


def cyan(text: str) -> str:
    return f"{C.CYAN}{text}{C.RESET}"


def magenta(text: str) -> str:
    return f"{C.MAGENTA}{text}{C.RESET}"


def bold(text: str) -> str:
    return f"{C.BOLD}{text}{C.RESET}"


def dim(text: str) -> str:
    return f"{C.DIM}{text}{C.RESET}"


def bright_cyan(text: str) -> str:
    return f"{C.BRIGHT_CYAN}{text}{C.RESET}"


def bright_green(text: str) -> str:
    return f"{C.BRIGHT_GREEN}{text}{C.RESET}"


def bright_yellow(text: str) -> str:
    return f"{C.BRIGHT_YELLOW}{text}{C.RESET}"


def bright_red(text: str) -> str:
    return f"{C.BRIGHT_RED}{text}{C.RESET}"


def bright_magenta(text: str) -> str:
    return f"{C.BRIGHT_MAGENTA}{text}{C.RESET}"


# =====================================================================
# Рамки
# =====================================================================

def box_top(width: int = 68, color: str = "") -> str:
    return f"{color}╔{'═' * (width - 2)}╗{C.RESET}"


def box_bottom(width: int = 68, color: str = "") -> str:
    return f"{color}╚{'═' * (width - 2)}╝{C.RESET}"


def box_line(text: str = "", width: int = 68, color: str = "", align: str = "left") -> str:
    """Строка внутри рамки."""
    inner_width = width - 4
    text = text[:inner_width]

    if align == "center":
        text = text.center(inner_width)
    elif align == "right":
        text = text.rjust(inner_width)
    else:
        text = text.ljust(inner_width)

    return f"{color}║ {text} ║{C.RESET}"


def box_sep(width: int = 68, color: str = "") -> str:
    return f"{color}╠{'═' * (width - 2)}╣{C.RESET}"


def simple_line(width: int = 68, color: str = "") -> str:
    return f"{color}{'─' * width}{C.RESET}"


def print_banner(text: str, width: int = 68, color: str = None):
    """Печатает заголовок в рамке."""
    if color is None:
        color = C.BRIGHT_CYAN
    print()
    print(box_top(width, color))
    print(box_line(text, width, color, align="center"))
    print(box_bottom(width, color))
    print()
