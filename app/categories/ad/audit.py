"""
Аудит Active Directory.
- Отключённые учётки
- Учётки с неистекающим паролем
- Учётки без входа > 90 дней
- Пользователи с правами админа
"""
from datetime import datetime, timezone, timedelta

from app.core.logger import setup_logger
from app.categories.ad.config import load_ad_config, is_ad_configured, show_ad_setup_help
from app.categories.ad.users import connect_ldap, get_base_dn

logger = setup_logger("ad-audit")


# Флаги userAccountControl
UAC_DISABLED = 0x0002
UAC_PASSWORD_NEVER_EXPIRES = 0x10000
UAC_DONT_EXPIRE_PASSWORD = 0x10000


def filetime_to_dt(filetime: int) -> datetime:
    """Конвертирует Windows FILETIME в datetime."""
    if filetime == 0 or filetime == 9223372036854775807:
        return None
    try:
        # FILETIME в 100-наносекундных интервалах с 1601 года
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=filetime / 10)
    except Exception:
        return None


def audit_ad(config: dict) -> dict:
    """Проводит аудит AD."""
    conn = connect_ldap(config)
    if not conn:
        return {}

    base_dn = get_base_dn(config)
    result = {
        "disabled": [],
        "password_never_expires": [],
        "inactive_90d": [],
        "total": 0,
    }

    try:
        from ldap3 import SUBTREE
        conn.search(
            search_base=base_dn,
            search_filter="(&(objectClass=user)(objectCategory=person))",
            search_scope=SUBTREE,
            attributes=[
                "sAMAccountName", "displayName", "userAccountControl",
                "lastLogonTimestamp", "pwdLastSet", "memberOf",
            ],
        )

        now = datetime.now(timezone.utc)

        for entry in conn.entries:
            result["total"] += 1
            login = str(entry.sAMAccountName) if entry.sAMAccountName else "?"
            name = str(entry.displayName) if entry.displayName else ""

            uac = int(entry.userAccountControl.value) if entry.userAccountControl else 0

            # Отключённые
            if uac & UAC_DISABLED:
                result["disabled"].append({"login": login, "name": name})
                continue  # отключённые дальше не проверяем

            # Пароль не истекает
            if uac & UAC_PASSWORD_NEVER_EXPIRES:
                result["password_never_expires"].append({"login": login, "name": name})

            # Не входил > 90 дней
            last_logon = None
            if entry.lastLogonTimestamp:
                last_logon = filetime_to_dt(int(entry.lastLogonTimestamp.value))

            if last_logon:
                days = (now - last_logon).days
                if days > 90:
                    result["inactive_90d"].append({
                        "login": login,
                        "name": name,
                        "days": days,
                    })

        conn.unbind()
    except Exception as e:
        logger.error(f"Ошибка аудита: {e}")
        print(f"  ❌ Ошибка: {e}")

    return result


def print_audit(result: dict):
    """Красивый вывод."""
    if not result:
        return

    print()
    print("=" * 80)
    print("  АУДИТ ACTIVE DIRECTORY")
    print("=" * 80)
    print(f"  Всего пользователей: {result['total']}")
    print()

    # Отключённые
    disabled = result.get("disabled", [])
    if disabled:
        print(f"  🔴 ОТКЛЮЧЁННЫЕ УЧЁТКИ ({len(disabled)})")
        print("  " + "─" * 76)
        for u in disabled[:20]:
            print(f"     • {u['login']:<25} {u['name']}")
        if len(disabled) > 20:
            print(f"     ... и ещё {len(disabled) - 20}")
        print()

    # Пароль не истекает
    never_expires = result.get("password_never_expires", [])
    if never_expires:
        print(f"  🟡 ПАРОЛЬ НЕ ИСТЕКАЕТ ({len(never_expires)})")
        print("  " + "─" * 76)
        for u in never_expires[:20]:
            print(f"     • {u['login']:<25} {u['name']}")
        if len(never_expires) > 20:
            print(f"     ... и ещё {len(never_expires) - 20}")
        print()

    # Неактивные
    inactive = result.get("inactive_90d", [])
    if inactive:
        print(f"  🟡 НЕ ВХОДИЛИ > 90 ДНЕЙ ({len(inactive)})")
        print("  " + "─" * 76)
        for u in sorted(inactive, key=lambda x: -x["days"])[:20]:
            print(f"     • {u['login']:<25} {u['name']:<30} {u['days']} дней")
        if len(inactive) > 20:
            print(f"     ... и ещё {len(inactive) - 20}")
        print()

    # Итог
    print("=" * 80)
    print("  РЕКОМЕНДАЦИИ")
    print("=" * 80)
    print()
    if disabled:
        print(f"  • Отключённых учёток: {len(disabled)}. Проверь, все ли уволены.")
    if never_expires:
        print(f"  • Учёток с неистекающим паролем: {len(never_expires)}. Это риск безопасности!")
    if inactive:
        print(f"  • Неактивных >90 дней: {len(inactive)}. Возможно, уволены или забыты.")
    if not (disabled or never_expires or inactive):
        print("  ✅ Проблем не найдено.")
    print()


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  АУДИТ ACTIVE DIRECTORY")
    print("=" * 80)
    print()

    config = load_ad_config()
    if not is_ad_configured(config):
        show_ad_setup_help()
        input("  Нажми Enter...")
        return

    print(f"  Домен: {config['domain']}")
    print()
    print("  ⚠️  Аудит может занять 10-30 секунд (зависит от размера AD).")
    print()

    confirm = input("  Начать аудит? [Y/n]: ").strip().lower()
    if confirm == "n":
        return

    print()
    print("  🔍 Аудит AD...")

    result = audit_ad(config)
    print_audit(result)

    # Сохранение
    if result:
        import json
        from pathlib import Path
        output_dir = Path(__file__).parent.parent.parent.parent / "output" / "ad_audit"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = output_dir / f"ad_audit_{timestamp}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        print(f"  📄 Отчёт сохранён: {filepath}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
