from flask import Flask, request, render_template, g, abort
import sqlite3
import os
import json
import time

# reuse the parser utilities
import filtered_tags

DB_PATH = os.path.join(os.path.dirname(__file__), 'recipes.db')

app = Flask(__name__)


def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_db', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    field = request.args.get('field', 'any')
    # pagination
    try:
        page = int(request.args.get('page', '1') or 1)
    except Exception:
        page = 1
    if page < 1:
        page = 1
    per_page = 50
    offset = (page - 1) * per_page

    db = get_db()
    if not q:
        cur = db.execute('SELECT id,title,filename FROM recipes ORDER BY title LIMIT ? OFFSET ?', (per_page, offset))
        rows = cur.fetchall()
    else:
        # Use FTS if available for faster, smarter full-text search
        q_sanitized = q.replace('"', ' ').strip()
        try:
            if field == 'title':
                fts_q = f'title:"{q_sanitized}"'
            elif field == 'ingredients':
                fts_q = f'ingredients:"{q_sanitized}"'
            else:
                fts_q = q_sanitized

            # Try FTS5 match first (paginated)
            cur = db.execute(
                'SELECT recipes.id,recipes.title,recipes.filename FROM recipes JOIN recipes_fts ON recipes.id = recipes_fts.rowid WHERE recipes_fts MATCH ? ORDER BY recipes.title LIMIT ? OFFSET ?',
                (fts_q, per_page, offset)
            )
            rows = cur.fetchall()
        except Exception:
            # Fallback to LIKE queries if FTS isn't available (paginated)
            like = f'%{q.lower()}%'
            if field == 'title':
                cur = db.execute('SELECT id,title,filename FROM recipes WHERE lower(title) LIKE ? ORDER BY title LIMIT ? OFFSET ?', (like, per_page, offset))
            elif field == 'ingredients':
                cur = db.execute('SELECT id,title,filename FROM recipes WHERE ingredients_text LIKE ? ORDER BY title LIMIT ? OFFSET ?', (like, per_page, offset))
            else:
                cur = db.execute('SELECT id,title,filename FROM recipes WHERE lower(title) LIKE ? OR ingredients_text LIKE ? ORDER BY title LIMIT ? OFFSET ?', (like, like, per_page, offset))
            rows = cur.fetchall()
    return render_template('index.html', rows=rows, q=q, field=field)


@app.route('/recipe/<int:rid>')
def recipe(rid):
    db = get_db()
    cur = db.execute('SELECT * FROM recipes WHERE id=?', (rid,))
    row = cur.fetchone()
    if not row:
        abort(404)
    # parse JSON fields for display
    import json
    ingredients = json.loads(row['ingredients_json'] or '[]')
    method = json.loads(row['method_json'] or '[]')
    notes = json.loads(row['notes_json'] or '[]')
    details = json.loads(row['details_json'] or '[]')
    raw = json.loads(row['raw_json'] or '{}')
    return render_template('recipe.html', r=row, ingredients=ingredients, method=method, notes=notes, details=details, raw=raw)


@app.route('/import', methods=['GET', 'POST'])
def import_text():
    """Allow pasting a block of text/HTML, analyze into recipe fields, and save."""
    if request.method == 'GET':
        return render_template('import.html')

    # POST: analyze the provided text
    text = request.form.get('text', '').strip()
    title_override = request.form.get('title', '').strip() or None
    if not text:
        return render_template('import.html', error='Please paste some text to analyze')

    # Try BS4 parser if available and looks like HTML, otherwise fallback regex parser
    parsed = None
    try:
        if filtered_tags.BeautifulSoup and ('<' in text and '>' in text):
            parsed = filtered_tags.parse_with_bs4(text)
        else:
            parsed = filtered_tags.parse_with_fallback(text)
    except Exception:
        parsed = filtered_tags.parse_with_fallback(text)

    # Honor optional title override
    if title_override:
        parsed['title'] = title_override

    # Prepare JSON blobs for saving and show result for confirmation
    result = {
        'title': parsed.get('title'),
        'preamble': parsed.get('preamble'),
        'ingredients': parsed.get('ingredients') or [],
        'method': parsed.get('method') or [],
        'notes': parsed.get('notes') or [],
        'details': parsed.get('details') or [],
        'raw': text,
    }

    return render_template('import_result.html', r=result)


@app.route('/import/save', methods=['POST'])
def import_save():
    db = get_db()
    title = request.form.get('title') or 'Imported recipe'
    preamble = request.form.get('preamble') or None
    # parse lists: accept either JSON array or multiline textarea
    def parse_list_field(name):
        v = request.form.get(name) or ''
        v = v.strip()
        if not v:
            return []
        if v.startswith('['):
            try:
                return json.loads(v)
            except Exception:
                pass
        # split lines
        return [line.strip() for line in v.splitlines() if line.strip()]

    ingredients = parse_list_field('ingredients')
    method = parse_list_field('method')
    notes = parse_list_field('notes')
    details = parse_list_field('details')

    # build a filename safe-ish identifier
    base = title or 'imported'
    safe = ''.join(c for c in base if c.isalnum() or c in (' ', '-', '_')).rstrip()

    fname = f"imported-{int(time.time())}-{safe.replace(' ', '-')[:80]}.json"

    ingredients_text = ' '.join([str(x).strip().lower() for x in ingredients if x])

    cur = db.cursor()
    cur.execute('''
      INSERT INTO recipes (filename,title,preamble,ingredients_json,ingredients_text,method_json,notes_json,details_json,raw_json)
      VALUES (?,?,?,?,?,?,?,?,?)
    ''', (
        fname,
        title,
        preamble,
        json.dumps(ingredients, ensure_ascii=False),
        ingredients_text,
        json.dumps(method, ensure_ascii=False),
        json.dumps(notes, ensure_ascii=False),
        json.dumps(details, ensure_ascii=False),
        None
    ))
    db.commit()
    rid = cur.lastrowid
    return render_template('import_saved.html', id=rid, title=title)


@app.route('/recipe/<int:rid>/edit', methods=['GET', 'POST'])
def edit_recipe(rid):
    db = get_db()
    if request.method == 'GET':
        cur = db.execute('SELECT * FROM recipes WHERE id=?', (rid,))
        row = cur.fetchone()
        if not row:
            abort(404)
        ingredients = json.loads(row['ingredients_json'] or '[]')
        method = json.loads(row['method_json'] or '[]')
        notes = json.loads(row['notes_json'] or '[]')
        details = json.loads(row['details_json'] or '[]')
        return render_template('edit.html', r=row, ingredients=ingredients, method=method, notes=notes, details=details)

    # POST: save updates
    title = request.form.get('title') or None
    preamble = request.form.get('preamble') or None

    def lines_to_list(name):
        v = request.form.get(name) or ''
        return [line.strip() for line in v.splitlines() if line.strip()]

    ingredients = lines_to_list('ingredients')
    method = lines_to_list('method')
    notes = lines_to_list('notes')
    details = lines_to_list('details')

    ingredients_text = ' '.join([str(x).strip().lower() for x in ingredients if x])

    db.execute('''
      UPDATE recipes SET title=?, preamble=?, ingredients_json=?, ingredients_text=?, method_json=?, notes_json=?, details_json=? WHERE id=?
    ''', (
        title,
        preamble,
        json.dumps(ingredients, ensure_ascii=False),
        ingredients_text,
        json.dumps(method, ensure_ascii=False),
        json.dumps(notes, ensure_ascii=False),
        json.dumps(details, ensure_ascii=False),
        rid
    ))
    db.commit()
    return render_template('import_saved.html', id=rid, title=title)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
