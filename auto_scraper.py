
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from collections import deque
import re
import time

START_URL = "http://www.42wide.com/food3/"
ALLOWED_HOST = "www.42wide.com"
ALLOWED_PATH_PREFIX = "/food3"
REQUEST_TIMEOUT = 10
CRAWL_DELAY_SECONDS = 0.2  # be polite to server

# Recipe URL pattern like: 624-lamp-thai-green-curry
RECIPE_PATTERN = re.compile(r"/\d+-[a-zA-Z0-9\-]+/?$")

# Skip links that are usually non-content/noisy
SKIP_SUBSTRINGS = ("login", "layout=", "task=")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; RecipeCrawler/1.0; +https://github.com/terakdesk/Recipes)"
})

def normalize_url(url: str) -> str:
    # remove #fragment
    url, _ = urldefrag(url)
    # strip trailing slash except root-like path handling can stay consistent
    if url.endswith("/") and len(url) > len("http://a/"):
        url = url.rstrip("/")
    return url

def is_allowed(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        if p.netloc != ALLOWED_HOST:
            return False
        if not p.path.startswith(ALLOWED_PATH_PREFIX):
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
        abs_url = normalize_url(urljoin(page_url, href))
        yield abs_url

def crawl_all_recipes(start_url: str):
    start_url = normalize_url(start_url)
    q = deque([start_url])
    visited = set()
    recipes = set()

    while q:
        url = q.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url):
            continue

        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
                continue

            # If current page itself is a recipe URL, keep it
            if looks_like_recipe(url):
                recipes.add(url)

            # Discover more links
            for link in extract_links(url, resp.text):
                if not is_allowed(link):
                    continue

                if looks_like_recipe(link):
                    recipes.add(link)
                # Still queue all allowed pages so we can find deep recipes and paginated indexes
                if link not in visited:
                    q.append(link)

            time.sleep(CRAWL_DELAY_SECONDS)

        except requests.RequestException:
            continue

    return recipes, visited

if __name__ == "__main__":
    recipes, visited_pages = crawl_all_recipes(START_URL)

    with open("found_recipes.txt", "w", encoding="utf-8") as f:
        for r in sorted(recipes):
            f.write(r + "\n")

    print(f"Crawled pages: {len(visited_pages)}")
    print(f"Total unique recipes found: {len(recipes)}")
    print("Saved to found_recipes.txt")
