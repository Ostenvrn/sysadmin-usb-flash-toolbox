"""
Экспорт отчётов.
- Markdown → HTML (для браузера)
- JSON → CSV (для Excel)
"""
import json
import csv
import html
from pathlib import Path
from datetime import datetime

from app.core.logger import setup_logger

logger = setup_logger("reports-export")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
REPORTS_DIR = PROJECT_ROOT / "output" / "reports"


def list_reports() -> list:
    """Список JSON-отчётов."""
    if not REPORTS_DIR.exists():
        return []

    files = sorted(REPORTS_DIR.glob("report_*.json"), reverse=True)
    return files


def json_to_csv(json_path: Path) -> Path:
    """Конвертирует JSON-отчёт в CSV."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    csv_path = json_path.with_suffix(".csv")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")

        # Заголовок
        writer.writerow(["Секция", "Ключ", "Значение"])

        # Система
        for key, val in data.get("system", {}).items():
            if key == "disks":
                for d in val:
                    writer.writerow(["Диски", d.get("path"), f"{d.get('percent')}% ({d.get('used_gb')}/{d.get('total_gb')} ГБ)"])
            else:
                writer.writerow(["Система", key, val])

        # Health Check
        hc = data.get("health_check", {})
        summary = hc.get("summary", {})
        writer.writerow(["Health Check", "Всего", summary.get("total", 0)])
        writer.writerow(["Health Check", "OK", summary.get("ok", 0)])
        writer.writerow(["Health Check", "Warning", summary.get("warning", 0)])
        writer.writerow(["Health Check", "Critical", summary.get("critical", 0)])

        for r in hc.get("results", []):
            for prob in r.get("problems", []):
                writer.writerow([f"HC: {r['category']}", r.get("status"), prob])

        # Принтеры
        for p in data.get("printers", {}).get("printers", []):
            writer.writerow(["Принтеры", p.get("name"), f"{p.get('ip')} — {p.get('model')}"])

        # Бэкапы
        for b in data.get("backups", {}).get("backups", []):
            writer.writerow(["Бэкапы", b.get("name"), f"{b.get('date')} — {b.get('size')}"])

        # Сеть
        for d in data.get("network", {}).get("devices", []):
            writer.writerow(["Сеть", d.get("ip"), f"{d.get('hostname') or '—'} — {d.get('vendor') or '—'}"])

    return csv_path


def markdown_to_html(md_path: Path) -> Path:
    """Конвертирует Markdown в HTML (простая конвертация)."""
    with open(md_path, "r", encoding="utf-8") as f:
        md = f.read()

    # Простой конвертер (без внешних библиотек)
    lines = md.split("\n")
    html_lines = []

    html_lines.append("<!DOCTYPE html>")
    html_lines.append("<html lang='ru'>")
    html_lines.append("<head>")
    html_lines.append("<meta charset='UTF-8'>")
    html_lines.append(f"<title>{md_path.stem}</title>")
    html_lines.append("<style>")
    html_lines.append("""
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #c9d1d9; max-width: 1200px; margin: 20px auto; padding: 20px; }
        h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
        h2 { color: #58a6ff; margin-top: 30px; }
        h3 { color: #79c0ff; }
        table { border-collapse: collapse; width: 100%; margin: 15px 0; }
        th, td { border: 1px solid #30363d; padding: 8px; text-align: left; }
        th { background: #161b22; color: #58a6ff; }
        tr:nth-child(even) { background: #161b22; }
        code { background: #161b22; padding: 2px 6px; border-radius: 4px; }
        ul { padding-left: 20px; }
        li { margin: 5px 0; }
        strong { color: #79c0ff; }
    """)
    html_lines.append("</style>")
    html_lines.append("</head>")
    html_lines.append("<body>")

    in_table = False
    for line in lines:
        line = line.strip()

        if line.startswith("# "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True

            cells = [c.strip() for c in line.strip("|").split("|")]
            # Пропускаем разделитель |---|
            if all(c.startswith("-") or c == "" for c in cells):
                continue

            if html_lines[-1] == "<table>":
                html_lines.append("<tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in cells) + "</tr>")
            else:
                html_lines.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
        elif line.startswith("- "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.startswith("**"):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            # Жирный
            text = line.replace("**", "")
            html_lines.append(f"<p><strong>{html.escape(text)}</strong></p>")
        elif line:
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<p>{html.escape(line)}</p>")

    if in_table:
        html_lines.append("</table>")

    html_lines.append("</body>")
    html_lines.append("</html>")

    html_path = md_path.with_suffix(".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_lines))

    return html_path


def run():
    """Точка входа."""
    print()
    print("=" * 80)
    print("  ЭКСПОРТ ОТЧЁТОВ")
    print("=" * 80)
    print()

    reports = list_reports()

    if not reports:
        print("  📭 Отчётов не найдено.")
        print("  Сначала запусти «Сгенерировать отчёт».")
        print()
        input("  Нажми Enter...")
        return

    print(f"  Доступно отчётов: {len(reports)}")
    print()
    for i, r in enumerate(reports[:20], start=1):
        print(f"    [{i:2}] {r.name}")

    print("    [0] ← Назад")
    print()

    choice = input("  Выбери отчёт: ").strip()
    if choice == "0":
        return

    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(reports[:20]):
        print("  Неверный выбор.")
        input("  Нажми Enter...")
        return

    report = reports[int(choice) - 1]

    print()
    print("  Что экспортировать?")
    print("    [1] HTML (для браузера)")
    print("    [2] CSV (для Excel)")
    print("    [3] Оба формата")
    print()

    fmt = input("  Выбор [3]: ").strip() or "3"

    md_path = report.with_suffix(".md")

    if fmt in ("1", "3"):
        if md_path.exists():
            html_path = markdown_to_html(md_path)
            print(f"  ✅ HTML: {html_path}")
        else:
            print(f"  ⚠️  Markdown не найден: {md_path}")

    if fmt in ("2", "3"):
        csv_path = json_to_csv(report)
        print(f"  ✅ CSV: {csv_path}")

    print()
    input("  Нажми Enter для продолжения...")


if __name__ == "__main__":
    run()
