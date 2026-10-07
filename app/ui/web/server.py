"""
Веб-сервер Flask для sysadmin-usb.
Запускает веб-интерфейс с дашбордом.
"""
import os
import sys
import json
import threading
import webbrowser
from pathlib import Path
from datetime import datetime

# Добавляем libs в путь
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT / "libs"))

from app.core.logger import setup_logger

logger = setup_logger("web-server")

try:
    from flask import Flask, render_template, jsonify, request
except ImportError:
    print("  ❌ Flask не установлен.")
    print("     Установи: pip install --target=libs/ flask")
    sys.exit(1)


def create_app(config: dict) -> Flask:
    """Создаёт Flask-приложение."""
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config["SECRET_KEY"] = os.environ.get("WEB_SECRET_KEY", "dev-secret-key")
    app.config["USBU"] = config

    # =================================================================
    # Маршруты
    # =================================================================

    @app.route("/")
    def index():
        """Главная страница."""
        return render_template("index.html", config=config)

    @app.route("/api/status")
    def api_status():
        """Статус системы."""
        from app.os_detect import os_detector
        info = os_detector.get_system_info()
        return jsonify({
            "ok": True,
            "hostname": info["hostname"],
            "os": info["system"],
            "release": info["release"],
            "time": datetime.now().isoformat(),
        })

    @app.route("/api/categories")
    def api_categories():
        """Список категорий."""
        categories = config.get("categories", {})
        enabled = {
            k: {"name": v["name"], "functions": v.get("functions", [])}
            for k, v in categories.items() if v.get("enabled")
        }
        return jsonify(enabled)

    @app.route("/api/health")
    def api_health():
        """Health check."""
        try:
            from app.categories.system.health_check import runner
            results = runner.run_all_checks()
            summary = runner.summarize(results)
            return jsonify({"ok": True, "summary": summary, "results": results})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/printers")
    def api_printers():
        """Список принтеров."""
        try:
            import yaml
            printers = []
            for cfg_name in ["printers.yaml", "printers_auto.yaml"]:
                cfg = PROJECT_ROOT / "config" / cfg_name
                if cfg.exists():
                    with open(cfg, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    printers.extend(data.get("printers", []))
            return jsonify({"ok": True, "printers": printers, "count": len(printers)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/backups")
    def api_backups():
        """Список бэкапов."""
        try:
            from app.categories.backup.list import list_backups, format_size
            backups = list_backups()
            return jsonify({
                "ok": True,
                "count": len(backups),
                "backups": [
                    {
                        "name": b["name"],
                        "date": b["date_str"],
                        "size": format_size(b["size"]),
                        "path": str(b["path"]),
                    }
                    for b in backups
                ],
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/network/last")
    def api_network_last():
        """Последнее сканирование сети."""
        try:
            scans_dir = PROJECT_ROOT / "output" / "scans"
            if not scans_dir.exists():
                return jsonify({"ok": True, "count": 0, "devices": []})

            files = sorted(scans_dir.glob("network_*.json"), reverse=True)
            if not files:
                return jsonify({"ok": True, "count": 0, "devices": []})

            with open(files[0], "r", encoding="utf-8") as f:
                data = json.load(f)

            return jsonify({
                "ok": True,
                "count": len(data.get("devices", [])),
                "scanned_at": data.get("scanned_at", ""),
                "devices": data.get("devices", []),
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/reports")
    def api_reports():
        """Список отчётов."""
        try:
            reports_dir = PROJECT_ROOT / "output" / "reports"
            if not reports_dir.exists():
                return jsonify({"ok": True, "reports": []})

            reports = []
            for f in sorted(reports_dir.glob("report_*.md"), reverse=True)[:20]:
                stat = f.stat()
                reports.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "date": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                })
            return jsonify({"ok": True, "reports": reports})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/run/<category>/<func_id>", methods=["POST"])
    def api_run(category: str, func_id: str):
        """Запускает функцию (в разработке — только заглушка)."""
        return jsonify({
            "ok": False,
            "error": "Запуск функций из веба пока не поддерживается. Используй консоль.",
        }), 501

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"ok": False, "error": "Не найдено"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"ok": False, "error": "Ошибка сервера"}), 500

    return app


def run_web(config: dict):
    """Запускает веб-сервер."""
    app = create_app(config)

    host = config.get("web", {}).get("host", "127.0.0.1")
    port = config.get("web", {}).get("port", 8080)

    url = f"http://{host}:{port}"

    print()
    print("=" * 68)
    print("  🌐 ВЕБ-ИНТЕРФЕЙС")
    print("=" * 68)
    print()
    print(f"  Сервер: {url}")
    print(f"  Для остановки: Ctrl+C")
    print()

    # Открываем браузер через 1 секунду
    def open_browser():
        import time
        time.sleep(1)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print()
        print("  🛑 Сервер остановлен.")
        print()
