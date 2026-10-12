import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
import re
import time

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

RECIPE_PATTERN = re.compile(r"/\d+-[a-zA-Z0-9\-]+/?$")

SKIP_SUBSTRINGS = ("login", "layout=", "task=", "search", "limit=", "javascript:", "mailto:")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
})

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
    except Exception:
        return False

def looks_like_recipe(url: str) -> bool:
    p = urlparse(url)
    return bool(RECIPE_PATTERN.search(p.path))

def extract_links(page_url: str, html: str):
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        full = normalize_url(urljoin(page_url, href))
        yield full

def crawl(start_urls):
    queue = deque()
    for s in start_urls:
        queue.append(normalize_url(s))

    visited = set()
    recipes = set()
    crawled = 0

    while queue and len(visited) < MAX_PAGES:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url):
            continue

        try:
            print(f"Fetching: {url}")
            r = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            print(f"Status for {url}: {r.status_code}")

            if r.status_code != 200:
                continue

            content_type = r.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                print(f"Skipping non-HTML page: {url}")
                continue

            if looks_like_recipe(url):
                recipes.add(url)

            for link in extract_links(url, r.text):
                if not is_allowed(link):
                    continue
                if looks_like_recipe(link):
                    recipes.add(link)
                if link not in visited:
                    queue.append(link)

            crawled += 1
            time.sleep(CRAWL_DELAY_SECONDS)

        except Exception as e:
            print(f"ERROR on {url}: {e}")

    return recipes, visited, crawled

if __name__ == "__main__":
    recipes, visited, crawled = crawl(START_URLS)

    with open("found_recipes.txt", "w", encoding="utf-8") as f:
        for recipe in sorted(recipes):
            f.write(recipe + "\n")

    print(f"Visited pages: {len(visited)}")
    print(f"Crawled pages: {crawled}")
    print(f"Recipes found: {len(recipes)}")
    print("Saved to found_recipes.txt")
