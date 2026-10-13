from flask import Flask, request, render_template, g, abort
import sqlite3
import os

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
    db = get_db()
    if not q:
        cur = db.execute('SELECT id,title,filename FROM recipes ORDER BY title LIMIT 50')
        rows = cur.fetchall()
    else:
        like = f'%{q.lower()}%'
        if field == 'title':
            cur = db.execute('SELECT id,title,filename FROM recipes WHERE lower(title) LIKE ? ORDER BY title LIMIT 500', (like,))
        elif field == 'ingredients':
            cur = db.execute('SELECT id,title,filename FROM recipes WHERE ingredients_text LIKE ? ORDER BY title LIMIT 500', (like,))
        else:
            cur = db.execute('SELECT id,title,filename FROM recipes WHERE lower(title) LIKE ? OR ingredients_text LIKE ? ORDER BY title LIMIT 500', (like, like))
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
