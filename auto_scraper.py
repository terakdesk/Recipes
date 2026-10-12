import json
import os
import re
import time
import traceback
from collections import deque
from datetime import datetime
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup

START_URLS = [
    "https://www.42wide.com/food3/",
    "https://42wide.com/food3/",
    "http://www.42wide.com/food3/",
    "http://42wide.com/food3/",
]

ALLOWED_HOSTS = {"42wide.com", "www.42wide.com"}
ALLOWED_PATH_PREFIX = "/food3"

REQUEST_TIMEOUT = 15
CRAWL_DELAY_SECONDS = 0.3
MAX_PAGES = 5000
MAX_RETRIES = 3
MAX_RECIPE_PAGES = 100  # stop after this many valid recipe pages

# Match recipe URL pattern like:
# /624-lamp-thai-green-curry
RECIPE_PATTERN = re.compile(r"/\d+-[a-zA-Z0-9\-]+/?$")

# Filters for URLs we don't want to process
SKIP_SUBSTRINGS = (
    "login", "layout=", "task=", "search", "limit=", "javascript:",
    "mailto:", "print", "feed", "rss"
)

os.makedirs("saved_recipes", exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 "
                  "Safari/537.36"
})

def log_error(message, exc=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("errors.log", "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}] {message}\n")
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

def looks_like_recipe(url: str) -> bool:
    try:
        parsed = urlparse(url)
        path = parsed.path or ""
        return bool(RECIPE_PATTERN.search(path))
    except Exception as e:
        log_error(f"looks_like_recipe() failed for {url}", e)
        return False

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
            continue

    if last_error is not None:
        raise last_error

    return None

def cleanup_filename(url: str) -> str:
    path = urlparse(url).path
    slug = path.strip("/").split("/")[-1]
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", slug).strip("_")
    if not safe:
        safe = "recipe"
    return safe

def save_recipe_html(url: str, html: str, recipe_manifest: list, seen_slugs: set):
    slug = cleanup_filename(url)
    safe_slug = slug
    suffix = 1
    while safe_slug in seen_slugs:
        safe_slug = f"{slug}_{suffix}"
        suffix += 1

    seen_slugs.add(safe_slug)
    filename = f"saved_recipes/{safe_slug}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    recipe_manifest.append({
        "url": url,
        "filename": filename,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return filename

def crawl_and_save(start_urls):
    queue = deque()
    for s in start_urls:
        queue.append(normalize_url(s))

    visited = set()
    recipe_urls = set()
    seen_slugs = set()
    recipe_manifest = []
    recipe_count = 0

    while queue and len(visited) < MAX_PAGES:
        url = queue.popleft()
        if url in visited:
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
                print(f"Skipping non-HTML page: {url}")
                continue

            html = r.text

            # Save recipe pages only
            if looks_like_recipe(url):
                recipe_urls.add(url)
                if url not in recipe_urls:
                    # this is redundant, but keeps logic clear
                    pass

                # Save only once per URL
                if url not in [item["url"] for item in recipe_manifest]:
                    filename = save_recipe_html(url, html, recipe_manifest, seen_slugs)
                    recipe_count += 1
                    print(f"Saved recipe HTML: {filename}")
                    if recipe_count >= MAX_RECIPE_PAGES:
                        break

            # Crawl internal links
            for link in extract_links(url, html):
                if not is_allowed(link):
                    continue

                if looks_like_recipe(link):
                    recipe_urls.add(link)
                    if link not in [item["url"] for item in recipe_manifest]:
                        try:
                            recipe_page = fetch_with_retry(link)
                            if recipe_page is not None:
                                filename = save_recipe_html(link, recipe_page.text, recipe_manifest, seen_slugs)
                                recipe_count += 1
                                print(f"Saved discovered recipe HTML: {filename}")
                                if recipe_count >= MAX_RECIPE_PAGES:
                                    break
                        except Exception as e:
                            log_error(f"Failed to save discovered recipe {link}", e)

                if link not in visited:
                    queue.append(link)

            if recipe_count >= MAX_RECIPE_PAGES:
                break

            time.sleep(CRAWL_DELAY_SECONDS)

        except Exception as e:
            log_error(f"Request failed for {url}", e)

    # Save raw unique URLs
    with open("found_recipes.txt", "w", encoding="utf-8") as f:
        for recipe in sorted(recipe_urls):
            f.write(recipe + "\n")

    # Save JSON manifest
    with open("recipe_manifest.json", "w", encoding="utf-8") as f:
        json.dump(recipe_manifest, f, indent=2, ensure_ascii=False)

    print(f"\nFinished.")
    print(f"Unique recipe URLs discovered: {len(recipe_urls)}")
    print(f"Recipe HTML files saved: {recipe_count}")
    print("Saved to: found_recipes.txt")
    print("Saved to: recipe_manifest.json")

if __name__ == "__main__":
    try:
        crawl_and_save(START_URLS)
    except Exception as e:
        log_error("Fatal scraper error", e)
        print(f"Fatal scraper error: {e}")
