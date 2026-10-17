# Recipes

A personal cookbook: store recipes locally, search them, and add or edit them in the browser.

Recipes live as JSON on disk and in a SQLite database. A small Flask app is the UI. Many of the current recipes were scraped from [42wide.com/food3](https://www.42wide.com/food3/index.php) and parsed into structured files.

## What you get

- Browse and search recipes by title or ingredients
- Open a recipe (ingredients, method, notes, details)
- Import by pasting text or HTML
- Edit an existing recipe

## How the pieces connect

```
auto_scraper.py          →  saved_recipes/*.html
filtered_tags.py         →  saved_recipes_json/*.json
merge_json_to_sqlite.py  →  recipes.db
create_fts.py            →  recipes_fts (full-text search)
app.py + templates/      →  http://127.0.0.1:5000
deploy/                  →  systemd + nginx (production)
```

| Path | Role |
|------|------|
| `app.py` | Flask routes and SQLite access |
| `templates/` | Jinja pages (search, recipe, import, edit) |
| `saved_recipes/` | Saved HTML source pages |
| `saved_recipes_json/` | Parsed recipes (`title`, `preamble`, `ingredients`, `method`, `notes`, `details`) |
| `recipes.db` | SQLite store used by the web app (built locally; not required in git) |
| `filtered_tags.py` | HTML → JSON parser (also used on import) |
| `merge_json_to_sqlite.py` | JSON files → `recipes` table |
| `create_fts.py` | Rebuilds `recipes_fts` for search |
| `auto_scraper.py` | Crawls the original site into `saved_recipes/` |
| `deploy/` | Gunicorn unix socket + nginx |

## Run locally

Python 3 and a virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` lists Flask. For HTML parsing and scraping, also install:

```bash
pip install beautifulsoup4 requests
```

Build the database from the JSON files, then start the app:

```bash
python merge_json_to_sqlite.py
python create_fts.py
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

Rebuild `recipes.db` and the FTS index whenever you add or change JSON files on disk. Edits made in the web UI write to SQLite only.

### Useful routes

| URL | What it does |
|-----|----------------|
| `/` | Search and list |
| `/recipe/<id>` | View one recipe |
| `/recipe/<id>/edit` | Edit |
| `/import` | Paste text/HTML, preview, then save |

## Rebuild data from HTML

If you have HTML in `saved_recipes/` and want fresh JSON:

```bash
python filtered_tags.py --src saved_recipes --out saved_recipes_json
python merge_json_to_sqlite.py
python create_fts.py
```

Re-running the scraper (`python auto_scraper.py`) crawls `42wide.com` again. Use that only when you intend to fetch live pages.

## Production

`deploy/` runs the Flask app with Gunicorn on a unix socket under `/run/recipes`, with nginx in front. See [deploy/README.md](deploy/README.md). Paths in those files assume a server copy such as `~/recipes_remote`.

## Where to start as a newcomer

1. `app.py` — the whole web surface is this file.
2. `templates/index.html` — search UI.
3. Any file in `saved_recipes_json/` — the recipe JSON shape.
4. `merge_json_to_sqlite.py` — table schema and import.
