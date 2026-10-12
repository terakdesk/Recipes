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
CRAWL_DELAY_SECONDS = 0.2
MAX_PAGES = 5000  # safety cap, not category cap

# Example recipe URL pattern:
# /624-lamp-thai-green-curry
RECIPE_PATTERN = re.compile(r"/\d+-[a-zA-Z0-9\-]+/?$")

# Treat category pages as valid crawl targets
# We do NOT exclude them here.
SKIP_SUBSTRINGS = ("login", "layout=", "task=", "search", "limit=")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/")

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
        if abs_url:
            yield abs_url

def crawl_site(start_url):
    q = deque([normalize_url(start_url)])
    visited = set()
    recipes = set()
    category_pages = set()

    while q and len(visited) < MAX_PAGES:
        url = q.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url):
            continue

        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                continue
            content_type = r.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                continue
        except requests.RequestException:
            continue

        page_url = normalize_url(url)
        if looks_like_recipe(page_url):
            recipes.add(page_url)
        else:
            # If this is not a recipe page, keep it as a category/index page candidate
            # because it may lead to more recipes
            category_pages.add(page_url)

        try:
            for link in extract_links(page_url, r.text):
                if not is_allowed(link):
                    continue

                if looks_like_recipe(link):
                    recipes.add(link)
                else:
                    # include category/index pages in the queue
                    if link not in visited:
                        q.append(link)
        except Exception:
            pass

        time.sleep(CRAWL_DELAY_SECONDS)

    return recipes, category_pages, visited

if __name__ == "__main__":
    recipes, category_pages, visited = crawl_site(START_URL)

    with open("found_recipes.txt", "w", encoding="utf-8") as f:
        for recipe in sorted(recipes):
            f.write(recipe + "\n")

    print(f"Visited pages: {len(visited)}")
    print(f"Category pages found: {len(category_pages)}")
    print(f"Recipes found: {len(recipes)}")
    print("Saved to found_recipes.txt")
