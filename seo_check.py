
import argparse
import csv
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin


class SEOParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.robots = ""
        self.h1 = []
        self.in_title = False
        self.in_h1 = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "title":
            self.in_title = True

        if tag == "h1":
            self.in_h1 = True
            self.h1.append("")

        if tag == "meta":
            name = attrs.get("name", "").lower()
            content = attrs.get("content", "")

            if name == "description":
                self.description = content

            if name in ("robots", "googlebot", "yandex"):
                self.robots += f"{name}: {content}; "

        if tag == "link":
            rel = attrs.get("rel", "").lower()
            if "canonical" in rel.split():
                self.canonical = attrs.get("href", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data

        if self.in_h1 and self.h1:
            self.h1[-1] += data


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 SEO-Audit"}
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return (
                response.status,
                response.geturl(),
                response.read(4 * 1024 * 1024),
                ""
            )

    except urllib.error.HTTPError as e:
        return e.code, e.geturl(), b"", str(e)

    except Exception as e:
        return 0, url, b"", str(e)


def get_sitemap_urls(sitemap_url, visited=None):
    if visited is None:
        visited = set()

    if sitemap_url in visited:
        return []

    visited.add(sitemap_url)

    status, final_url, data, error = fetch(sitemap_url)

    if status != 200:
        raise RuntimeError(
            f"Не удалось открыть Sitemap: {sitemap_url}. "
            f"HTTP {status}. {error}"
        )

    root = ET.fromstring(data)
    tag = root.tag.split("}")[-1]

    locations = [
        element.text.strip()
        for element in root.iter()
        if element.tag.split("}")[-1] == "loc"
        and element.text
    ]

    if tag == "sitemapindex":
        result = []
        for location in locations:
            result.extend(
                get_sitemap_urls(location, visited)
            )
        return result

    return locations


def check_page(url):
    status, final_url, data, error = fetch(url)

    result = {
        "URL": url,
        "HTTP": status,
        "Final URL": final_url,
        "Title": "",
        "Description": "",
        "H1": "",
        "H1 Count": 0,
        "Canonical": "",
        "Robots": "",
        "Problems": ""
    }

    problems = []

    if status != 200:
        problems.append(f"HTTP {status}: {error}")

    if final_url.rstrip("/") != url.rstrip("/"):
        problems.append("Редирект")

    if status == 200:
        parser = SEOParser()

        try:
            parser.feed(data.decode("utf-8", errors="replace"))
        except Exception as e:
            problems.append(f"Ошибка HTML: {e}")

        result["Title"] = parser.title.strip()
        result["Description"] = parser.description.strip()
        result["H1"] = " | ".join(
            h.strip() for h in parser.h1
        )
        result["H1 Count"] = len(parser.h1)
        result["Canonical"] = parser.canonical
        result["Robots"] = parser.robots

        if not result["Title"]:
            problems.append("Нет Title")

        if not result["Description"]:
            problems.append("Нет Description")

        if len(parser.h1) == 0:
            problems.append("Нет H1")

        if len(parser.h1) > 1:
            problems.append("Несколько H1")

        if not parser.canonical:
            problems.append("Нет Canonical")
        elif urljoin(final_url, parser.canonical).rstrip("/") != final_url.rstrip("/"):
            problems.append("Canonical отличается от URL")

        if "noindex" in parser.robots.lower():
            problems.append("NOINDEX")

    result["Problems"] = "; ".join(problems)
    return result


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("website")
    arg_parser.add_argument(
        "--out",
        default="seo_report.csv"
    )

    args = arg_parser.parse_args()

    sitemap_url = urljoin(
        args.website.rstrip("/") + "/",
        "sitemap.xml"
    )

    print("Читаю Sitemap:", sitemap_url)

    try:
        urls = list(dict.fromkeys(
            get_sitemap_urls(sitemap_url)
        ))
    except Exception as e:
        print("Ошибка:", e)
        return

    print("Найдено страниц:", len(urls))

    results = []

    for index, url in enumerate(urls, 1):
        print(f"[{index}/{len(urls)}] {url}")

        result = check_page(url)
        results.append(result)

        if result["Problems"]:
            print("  Проблемы:", result["Problems"])
        else:
            print("  OK")

        time.sleep(0.3)

    if not results:
        print("В Sitemap нет URL для проверки.")
        return

    with open(
        args.out,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=results[0].keys(),
            delimiter=";"
        )

        writer.writeheader()
        writer.writerows(results)

    print("\nПроверка завершена!")
    print("Отчёт:", args.out)
    print(
        "Страниц с замечаниями:",
        sum(bool(r["Problems"]) for r in results)
    )


if __name__ == "__main__":
    main()
