from flask import Flask, request, render_template, g, abort
import sqlite3
import os
import re
import json
import time
import math

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
    # Fetch matching rows, normalize titles to Title Case for display,
    # sort case-insensitively, then apply pagination in Python so order
    # is consistent across pages.
    if not q:
        cur = db.execute('SELECT id,title,filename FROM recipes')
        all_rows = cur.fetchall()
    else:
        like = f'%{q.lower()}%'
        if field == 'title':
            cur = db.execute('SELECT id,title,filename FROM recipes WHERE lower(title) LIKE ?', (like,))
            all_rows = cur.fetchall()
        elif field == 'ingredients':
            cur = db.execute('SELECT id,title,filename FROM recipes WHERE ingredients_text LIKE ?', (like,))
            all_rows = cur.fetchall()
        else:
            cur = db.execute('SELECT id,title,filename FROM recipes WHERE lower(title) LIKE ? OR ingredients_text LIKE ?', (like, like))
            all_rows = cur.fetchall()

    # Convert sqlite rows to dicts and normalize title case for display
    rows_list = []
    for r in all_rows:
        d = dict(r)
        t = d.get('title') or ''
        d['title'] = t.title()
        rows_list.append(d)

    # sort case-insensitively by the normalized title
    rows_list.sort(key=lambda x: (x.get('title') or '').lower())

    total_count = len(rows_list)
    # apply pagination slice
    rows = rows_list[offset: offset + per_page]
    # compute pagination totals
    try:
        total_count = int(total_count)
    except Exception:
        total_count = 0
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template('index.html', rows=rows, q=q, field=field, page=page, per_page=per_page, total_count=total_count, total_pages=total_pages)


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

    # Multi-pass analysis: try BS4, fallback parser, then lightweight heuristics
    def analyze_text_multi_pass(raw_text: str) -> dict:
        # 1) try BS4 parsing when available
        parsed_primary = None
        try:
            if filtered_tags.BeautifulSoup and ('<' in raw_text and '>' in raw_text):
                parsed_primary = filtered_tags.parse_with_bs4(raw_text)
            else:
                parsed_primary = filtered_tags.parse_with_fallback(raw_text)
        except Exception:
            parsed_primary = filtered_tags.parse_with_fallback(raw_text)

        # 2) always run fallback parser to get additional candidates
        try:
            parsed_fallback = filtered_tags.parse_with_fallback(raw_text)
        except Exception:
            parsed_fallback = {'title': None, 'preamble': None, 'ingredients': None, 'method': None, 'notes': None, 'details': None}

        # 3) manual, heading-driven section parser
        # Prefer using BeautifulSoup to find heading elements and collect their following
        # content (robust across blank lines and mixed HTML). If BS4 isn't available,
        # fall back to a tolerant line-oriented parser.
        keyword_map = {
            'ingredients': ['ingredient', 'ingredients', 'item', 'items'],
            'method': ['method', 'methods', 'instruction', 'instructions', 'procedure'],
            'notes': ['note', 'notes', 'serving', 'tips'],
            'details': ['detail', 'details'],
        }

        # reverse lookup from word -> canonical
        rev = {}
        for canon, words in keyword_map.items():
            for w in words:
                rev[w] = canon

        sections = {'preamble': [], 'ingredients': [], 'method': [], 'notes': [], 'details': []}

        # If BeautifulSoup is available, use it to find headings and gather siblings
        if filtered_tags.BeautifulSoup and ('<' in raw_text and '>' in raw_text):
            try:
                soup = filtered_tags.BeautifulSoup(raw_text, 'html.parser')
                headers = soup.find_all(re.compile('^h[1-6]$'))
                # track whether we've seen any heading; text before first matched heading -> preamble
                seen_any = False
                for h in headers:
                    htxt = ' '.join(h.stripped_strings).lower()
                    matched = None
                    for w, canon in rev.items():
                        # only match if the keyword appears at the start of the heading
                        # (allowing optional leading whitespace) and either is a whole
                        # word or followed by ':'
                        if re.match(rf'^\s*{re.escape(w)}(\b|:)', htxt):
                            matched = canon
                            break
                    if not matched:
                        continue

                    seen_any = True
                    # collect following siblings until next header
                    collected = []
                    for sib in h.next_siblings:
                        if getattr(sib, 'name', None) and re.match('^h[1-6]$', getattr(sib, 'name')):
                            break
                        # get visible text from sibling
                        try:
                            text = ''
                            if getattr(sib, 'get_text', None):
                                text = sib.get_text('\n', strip=True)
                            else:
                                text = str(sib).strip()
                        except Exception:
                            text = str(sib).strip()
                        if not text:
                            continue
                        # split on newlines within the sibling to get multiple items
                        for part in text.splitlines():
                            part = part.strip()
                            if not part:
                                continue
                            if part.lstrip().startswith('-'):
                                sections[matched].append(f"<h4>{part}</h4>")
                            else:
                                sections[matched].append(part)

                # if there was text before the first header, capture as preamble
                if headers:
                    first_header = headers[0]
                    pre_text_parts = []
                    for node in soup.body.descendants:
                        # collect text until we reach the first header element
                        if node is first_header:
                            break
                        if getattr(node, 'string', None):
                            s = str(node.string).strip()
                            if s:
                                pre_text_parts.append(s)
                    if pre_text_parts:
                        sections['preamble'] = ['\n\n'.join(pre_text_parts)]
            except Exception:
                # fall back to line-based parser below
                pass

        # If BS4 not used or produced no sections, fall back to tolerant line parser
        if not any(sections[k] for k in sections):
            norm = raw_text
            for tag in [r'<br\s*/?>', r'</p>', r'</div>', r'</li>', r'</h1>', r'</h2>', r'</h3>', r'</h4>', r'</h5>', r'</h6>', r'</ul>', r'</ol>', r'<hr\s*/?>']:
                norm = re.sub(tag, '\n', norm, flags=re.I)
            lines = norm.splitlines()
            current = 'preamble'

            def detect_keyword(line: str) -> str:
                low = line.lower()
                for w, canon in rev.items():
                    # only consider a keyword if it occurs at the start of the line
                    if re.match(rf'^\s*{re.escape(w)}(\b|:)', low):
                        return canon
                return ''

            for ln in lines:
                raw_ln = ln.rstrip('\r')
                # treat blank lines as separators but do not change current section
                if raw_ln.strip() == '':
                    continue
                k = detect_keyword(raw_ln)
                if k:
                    current = k
                    continue
                if raw_ln.lstrip().startswith('-'):
                    entry = f"<h4>{raw_ln}</h4>"
                else:
                    entry = raw_ln.strip()
                sections[current].append(entry)

        # convert empty lists to None to match parser outputs
        manual_ingredients = sections['ingredients'] or None
        manual_method = sections['method'] or None
        manual_notes = sections['notes'] or None
        manual_details = sections['details'] or None
        manual_preamble = '\n\n'.join(sections['preamble']) or None

        # Merge parsed results: prefer primary parse, but append any manual
        # items (from the Analyze step) that the parser missed. For scalar
        # fields prefer primary -> fallback -> manual.
        def merge_list(primary, fallback, manual):
            if primary:
                # append manual items not already present (preserve order)
                out = list(primary)
                if manual:
                    existing = {str(x).strip().lower() for x in out}
                    for m in manual:
                        if str(m).strip().lower() not in existing:
                            out.append(m)
                return out
            if fallback:
                return list(fallback)
            if manual:
                return list(manual)
            return None

        def pick_scalar(primary, fallback, manual):
            return primary or fallback or manual or None

        merged = {
            'title': parsed_primary.get('title') or parsed_fallback.get('title'),
            'preamble': pick_scalar(parsed_primary.get('preamble'), parsed_fallback.get('preamble'), manual_preamble),
            'ingredients': merge_list(parsed_primary.get('ingredients'), parsed_fallback.get('ingredients'), manual_ingredients),
            'method': merge_list(parsed_primary.get('method'), parsed_fallback.get('method'), manual_method),
            'notes': merge_list(parsed_primary.get('notes'), parsed_fallback.get('notes'), manual_notes),
            'details': merge_list(parsed_primary.get('details'), parsed_fallback.get('details'), manual_details),
        }
        return merged

    parsed = analyze_text_multi_pass(text)

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

    # preserve raw posted text (if present) so recipe page can show original
    raw_post = request.form.get('raw') or None

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
                json.dumps(raw_post, ensure_ascii=False) if raw_post is not None else None
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
