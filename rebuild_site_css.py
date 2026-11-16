
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import re
import shutil

ROOT = Path(__file__).resolve().parent

CSS_FILES = [
    "style.css",
    "identity.css",
    "portfolio.css",
    "seo.css",
    "personal.css",
    "growth.css",
    "today.css",
    "contacts.css",
    "consent.css",
]

SKIP = {
    ".git", ".seo-backup", ".css-backup",
    ".css-migrate-backup", "node_modules", ".venv"
}

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()

parts = []

for name in CSS_FILES:
    path = ROOT / name

    if not path.is_file():
        raise FileNotFoundError(name)

    content = path.read_text(encoding="utf-8-sig")
    parts.append(f"\n/* {name} */\n{content}\n")

# Восстанавливаем стили, которые были
# внутри <style> на странице 404.html.
error_page = (ROOT / "404.html").read_text(
    encoding="utf-8"
)

match = re.search(
    r'data-svd-page="([^"]+)"',
    error_page
)

if not match:
    raise RuntimeError(
        "В 404.html не найден data-svd-page"
    )

prefix = f'html[data-svd-page="{match.group(1)}"]'

parts.append(f"""
/* 404 page */
{prefix} main {{
    max-width: 800px;
    margin: 12vh auto;
    padding: 30px;
}}
{prefix} h1 {{
    font-size: clamp(36px, 7vw, 70px);
    line-height: 1.1;
}}
{prefix} p {{
    line-height: 1.8;
}}
{prefix} a {{
    color: #2c41ed;
    text-decoration: underline;
}}
""")

css = "\n".join(parts)
version = hashlib.sha256(
    css.encode("utf-8")
).hexdigest()[:10]

changes = []

for file in ROOT.rglob("*.html"):
    if any(part in SKIP for part in file.relative_to(ROOT).parts):
        continue

    html = file.read_text(encoding="utf-8-sig")

    updated, count = re.subn(
        r'href=(["\'])/site\.css(?:\?[^"\']*)?\1',
        lambda m: (
            f'href={m.group(1)}/site.css?v={version}{m.group(1)}'
        ),
        html
    )

    if count > 1:
        raise RuntimeError(
            f"Несколько подключений site.css: {file}"
        )

    if count == 1 and updated != html:
        changes.append((file, updated))

print("CSS-файлов:", len(CSS_FILES))
print("Размер нового CSS:", len(css.encode("utf-8")), "байт")
print("Версия CSS:", version)
print("HTML для обновления:", len(changes))

if not args.apply:
    print("Проверка завершена. Ничего не изменено.")
else:
    output = ROOT / "site.css"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / ".css-backup" / stamp
    backup.mkdir(parents=True, exist_ok=True)

    if output.exists():
        shutil.copy2(output, backup / "site.css")

    for file, updated in changes:
        destination = backup / file.relative_to(ROOT)
        destination.parent.mkdir(
            parents=True, exist_ok=True
        )
        shutil.copy2(file, destination)

    output.write_text(css, encoding="utf-8")

    for file, updated in changes:
        file.write_text(updated, encoding="utf-8")

    print("Готово. Резервные копии:", backup)
