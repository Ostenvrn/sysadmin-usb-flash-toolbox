"""
ASCII-арт и приветствие.
"""
from app.ui.colors import C, bold, dim, cyan, bright_cyan, bright_green, bright_yellow


AUTHOR_NAME = "Чернов Александр Дмитриевич"
AUTHOR_SHORT = "Чернов А.Д."

VERSION = "1.0.0"


def print_ascii_banner():
    """ASCII-арт при запуске."""
    art = f"""{C.BRIGHT_CYAN}
   ███████╗██╗   ██╗███████╗ █████╗ ██████╗ ███╗   ███╗██╗███╗   ██╗
   ██╔════╝╚██╗ ██╔╝██╔════╝██╔══██╗██╔══██╗████╗ ████║██║████╗  ██║
   ███████╗ ╚████╔╝ ███████╗███████║██║  ██║██╔████╔██║██║██╔██╗ ██║
   ╚════██║  ╚██╔╝  ╚════██║██╔══██║██║  ██║██║╚██╔╝██║██║██║╚██╗██║
   ███████║   ██║   ███████║██║  ██║██████╔╝██║ ╚═╝ ██║██║██║ ╚████║
   ╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝
{C.RESET}"""
    print(art)


def print_welcome(hostname: str, os_name: str, user: str = ""):
    """Приветствие при запуске."""
    print()
    print(f"  {bold('Добро пожаловать в')} {bright_cyan('SYSADMIN-USB')} {dim(f'v{VERSION}')}")
    print()
    print(f"  {dim('Автор:')}     {bright_green(AUTHOR_NAME)}")
    print(f"  {dim('ПК:')}        {cyan(hostname)}")
    print(f"  {dim('ОС:')}        {cyan(os_name)}")
    if user:
        print(f"  {dim('Пользователь:')} {cyan(user)}")
    print()


def print_footer():
    """Подвал при выходе."""
    print()
    print(f"  {dim('─' * 60)}")
    print(f"  {dim('Спасибо за использование')} {bright_cyan('sysadmin-usb')}")
    print(f"  {dim('Автор:')} {bright_green(AUTHOR_NAME)}")
    print(f"  {dim('GitHub:')} {cyan('https://github.com/Ostenvrn/sysadmin-usb-flash-toolbox')}")
    print(f"  {dim('─' * 60)}")
    print()


def print_separator():
    """Разделитель."""
    print(f"  {dim('─' * 68)}")


def print_section(title: str):
    """Заголовок раздела."""
    print()
    print(f"  {bold(bright_cyan('▶'))} {bold(title)}")
    print(f"  {dim('─' * 66)}")
