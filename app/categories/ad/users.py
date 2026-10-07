"""
Управление пользователями AD.
- Список пользователей
- Поиск пользователя
- Информация о пользователе
- Создание пользователя
- Блокировка/разблокировка
"""
from app.core.logger import setup_logger
from app.categories.ad.config import load_ad_config, is_ad_configured, show_ad_setup_help

logger = setup_logger("ad-users")


# =====================================================================
# Подключение к AD
# =====================================================================

def connect_ldap(config: dict):
    """Подключается к AD через LDAP (ldap3)."""
    try:
        from ldap3 import Server, Connection, ALL, NTLM
    except ImportError:
        print("  ❌ ldap3 не установлен.")
        print("     Установи: pip install --target=libs/ ldap3")
        return None

    server_name = config.get("server") or config.get("domain")
    if not server_name:
        return None

    try:
        server = Server(server_name, get_info=ALL, connect_timeout=10)
        user = f"{config['domain']}\\{config['user']}"
        conn = Connection(
            server, user=user, password=config["password"],
            authentication=NTLM, auto_bind=True,
        )
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения: {e}")
        print(f"  ❌ Ошибка подключения: {e}")
        return None


def get_base_dn(config: dict) -> str:
    """Базовый DN."""
    if config.get("base_dn"):
        return config["base_dn"]
    parts = config["domain"].split(".")
    return ",".join(f"DC={p}" for p in parts)


# =====================================================================
# Операции
# =====================================================================

def list_users(config: dict, limit: int = 100) -> list:
    """Список пользователей AD."""
    conn = connect_ldap(config)
    if not conn:
        return []

    base_dn = get_base_dn(config)
    users = []

    try:
        from ldap3 import SUBTREE
        conn.search(
            search_base=base_dn,
            search_filter="(&(objectClass=user)(objectCategory=person))",
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName", "displayName", "mail",
                "userAccountControl", "lastLogonTimestamp",
                "pwdLastSet", "memberOf", "department", "title",
            ],
            size_limit=limit,
        )

        for entry in conn.entries:
            users.append({
                "login": str(entry.sAMAccountName) if entry.sAMAccountName else "",
                "name": str(entry.displayName) if entry.displayName else "",
                "email": str(entry.mail) if entry.mail else "",
                "department": str(entry.department) if entry.department else "",
                "title": str(entry.title) if entry.title else "",
                "uac": int(entry.userAccountControl.value) if entry.userAccountControl else 0,
                "enabled": not (int(entry.userAccountControl.value) & 2) if entry.userAccountControl else False,
            })

        conn.unbind()
    except Exception as e:
        logger.error(f"Ошибка list_users: {e}")
        print(f"  ❌ Ошибка: {e}")

    return users


def find_user(config: dict, login: str) -> dict:
    """Находит пользователя по логину."""
    conn = connect_ldap(config)
    if not conn:
        return {}

    base_dn = get_base_dn(config)

    try:
        conn.search(
            search_base=base_dn,
            search_filter=f"(&(objectClass=user)(sAMAccountName={login}))",
            attributes=[
                "sAMAccountName", "displayName", "mail", "userAccountControl",
                "lastLogonTimestamp", "pwdLastSet", "memberOf",
                "department", "title", "telephoneNumber", "distinguishedName",
            ],
        )

        if not conn.entries:
            print(f"  ❌ Пользователь {login} не найден")
            conn.unbind()
            return {}

        entry = conn.entries[0]
        result = {
            "login": str(entry.sAMAccountName) if entry.sAMAccountName else "",
            "name": str(entry.displayName) if entry.displayName else "",
            "email": str(entry.mail) if entry.mail else "",
            "phone": str(entry.telephoneNumber) if entry.telephoneNumber else "",
            "department": str(entry.department) if entry.department else "",
            "title": str(entry.title) if entry.title else "",
            "dn": str(entry.distinguishedName) if entry.distinguishedName else "",
            "uac": int(entry.userAccountControl.value) if entry.userAccountControl else 0,
            "enabled": not (int(entry.userAccountControl.value) & 2) if entry.userAccountControl else False,
            "groups": [str(g) for g in entry.memberOf] if entry.memberOf else [],
        }

        conn.unbind()
        return result
    except Exception as e:
        logger.error(f"Ошибка find_user: {e}")
        print(f"  ❌ Ошибка: {e}")
        return {}


def unlock_user(config: dict, login: str) -> bool:
    """Разблокирует пользователя."""
    conn = connect_ldap(config)
    if not conn:
        return False

    base_dn = get_base_dn(config)

    try:
        # Ищем пользователя
        conn.search(
            search_base=base_dn,
            search_filter=f"(sAMAccountName={login})",
            attributes=["distinguishedName", "lockoutTime"],
        )

        if not conn.entries:
            print(f"  ❌ Пользователь {login} не найден")
            conn.unbind()
            return False

        user_dn = str(conn.entries[0].distinguishedName)

        # Сбрасываем lockoutTime в 0
        conn.modify(user_dn, {"lockoutTime": [(2, ["0"])]})

        if conn.result["result"] == 0:
            print(f"  ✅ Пользователь {login} разблокирован")
            conn.unbind()
            return True
        else:
            print(f"  ❌ Ошибка: {conn.result['description']}")
            conn.unbind()
            return False
    except Exception as e:
        logger.error(f"Ошибка unlock_user: {e}")
        print(f"  ❌ Ошибка: {e}")
        return False


# =====================================================================
# Меню
# =====================================================================

def print_users(users: list):
    """Красивый вывод списка."""
    if not users:
        print("  Пользователи не найдены.")
        return

    print()
    print("=" * 90)
    print(f"  ПОЛЬЗОВАТЕЛИ AD ({len(users)})")
    print("=" * 90)
    print()
    print(f"  {'Логин':<20} {'Имя':<25} {'Отдел':<15} {'Статус':<10}")
    print("  " + "─" * 84)

    for u in users:
        status = "✅ активен" if u["enabled"] else "🔴 отключён"
        login = u["login"][:19]
        name = u["name"][:24]
        dept = u["department"][:14]
        print(f"  {login:<20} {name:<25} {dept:<15} {status:<10}")


def run():
    """Точка входа."""
    print()
    print("=" * 90)
    print("  ПОЛЬЗОВАТЕЛИ AD")
    print("=" * 90)
    print()

    config = load_ad_config()
    if not is_ad_configured(config):
        show_ad_setup_help()
        input("  Нажми Enter...")
        return

    print(f"  Домен: {config['domain']}")
    print(f"  Сервер: {config.get('server') or config['domain']}")
    print(f"  Пользователь: {config['user']}")
    print()

    print("  Выбери действие:")
    print("    [1] 📋 Список пользователей")
    print("    [2] 🔍 Найти пользователя")
    print("    [3] 🔓 Разблокировать пользователя")
    print("    [0] ← Назад")
    print()

    choice = input("  Выбор: ").strip()

    if choice == "0":
        return
    elif choice == "1":
        print()
        print("  Запрос к AD...")
        users = list_users(config)
        print_users(users)
    elif choice == "2":
        login = input("  Логин: ").strip()
        if login:
            print()
            info = find_user(config, login)
            if info:
                print()
                print("  " + "─" * 70)
                print(f"  Логин:     {info['login']}")
                print(f"  Имя:       {info['name']}")
                print(f"  Email:     {info['email']}")
                print(f"  Телефон:   {info['phone']}")
                print(f"  Отдел:     {info['department']}")
                print(f"  Должность: {info['title']}")
                print(f"  Статус:    {'✅ активен' if info['enabled'] else '🔴 отключён'}")
                print(f"  DN:        {info['dn']}")
                if info["groups"]:
                    print(f"  Группы:    {len(info['groups'])}")
                    for g in info["groups"][:5]:
                        print(f"     • {g}")
                print("  " + "─" * 70)
    elif choice == "3":
        login = input("  Логин: ").strip()
        if login:
            print()
            unlock_user(config, login)
    else:
        print("  Неверный выбор.")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
