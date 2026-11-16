
import argparse
import json
import re
import shutil
import xml.etree.ElementTree as ET

from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent

# ==========================================
# 1. СЕМАНТИЧЕСКАЯ КАРТА
# ==========================================

SEO = {
    "/": {
        "cluster": "создание сайтов / сайты под ключ",
        "title": "Создание сайтов под ключ от 5 000 ₽ | Сайт в дело",
        "description": (
            "Создание сайтов под ключ для бизнеса и специалистов. "
            "Лендинги и сайты-визитки от 5 000 ₽. "
            "Адаптивный дизайн, примеры работ и помощь с запуском."
        ),
        "h1": (
            "Создание сайтов под ключ "
            "<br><em>для бизнеса.</em>"
        )
    },

    "/uslugi/razrabotka-lendinga/": {
        "cluster": "создание лендинга / лендинг под ключ",
        "title": "Создание лендинга под ключ от 5 000 ₽ | Сайт в дело",
        "description": (
            "Создание лендинга под ключ от 5 000 ₽: "
            "до 8 смысловых блоков, адаптивный дизайн, "
            "форма обращения и помощь с запуском. "
            "Примеры работ."
        ),
        "h1": (
            "Создание лендинга "
            "<br><em>под ключ.</em>"
        )
    },

    "/uslugi/sozdanie-saita-vizitki/": {
        "cluster": "создание сайта-визитки / визитка под ключ",
        "title": (
            "Создание сайта-визитки под ключ "
            "от 5 000 ₽ | Сайт в дело"
        ),
        "description": (
            "Создание сайта-визитки под ключ от 5 000 ₽: "
            "до 5 страниц, адаптивный дизайн, разделы услуг "
            "и портфолио, помощь с запуском. Примеры сайтов."
        ),
        "h1": (
            "Создание сайта-визитки "
            "<br><em>под ключ.</em>"
        )
    }
}


# ==========================================
# 2. РЕГИОНАЛЬНЫЕ СТРАНИЦЫ
# ==========================================

CITIES = {
    "samara": "Самаре",
    "tolyatti": "Тольятти",
    "kazan": "Казани",
    "moscow": "Москве",
    "nizhny-novgorod": "Нижнем Новгороде",
    "orenburg": "Оренбурге",
    "penza": "Пензе",
    "saratov": "Саратове",
    "ufa": "Уфе",
    "ulyanovsk": "Ульяновске"
}

for slug, city in CITIES.items():
    path = f"/goroda/{slug}/"

    title = (
        "Создание сайтов в Самаре от 5 000 ₽ | Сайт в дело"
        if slug == "samara"
        else f"Создание сайтов в {city} под ключ | Сайт в дело"
    )

    SEO[path] = {
        "cluster": f"создание сайтов / {city}",
        "title": title,
        "h1": f"Создание сайтов <br><em>в {city}.</em>"
    }

    # Description городов не заменяем:
    # существующие описания уже уникальные.


# ==========================================
# 3. ТОЧЕЧНЫЕ ПРАВКИ H2, ТЕКСТОВ И ССЫЛОК
# ==========================================

EDITS = {
    "/": [
        (
            "<h2>Разработка сайтов<br><em>для разных задач.</em></h2>",
            "<h2>Создание сайтов <br><em>для разных задач.</em></h2>"
        ),
        (
            '<p class="service-note">Точный состав работ согласуем до старта.',
            '<p class="service-note">Создание сайта под ключ начинается '
            'с обсуждения задачи, структуры и дизайна. '
            'Точный состав работ согласуем до старта.'
        ),
        (
            '<a class="btn orange" href="/uslugi/razrabotka-lendinga/">Подробнее о лендинге',
            '<a class="btn orange" href="/uslugi/razrabotka-lendinga/">Создание лендинга под ключ'
        ),
        (
            '<a class="btn dark" href="/uslugi/sozdanie-saita-vizitki/">Подробнее о сайте-визитке',
            '<a class="btn dark" href="/uslugi/sozdanie-saita-vizitki/">Создание сайта-визитки'
        )
    ],

    "/uslugi/razrabotka-lendinga/": [
        (
            "<h2>Что входит<br><em>в лендинг под ключ.</em></h2>",
            "<h2>Что входит <br><em>в создание лендинга.</em></h2>"
        ),
        (
            '<p class="lead"><strong>В базовом объёме.</strong> Одна страница до 8 смысловых блоков.',
            '<p class="lead"><strong>Создание лендинга под ключ.</strong> '
            'В базовом объёме — одна страница до 8 смысловых блоков.'
        ),
        (
            '<a href="/goroda/samara/">Посмотрите страницу разработки сайтов для бизнеса Самары</a>',
            '<a href="/goroda/samara/">Создание сайтов в Самаре: условия и примеры</a>'
        )
    ],

    "/uslugi/sozdanie-saita-vizitki/": [
        (
            "<h2>Что входит<br><em>в разработку.</em></h2>",
            "<h2>Что входит <br><em>в создание сайта-визитки.</em></h2>"
        ),
        (
            '<p class="lead"><strong>В базовом объёме.</strong> До 5 страниц.',
            '<p class="lead"><strong>Сайт-визитка под ключ.</strong> '
            'В базовом объёме — до 5 страниц.'
        ),
        (
            '<a href="/goroda/samara/">Посмотрите страницу разработки сайтов для бизнеса Самары</a>',
            '<a href="/goroda/samara/">Создание сайтов в Самаре: условия и примеры</a>'
        )
    ],

    "/goroda/samara/": [
        (
            "<h2>Лендинг или<br><em>сайт-визитка?</em></h2>",
            "<h2>Лендинг или <br><em>сайт-визитка в Самаре?</em></h2>"
        ),
        (
            '<p class="growth-intro">Чтобы подготовить предложение, нужно понять объём работы.',
            '<p class="growth-intro">Создание сайта под ключ в Самаре '
            'начинается с выбора формата и объёма работ. '
            'Чтобы подготовить предложение, нужно понять объём работы.'
        ),
        (
            '<a class="btn orange" href="/uslugi/razrabotka-lendinga/">Подробнее о лендинге',
            '<a class="btn orange" href="/uslugi/razrabotka-lendinga/">Лендинг под ключ'
        ),
        (
            '<a class="btn dark" href="/uslugi/sozdanie-saita-vizitki/">Подробнее о визитке',
            '<a class="btn dark" href="/uslugi/sozdanie-saita-vizitki/">Сайт-визитка под ключ'
        )
    ]
}


# ==========================================
# 4. HTML-ИНСТРУМЕНТЫ
# ==========================================

HEAD = re.compile(
    r"(<head\b[^>]*>)(.*?)(</head\s*>)",
    re.I | re.S
)

TITLE = re.compile(
    r"<title\b[^>]*>.*?</title\s*>",
    re.I | re.S
)

META = re.compile(
    r"<meta\b[^>]*>",
    re.I | re.S
)

LINK = re.compile(
    r"<link\b[^>]*>",
    re.I | re.S
)

H1 = re.compile(
    r"(<h1\b[^>]*>)(.*?)(</h1\s*>)",
    re.I | re.S
)

JSONLD = re.compile(
    r"(<script\b[^>]*>)(.*?)(</script\s*>)",
    re.I | re.S
)


class TagAttrs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        self.fields = dict(attrs)


def attrs(tag):
    parser = TagAttrs()
    parser.feed(tag)
    return parser.fields


def put_title(head, title):
    matches = list(TITLE.finditer(head))

    if len(matches) != 1:
        raise ValueError(
            f"Ожидался один title, найдено {len(matches)}"
        )

    return TITLE.sub(
        lambda _: f"<title>{escape(title)}</title>",
        head,
        count=1
    )


def get_meta(head, field, key):
    matches = [
        match
        for match in META.finditer(head)
        if (
            attrs(match.group(0)).get(field) or ""
        ).lower() == key.lower()
    ]

    if len(matches) > 1:
        raise ValueError(f"Дубли метатега: {key}")

    return matches[0].group(0) if matches else None


def put_meta(head, field, key, value):
    tag = (
        f'<meta {field}="{key}" '
        f'content="{escape(value, quote=True)}">'
    )

    original = get_meta(head, field, key)

    if original:
        return head.replace(original, tag, 1)

    return head + tag


def put_canonical(head, url):
    matches = [
        match
        for match in LINK.finditer(head)
        if "canonical" in (
            attrs(match.group(0)).get("rel") or ""
        ).lower().split()
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Ожидался один canonical, найдено {len(matches)}"
        )

    tag = (
        f'<link rel="canonical" '
        f'href="{escape(url, quote=True)}">'
    )

    return head.replace(
        matches[0].group(0), tag, 1
    )


# ==========================================
# 5. СИНХРОНИЗАЦИЯ SCHEMA.ORG
# ==========================================

def sync_jsonld(head, url, title, description):

    def update_value(value):
        if isinstance(value, list):
            for item in value:
                update_value(item)

        elif isinstance(value, dict):
            types = value.get("@type", [])

            if isinstance(types, str):
                types = [types]

            is_current_page = (
                "WebPage" in types
                and value.get("url", "").rstrip("/")
                == url.rstrip("/")
            )

            if is_current_page:
                value["name"] = title
                value["description"] = description

            for item in value.values():
                if isinstance(item, (dict, list)):
                    update_value(item)

    def replace(match):
        opening, content, closing = match.groups()

        script_type = (
            attrs(opening).get("type") or ""
        ).lower()

        if script_type != "application/ld+json":
            return match.group(0)

        data = json.loads(content)

        update_value(data)

        serialized = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":")
        )

        serialized = serialized.replace("</", "<\\/")

        return opening + serialized + closing

    return JSONLD.sub(replace, head)


# ==========================================
# 6. БЕЗОПАСНЫЕ ТЕКСТОВЫЕ ЗАМЕНЫ
# ==========================================

def replace_exact(html, before, after, path):
    if before in html:
        count = html.count(before)

        if count != 1:
            raise ValueError(
                f"Дубли фрагмента на {path}: {before[:70]}"
            )

        return html.replace(before, after, 1)

    if after in html:
        return html

    raise ValueError(
        f"Не найден фрагмент на {path}: {before[:70]}"
    )


# ==========================================
# 7. ОБРАБОТКА ОДНОЙ СТРАНИЦЫ
# ==========================================

def migrate(html, path, url):
    rule = SEO.get(path)

    if rule is None:
        # Портфолио и служебные страницы
        # оставляем без массовой замены.
        return html

    h1_matches = list(H1.finditer(html))

    if len(h1_matches) != 1:
        raise ValueError(
            f"На странице {path} найдено H1: {len(h1_matches)}"
        )

    h1 = h1_matches[0]

    html = (
        html[:h1.start(2)]
        + rule["h1"]
        + html[h1.end(2):]
    )

    for before, after in EDITS.get(path, []):
        html = replace_exact(
            html, before, after, path
        )

    match = HEAD.search(html)

    if not match:
        raise ValueError(f"Нет head: {path}")

    head = match.group(2)

    title = rule["title"]

    description_tag = get_meta(
        head, "name", "description"
    )

    if not description_tag:
        raise ValueError(
            f"Нет description: {path}"
        )

    description = rule.get(
        "description",
        attrs(description_tag).get("content", "")
    )

    if not description:
        raise ValueError(
            f"Пустое description: {path}"
        )

    # HTML SEO
    head = put_title(head, title)

    head = put_meta(
        head, "name", "description", description
    )

    head = put_canonical(head, url)

    # Open Graph
    head = put_meta(
        head, "property", "og:title", title
    )

    head = put_meta(
        head, "property", "og:description",
        description
    )

    head = put_meta(
        head, "property", "og:url", url
    )

    # Twitter / social preview
    head = put_meta(
        head, "name", "twitter:card", "summary"
    )

    head = put_meta(
        head, "name", "twitter:title", title
    )

    head = put_meta(
        head, "name", "twitter:description",
        description
    )

    # Schema.org WebPage
    head = sync_jsonld(
        head, url, title, description
    )

    return (
        html[:match.start(2)]
        + head
        + html[match.end(2):]
    )


# ==========================================
# 8. ПОЛУЧЕНИЕ СТРАНИЦ ИЗ SITEMAP
# ==========================================

def get_sitemap_pages():
    root = ET.parse(
        ROOT / "sitemap.xml"
    ).getroot()

    result = []
    seen = set()

    for entry in root.findall("./{*}url"):
        location = entry.find("{*}loc")

        if location is None or not location.text:
            continue

        url = location.text.strip()
        parsed = urlsplit(url)

        if (
            parsed.scheme != "https"
            or parsed.netloc != "saitvdelo.ru"
        ):
            raise ValueError(
                f"Неожиданный URL: {url}"
            )

        path = unquote(parsed.path)

        if not path.endswith("/"):
            raise ValueError(
                f"Ожидался URL с / на конце: {url}"
            )

        target = (
            ROOT / path.lstrip("/") / "index.html"
        ).resolve()

        if (
            not target.is_relative_to(ROOT)
            or not target.is_file()
        ):
            raise ValueError(
                f"Нет локального HTML для {url}"
            )

        if path in seen:
            raise ValueError(
                f"Повтор URL в sitemap: {url}"
            )

        result.append((path, target, url))
        seen.add(path)

    missing = set(SEO) - seen

    if missing:
        raise ValueError(
            f"SEO-страницы отсутствуют в sitemap: {sorted(missing)}"
        )

    return result


# ==========================================
# 9. ЗАПУСК
# ==========================================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить SEO-изменения"
    )

    args = parser.parse_args()

    changes = []
    pages = get_sitemap_pages()

    print("Страниц в Sitemap:", len(pages))
    print()

    # Сначала анализируем ВСЕ страницы.
    # Если возникает ошибка, ничего не записываем.

    for path, file, url in pages:
        original = file.read_text(
            encoding="utf-8-sig"
        )

        updated = migrate(
            original, path, url
        )

        status = (
            "ИЗМЕНИТСЯ"
            if original != updated
            else "без изменений"
        )

        print(f"{status:14} {path}")

        if original != updated:
            changes.append(
                (file, updated)
            )

    print()
    print("Изменяемых страниц:", len(changes))

    if not args.apply:
        print("Пробный запуск: файлы не изменены.")
        print("Для применения: py optimize_site.py --apply")
        return

    if not changes:
        print("Новых изменений нет.")
        return

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S-%f"
    )

    backup = ROOT / ".seo-backup" / stamp

    # Сохраняем оригиналы перед изменением.
    for file, updated in changes:
        destination = (
            backup / file.relative_to(ROOT)
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        shutil.copy2(
            file, destination
        )

    # Применяем изменения.
    for file, updated in changes:
        file.write_text(
            updated,
            encoding="utf-8"
        )

    print()
    print("SEO-обновление завершено!")
    print("Резервные копии:", backup)
    print("Проверь изменения командой git diff.")


if __name__ == "__main__":
    main()
