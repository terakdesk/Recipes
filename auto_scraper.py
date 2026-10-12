
import requests
from bs4 import BeautifulSoup
import random
from urllib.parse import urljoin
import datetime
import re

base_url = 'http://www.42wide.com/food3'

try:
    response = requests.get(base_url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. Collect all category links and recipe links from the main page
    links = soup.find_all('a', href=True)
    category_urls = set()
    recipe_urls = set()

    for link in links:
        href = link['href']
        full_url = urljoin(base_url, href)

        # Filter category pages to find more recipes
        if any(x in href.lower() for x in ['/recipes/', 'recipes', 'category']) and not any(x in href.lower() for x in ['layout=', 'login', 'search', 'task=', 'limit=']):
            if re.search(r'\d+-[a-zA-Z0-9\-]+', href):
                recipe_urls.add(full_url)
            else:
                category_urls.add(full_url)

    # 2. Visit a random category page to crawl deeper for individual recipes
    if category_urls:
        print(f"Gathering more recipes from categories...")
        for cat_url in list(category_urls)[:50]:  # Scan up to 50 categories to build a diverse pool
            try:
                cat_resp = requests.get(cat_url, timeout=5)
                if cat_resp.status_code == 200:
                    cat_soup = BeautifulSoup(cat_resp.text, 'html.parser')
                    for cat_link in cat_soup.find_all('a', href=True):
                        c_href = cat_link['href']
                        # If it has a pattern of a deep recipe article (e.g. 624-lamp-thai-green-curry)
                        if re.search(r'\d+-[a-zA-Z0-9\-]+', c_href) and not any(x in c_href.lower() for x in ['category', 'layout=', 'limit=']):
                            recipe_urls.add(urljoin(base_url, c_href))
            except Exception:
                continue

    recipe_list = list(recipe_urls)
    print(f"Total unique recipes found: {len(recipe_list)}")

    # Save the list of all found recipes to a text file
    with open('found_recipes.txt', 'w', encoding='utf-8') as rf:
        for recipe_url in sorted(recipe_list):
            rf.write(recipe_url + '\n')
    print("Saved all unique recipe URLs to 'found_recipes.txt'")

    if recipe_list:
        selected_recipe_url = random.choice(recipe_list)
        # If it matches index categories, try to pick another
        attempts = 0
        while ('recipes/' in selected_recipe_url and not re.search(r'\d+-[a-zA-Z0-9\-]+', selected_recipe_url)) and attempts < 10:
            selected_recipe_url = random.choice(recipe_list)
            attempts += 1

        print(f"Selected Recipe URL: {selected_recipe_url}")

        recipe_response = requests.get(selected_recipe_url, timeout=10)
        recipe_response.raise_for_status()

        # Create a unique filename with today's date
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        filename = f"recipe_{today_str}.html"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(recipe_response.text)

        print(f"Successfully saved {filename}!")
    else:
        print("No recipes found.")
except Exception as e:
    print(f"Error occurred: {e}")

