import os
import re
import json
import time
import traceback
from collections import deque
from datetime import datetime
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

START_URL = "https://www.42wide.com/food3/index.php"

ALLOWED_HOSTS = {"42wide.com", "www.42wide.com"}
ALLOWED_PATH_PREFIX = "/food3"

REQUEST_TIMEOUT = 15
CRAWL_DELAY_SECONDS = 0.3
MAX_PAGES = 20000
MAX_RECIPE_PAGES = 1000
MAX_DEPTH = 8
MAX_RETRIES = 3

# Match final segment like 745-nice-chickpeas-dish anywhere in the path
RECIPE_URL_RE = re.compile(r"/(?:[^/]+/)*\d+-[a-zA-Z0-9-]+/?$")

# Category/tag/list pages are usually crawl targets
CATEGORY_KEYWORDS = ("category", "categories", "tag", "tags", "list", "recipes")

# Strong recipe text markers
RECIPE_TEXT_KEYS = (
    "ingredients",
    "method",
    "preparation",
    "serves",
    "cook time",
    "prep time",
    "difficulty",
    "instructions"
)

SKIP_SUBSTRINGS = (
    "login", "layout=", "task=", "search", "limit=", "javascript:",
    "mailto:", "print", "feed", "rss", "account", "profile"
)

os.makedirs("saved_recipes", exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
})

def log_error(message, exc=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("errors.log", "a", encoding="utf-8") as f:
        f.write(f"\n[{ts}] {message}\n")
        if exc is not None:
            f.write(f"{traceback.format_exc()}\n")

def log_line(filename, text):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/")

def is_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]

        if host not in ALLOWED_HOSTS:
            return False

        if not parsed.path.startswith(ALLOWED_PATH_PREFIX):
            return False

        lower = url.lower()
        if any(s in lower for s in SKIP_SUBSTRINGS):
            return False

        return True
    except Exception as e:
        log_error(f"is_allowed() failed for {url}", e)
        return False

def looks_like_recipe_url(url: str) -> bool:
    try:
        p = urlparse(url)
        path = p.path.lower()
        return bool(RECIPE_URL_RE.search(path))
    except Exception as e:
        log_error(f"looks_like_recipe_url() failed for {url}", e)
        return False

def is_category_like(url: str) -> bool:
    lower = url.lower()
    if any(s in lower for s in SKIP_SUBSTRINGS):
        return False
    return any(k in lower for k in CATEGORY_KEYWORDS)

def extract_links(page_url: str, html: str):
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href:
                continue
            full = normalize_url(urljoin(page_url, href))
            yield full
    except Exception as e:
        log_error(f"extract_links() failed for {page_url}", e)

def fetch_with_retry(url: str, timeout: int = REQUEST_TIMEOUT, retries: int = MAX_RETRIES):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                return r
            last_error = RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:
            last_error = e

        if attempt < retries:
            time.sleep(1.5 * attempt)

    if last_error is not None:
        raise last_error
    return None

def has_recipe_content(html: str) -> bool:
    try:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True).lower()
        return any(key in text for key in RECIPE_TEXT_KEYS)
    except Exception:
        return False

def cleanup_filename(url: str) -> str:
    path = urlparse(url).path
    slug = path.strip("/").split("/")[-1]
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug).strip("_")
    if not safe:
        safe = "recipe"
    return safe

def unique_filename(url: str, used_names: set) -> str:
    base = cleanup_filename(url)
    name = base
    counter = 1
    while name in used_names:
        name = f"{base}_{counter}"
        counter += 1
    used_names.add(name)
    return name

def save_recipe_html(url: str, html: str, used_names: set, manifest: list):
    filename = unique_filename(url, used_names)
    full_path = f"saved_recipes/{filename}.html"
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(html)

    manifest.append({
        "url": url,
        "filename": full_path,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return full_path

def crawl_site(start_url):
    queue = deque([(normalize_url(start_url), 0)])
    visited = set()
    recipe_urls = set()
    recipe_manifest = []
    used_names = set()
    recipe_count = 0

    while queue and len(visited) < MAX_PAGES:
        url, depth = queue.popleft()
        if url in visited:
            continue
        if depth > MAX_DEPTH:
            continue
        visited.add(url)

        if not is_allowed(url):
            continue

        try:
            print(f"Fetching: {url}")
            log_line("visited_urls.log", url)

            r = fetch_with_retry(url)
            if r is None:
                continue

            content_type = r.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                continue

            html = r.text

            # If this page looks like a recipe URL and has recipe content, save it
            if looks_like_recipe_url(url) and has_recipe_content(html):
                recipe_urls.add(url)
                if url not in [m["url"] for m in recipe_manifest]:
                    filename = save_recipe_html(url, html, used_names, recipe_manifest)
                    recipe_count += 1
                    print(f"Saved recipe HTML: {filename}")
                    if recipe_count >= MAX_RECIPE_PAGES:
                        break

            # Keep crawling category/tag/list pages and recipe pages
            for link in extract_links(url, html):
                if not is_allowed(link):
                    continue

                if looks_like_recipe_url(link):
                    # We don't save immediately unless content is a real recipe page
                    try:
                        recipe_page = fetch_with_retry(link)
                        if recipe_page is not None and has_recipe_content(recipe_page.text):
                            recipe_urls.add(link)
                            if link not in [m["url"] for m in recipe_manifest]:
                                filename = save_recipe_html(link, recipe_page.text, used_names, recipe_manifest)
                                recipe_count += 1
                                print(f"Saved discovered recipe HTML: {filename}")
                                if recipe_count >= MAX_RECIPE_PAGES:
                                    break
                    except Exception as e:
                        log_error(f"Failed to validate recipe URL {link}", e)

                if is_category_like(link) and link not in visited:
                    queue.append((link, depth + 1))

            if recipe_count >= MAX_RECIPE_PAGES:
                break

            time.sleep(CRAWL_DELAY_SECONDS)

        except Exception as e:
            log_error(f"Request failed for {url}", e)

    with open("found_recipes.txt", "w", encoding="utf-8") as f:
        for recipe in sorted(recipe_urls):
            f.write(recipe + "\n")

    with open("recipe_manifest.json", "w", encoding="utf-8") as f:
        json.dump(recipe_manifest, f, indent=2, ensure_ascii=False)

    print(f"\nFinished.")
    print(f"Unique recipe URLs discovered: {len(recipe_urls)}")
    print(f"Recipe HTML files saved: {recipe_count}")

if __name__ == "__main__":
    try:
        crawl_site(START_URL)
    except Exception as e:
        log_error("Fatal scraper error", e)
        print(f"Fatal scraper error: {e}")
