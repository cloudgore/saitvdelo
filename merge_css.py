
import argparse
import hashlib
import re
import shutil
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "site.css"

SKIP = {
    ".git", ".css-migrate-backup", "node_modules",
    "dist", "backup", "backups", ".venv"
}

TAGS = re.compile(
    r"<style\b[^>]*>.*?</style\s*>|<link\b[^>]*>",
    re.I | re.S
)

URLS = re.compile(
    r"url\(\s*(['\"]?)(.*?)\1\s*\)",
    re.I | re.S
)


class Attributes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if not self.values:
            self.values = dict(attrs)


def attributes(tag):
    parser = Attributes()
    parser.feed(tag)
    return parser.values


def public_path(path):
    return "/" + path.relative_to(ROOT).as_posix()


def page_base(page):
    folder = page.parent.relative_to(ROOT).as_posix()
    return "/" if folder == "." else "/" + folder + "/"


def local_css(href, page):
    parts = urlsplit(href)

    if parts.scheme or parts.netloc or not parts.path:
        return None

    location = urljoin(page_base(page), parts.path)
    path = (ROOT / location.lstrip("/")).resolve()

    if not path.is_relative_to(ROOT):
        raise ValueError(f"Путь вне проекта: {href}")

    if not path.is_file():
        raise FileNotFoundError(
            f"Не найден CSS: {href} в {page}"
        )

    return path


def rewrite_urls(css, base):
    def replace(match):
        quote, value = match.group(1), match.group(2).strip()

        if (
            not value
            or value.startswith(("/", "#", "//"))
            or urlsplit(value).scheme
        ):
            return match.group(0)

        fixed = urljoin(base, value)
        return f"url({quote}{fixed}{quote})"

    return URLS.sub(replace, css)


def prepare_css(css, base, media="all"):
    css = re.sub(
        r"""@charset\s+['"][^'"]+['"]\s*;""",
        "",
        css,
        flags=re.I
    )

    if re.search(r"@(?:import|namespace)\b", css, re.I):
        raise ValueError(
            "Обнаружен @import или @namespace. "
            "Требуется ручная обработка."
        )

    css = rewrite_urls(css, base)

    if media and media.lower() != "all":
        css = f"@media {media} {{\n{css}\n}}"

    return css.strip()


def collect_page(page):
    html = page.read_text(encoding="utf-8-sig")
    chunks = []
    external = []

    def replace(match):
        tag = match.group(0)
        attrs = attributes(tag)

        if tag.lower().startswith("<link"):
            rel = (attrs.get("rel") or "").lower().split()

            if "stylesheet" not in rel:
                return tag

            href = attrs.get("href") or ""

            path = local_css(href, page)

            if path is None:
                external.append(href)
                return tag

            css = path.read_text(encoding="utf-8-sig")
            css = prepare_css(
                css,
                public_path(path),
                attrs.get("media") or "all"
            )

            chunks.append((str(path), css))
            return ""

        if attrs.get("type", "text/css").lower() != "text/css":
            raise ValueError(
                f"Неподдерживаемый тип <style> в {page}"
            )

        found = re.search(
            r"<style\b[^>]*>(.*?)</style\s*>",
            tag,
            re.I | re.S
        )

        if not found:
            return tag

        css = prepare_css(
            found.group(1),
            page_base(page),
            attrs.get("media") or "all"
        )

        identity = hashlib.sha256(
            css.encode("utf-8")
        ).hexdigest()

        chunks.append(("inline:" + identity, css))
        return ""

    changed = TAGS.sub(replace, html)

    for url in external:
        if not url.startswith("https://fonts.googleapis.com/"):
            raise ValueError(
                f"Внешний CSS требует ручной проверки: {url}"
            )

    identifier = hashlib.sha1(
        page.relative_to(ROOT).as_posix().encode()
    ).hexdigest()[:12]

    if not re.search(r"<html\b", changed, re.I):
        raise ValueError(f"Нет тега html: {page}")

    if not re.search(r"</head\s*>", changed, re.I):
        raise ValueError(f"Нет закрывающего head: {page}")

    changed = re.sub(
        r"<html\b",
        f'<html data-svd-page="{identifier}"',
        changed,
        count=1,
        flags=re.I
    )

    changed = re.sub(
        r"</head\s*>",
        '  <link rel="stylesheet" href="/site.css?v=1">\n</head>',
        changed,
        count=1,
        flags=re.I
    )

    inline_attributes = len(
        re.findall(r"\sstyle\s*=", html, re.I)
    )

    return {
        "path": page,
        "html": changed,
        "chunks": chunks,
        "id": identifier,
        "inline_attributes": inline_attributes
    }


def build_css(pages):
    sequences = [page["chunks"] for page in pages]
    common = 0

    if not sequences:
        return "", 0

    minimum = min(map(len, sequences))

    while common < minimum:
        first = sequences[0][common]

        if all(
            sequence[common] == first
            for sequence in sequences
        ):
            common += 1
        else:
            break

    output = [
        "/* Generated CSS: saitvdelo.ru */",
        "/* Check visually before publishing. */"
    ]

    for source, css in sequences[0][:common]:
        output.append(f"\n/* Shared: {source} */\n{css}")

    for page in pages:
        remaining = page["chunks"][common:]

        if not remaining:
            continue

        relative = page["path"].relative_to(ROOT)

        output.append(
            f"\n/* Page: {relative} */"
        )

        output.append(
            f'@scope (html[data-svd-page="{page["id"]}"]) {{'
        )

        for source, css in remaining:
            output.append(f"\n/* {source} */\n{css}")

        output.append("}")

    return "\n".join(output) + "\n", common


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить изменения"
    )

    args = parser.parse_args()

    if OUTPUT.exists():
        raise SystemExit(
            "site.css уже существует. "
            "Проверь предыдущую сборку."
        )

    html_files = sorted(
        path
        for path in ROOT.rglob("*.html")
        if not any(part in SKIP for part in path.parts)
    )

    if not html_files:
        raise SystemExit("HTML-файлы не найдены.")

    pages = []

    for page in html_files:
        print("Анализ:", page.relative_to(ROOT))
        pages.append(collect_page(page))

    css, shared_count = build_css(pages)

    total_blocks = sum(
        len(page["chunks"]) for page in pages
    )

    total_inline = sum(
        page["inline_attributes"] for page in pages
    )

    print("\n--- Результат ---")
    print("HTML-страниц:", len(pages))
    print("CSS-блоков и подключений:", total_blocks)
    print("Общих блоков:", shared_count)
    print("Размер site.css:", len(css.encode("utf-8")), "байт")
    print("Атрибутов style= (не изменены):", total_inline)

    if not args.apply:
        print("\nПредпросмотр завершён.")
        print("Для применения: py merge_css.py --apply")
        return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / ".css-migrate-backup" / stamp

    for page in pages:
        source = page["path"]
        destination = backup / source.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    OUTPUT.write_text(css, encoding="utf-8")

    for page in pages:
        page["path"].write_text(
            page["html"],
            encoding="utf-8"
        )

    print("\nГотово!")
    print("Создан:", OUTPUT)
    print("Резервные копии:", backup)
    print("Старые CSS-файлы не удалены.")


if __name__ == "__main__":
    main()
