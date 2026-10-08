"""
Проверка безопасности.
Кроссплатформенно: Linux (ufw) + Windows (Defender, Firewall).
"""
import json

from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-security")


def check_security() -> dict:
    result = {
        "category": "Безопасность",
        "status": "ok",
        "problems": [],
        "recommendations": [],
        "details": {},
    }

    if os_detector.is_windows:
        result = _check_windows(result)
    elif os_detector.is_linux:
        result = _check_linux(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"ОС {os_detector.system} не поддерживается")

    return result


def _check_windows(result: dict) -> dict:
    """Defender + Firewall на Windows."""
    # Defender
    ps_cmd = (
        "$d = Get-MpComputerStatus -ErrorAction SilentlyContinue; "
        "if ($d) { $d | Select-Object AntivirusEnabled,"
        "RealTimeProtectionEnabled,AntivirusSignatureAge | ConvertTo-Json -Compress } "
        "else { 'none' }"
    )
    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc == 0 and stdout.strip() and stdout.strip() != "none":
        try:
            data = json.loads(stdout)
            av_enabled = data.get("AntivirusEnabled", False)
            rt_enabled = data.get("RealTimeProtectionEnabled", False)
            sig_age = data.get("AntivirusSignatureAge", -1)

            result["details"]["antivirus_enabled"] = av_enabled
            result["details"]["realtime_protection"] = rt_enabled
            result["details"]["signature_age_days"] = sig_age

            if not av_enabled:
                result["status"] = "critical"
                result["problems"].append("🔴 Антивирус отключён!")
                result["recommendations"].append(
                    "Включите Windows Defender в настройках безопасности."
                )
            elif not rt_enabled:
                result["status"] = "warning"
                result["problems"].append("🟡 Защита в реальном времени отключена")

            if sig_age and sig_age > 7:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Базы антивируса устарели: {sig_age} дней"
                )
                result["recommendations"].append(
                    "Обновите базы Defender: wuauclt /detectnow"
                )
        except Exception as e:
            logger.error(f"Ошибка парсинга Defender: {e}")

    # Firewall
    ps_cmd = (
        "Get-NetFirewallProfile | Select-Object Name,Enabled | "
        "ConvertTo-Json -Compress"
    )
    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc == 0 and stdout.strip():
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]

            disabled = [p.get("Name") for p in data if not p.get("Enabled", True)]
            result["details"]["firewall_disabled_profiles"] = disabled

            if disabled:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Firewall отключён: {', '.join(disabled)}"
                )
                result["recommendations"].append(
                    "Включите Firewall в Безопасности Windows."
                )
        except Exception as e:
            logger.error(f"Ошибка парсинга Firewall: {e}")

    return result


def _check_linux(result: dict) -> dict:
    """UFW + обновления безопасности на Linux."""
    # UFW
    rc, stdout, _ = os_detector.run_command(["sudo", "ufw", "status"])
    if rc == 0:
        status_line = stdout.splitlines()[0] if stdout else ""
        result["details"]["ufw"] = status_line

        if "inactive" in status_line.lower():
            result["status"] = "warning"
            result["problems"].append("🟡 UFW (firewall) неактивен")
            result["recommendations"].append(
                "Включите UFW: sudo ufw enable"
            )

    # Обновления безопасности
    rc, stdout, _ = os_detector.run_command(["apt", "list", "--upgradable"])
    if rc == 0:
        security_updates = [
            line for line in stdout.splitlines() if "security" in line.lower()
        ]
        result["details"]["security_updates"] = len(security_updates)

        if len(security_updates) > 0:
            if result["status"] == "ok":
                result["status"] = "warning"
            result["problems"].append(
                f"🟡 Доступно {len(security_updates)} обновлений безопасности"
            )
            for line in security_updates[:3]:
                pkg = line.split("/")[0]
                result["problems"].append(f"   • {pkg}")
            result["recommendations"].append(
                "Установите обновления: sudo apt update && sudo apt upgrade"
            )

    return result
