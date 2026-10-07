"""
Проверка безопасности.
- Windows: Defender, Firewall
- Linux: firewall (ufw/iptables), обновления безопасности
"""
from app.os_detect import os_detector
from app.core.logger import setup_logger

logger = setup_logger("check-security")


def check_security() -> dict:
    """Проверяет безопасность."""
    result = {
        "category": "Безопасность",
        "status": "ok",
        "problems": [],
        "details": {},
    }

    if os_detector.is_windows:
        result = _check_windows(result)
    elif os_detector.is_linux:
        result = _check_linux(result)
    else:
        result["status"] = "warning"
        result["problems"].append(f"🟡 ОС {os_detector.system} не поддерживается")

    return result


def _check_windows(result: dict) -> dict:
    """Проверка безопасности на Windows."""
    # 1. Windows Defender
    ps_cmd = (
        "$defender = Get-MpComputerStatus -ErrorAction SilentlyContinue; "
        "if ($defender) { "
        "$defender | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,"
        "AntivirusSignatureAge | ConvertTo-Json -Compress "
        "} else { 'none' }"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc == 0 and stdout.strip() and stdout.strip() != "none":
        import json
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
            elif not rt_enabled:
                result["status"] = "warning"
                result["problems"].append("🟡 Защита в реальном времени отключена")

            if sig_age and sig_age > 7:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Базы антивируса устарели: {sig_age} дней"
                )
        except Exception:
            pass

    # 2. Firewall
    ps_cmd = (
        "Get-NetFirewallProfile | "
        "Select-Object Name,Enabled | "
        "ConvertTo-Json -Compress"
    )

    rc, stdout, _ = os_detector.run_command(
        ["powershell", "-NoProfile", "-Command", ps_cmd]
    )

    if rc == 0 and stdout.strip():
        import json
        try:
            data = json.loads(stdout)
            if isinstance(data, dict):
                data = [data]

            disabled_profiles = [
                p.get("Name") for p in data if not p.get("Enabled", True)
            ]
            result["details"]["firewall_disabled_profiles"] = disabled_profiles

            if disabled_profiles:
                if result["status"] == "ok":
                    result["status"] = "warning"
                result["problems"].append(
                    f"🟡 Firewall отключён: {', '.join(disabled_profiles)}"
                )
        except Exception:
            pass

    return result


def _check_linux(result: dict) -> dict:
    """Проверка безопасности на Linux."""
    # 1. UFW
    rc, stdout, _ = os_detector.run_command(["sudo", "ufw", "status"])
    if rc == 0:
        status_line = stdout.splitlines()[0] if stdout else ""
        result["details"]["ufw"] = status_line

        if "inactive" in status_line.lower():
            result["status"] = "warning"
            result["problems"].append("🟡 UFW (firewall) неактивен")

    # 2. Проверка обновлений безопасности
    rc, stdout, _ = os_detector.run_command(
        ["apt", "list", "--upgradable"]
    )
    if rc == 0:
        security_updates = [
            line for line in stdout.splitlines()
            if "security" in line.lower()
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

    # 3. Права на sudoers
    rc, _, _ = os_detector.run_command(["sudo", "-n", "true"])
    if rc != 0:
        result["details"]["sudo_passwordless"] = False
    else:
        result["details"]["sudo_passwordless"] = True

    return result
