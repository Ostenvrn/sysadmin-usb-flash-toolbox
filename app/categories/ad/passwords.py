"""
Проверка паролей AD.
- Учётки, у которых пароль не менялся > N дней
- Учётки с неистекающим паролем
- Учётки, у которых пароль не менялся никогда
"""
from datetime import datetime, timezone, timedelta

from app.core.logger import setup_logger
from app.categories.ad.config import load_ad_config, is_ad_configured, show_ad_setup_help
from app.categories.ad.users import connect_ldap, get_base_dn
from app.categories.ad.audit import filetime_to_dt, UAC_DISABLED, UAC_PASSWORD_NEVER_EXPIRES

logger = setup_logger("ad-passwords")

MAX_PASSWORD_AGE_DAYS = 180


def audit_passwords(config: dict) -> dict:
    """Аудит паролей."""
    conn = connect_ldap(config)
    if not conn:
        return {}

    base_dn = get_base_dn(config)
    result = {
        "old_passwords": [],       # > 180 дней
        "never_changed": [],       # pwdLastSet = 0
        "never_expires": [],       # UAC flag
        "total": 0,
    }

    try:
        from ldap3 import SUBTREE
        conn.search(
            search_base=base_dn,
            search_filter="(&(objectClass=user)(objectCategory=person))",
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName", "displayName", "userAccountControl", "pwdLastSet",
            ],
        )

        now = datetime.now(timezone.utc)

        for entry in conn.entries:
            result["total"] += 1
            login = str(entry.sAMAccountName) if entry.sAMAccountName else "?"
            name = str(entry.displayName) if entry.displayName else ""

            uac = int(entry.userAccountControl.value) if entry.userAccountControl else 0

            # Пропускаем отключённые
            if uac & UAC_DISABLED:
                continue

            # Неистекающий пароль
            if uac & UAC_PASSWORD_NEVER_EXPIRES:
                result["never_expires"].append({"login": login, "name": name})

            # Дата смены пароля
            pwd_last_set = int(entry.pwdLastSet.value) if entry.pwdLastSet else 0

            if pwd_last_set == 0:
                result["never_changed"].append({"login": login, "name": name})
                continue

            pwd_date = filetime_to_dt(pwd_last_set)
            if pwd_date:
                days = (now - pwd_date).days
                if days > MAX_PASSWORD_AGE_DAYS:
                    result["old_passwords"].append({
                        "login": login,
                        "name": name,
                        "days": days,
                        "date": pwd_date.strftime("%d.%m.%Y"),
                    })

        conn.unbind()
    except Exception as e:
        logger.error(f"Ошибка аудита паролей: {e}")
        print(f"  ❌ Ошибка: {e}")

    return result


def print_audit(result: dict):
    """Красивый вывод."""
    if not result:
        return

    print()
    print("=" * 80)
    print("  АУДИТ ПАРОЛЕЙ")
    print("=" * 80)
    print(f"  Всего пользователей: {result['total']}")
    print(f"  Максимальный возраст пароля: {MAX_PASSWORD_AGE_DAYS} дней")
    print()

    # Старые пароли
    old = result.get("old_passwords", [])
    if old:
        print(f"  🔴 ПАРОЛЬ СТАРШЕ {MAX_PASSWORD_AGE_DAYS} ДНЕЙ ({len(old)})")
        print("  " + "─" * 76)
        for u in sorted(old, key=lambda x: -x["days"])[:20]:
            print(f"     • {u['login']:<25} {u['name']:<30} {u['days']} дней (с {u['date']})")
        if len(old) > 20:
            print(f"     ... и ещё {len(old) - 20}")
        print()

    # Никогда не менялся
    never = result.get("never_changed", [])
    if never:
        print(f"  🔴 ПАРОЛЬ НИКОГДА НЕ МЕНЯЛСЯ ({len(never)})")
        print("  " + "─" * 76)
        for u in never[:20]:
            print(f"     • {u['login']:<25} {u['name']}")
        if len(never) > 20:
            print(f"     ... и ещё {len(never) - 20}")
        print()

    # Не истекает
    never_expires = result.get("never_expires", [])
    if never_expires:
        print(f"  🟡 ПАРОЛЬ НЕ ИСТЕКАЕТ ({len(never_expires)})")
        print("  " + "─" * 76)
        for u in never_expires[:20]:
            print(f"     • {u['login']:<25} {u['name']}")
        if len(never_expires) > 20:
            print(f"     ... и ещё {len(never_expires) - 20}")
        print()

    print("=" * 80)
    if not (old or never or never_expires):
        print("  ✅ Все пароли в норме.")
    else:
        print("  💡 РЕКОМЕНДАЦИИ:")
        if old:
            print(f"     • Попроси {len(old)} пользователей сменить пароль")
        if never:
            print(f"     • У {len(never)} пользователей пароль не менялся никогда — срочно сменить!")
        if never_expires:
            print(f"     • У {len(never_expires)} пользователей пароль не истекает — рассмотреть политику")
    print("=" * 80)


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  АУДИТ ПАРОЛЕЙ AD")
    print("=" * 80)
    print()

    config = load_ad_config()
    if not is_ad_configured(config):
        show_ad_setup_help()
        input("  Нажми Enter...")
        return

    print(f"  Домен: {config['domain']}")
    print()

    confirm = input("  Начать аудит? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print()
    print("  🔍 Аудит паролей...")

    result = audit_passwords(config)
    print_audit(result)

    # Сохранение
    if result:
        import json
        from pathlib import Path
        output_dir = Path(__file__).parent.parent.parent.parent / "output" / "ad_audit"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = output_dir / f"password_audit_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        print(f"  📄 Отчёт сохранён: {filepath}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
