from flask import Flask, request, render_template, g, abort, send_from_directory, redirect, url_for, session
import sqlite3
import os
import re
import json
import time
import math
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

# reuse the parser utilities
import filtered_tags

DB_PATH = os.path.join(os.path.dirname(__file__), 'recipes.db')

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'change-this-secret-key')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def get_session_timeout_seconds() -> int:
    """Return idle session timeout in seconds."""
    raw = (os.environ.get('RECIPES_SESSION_TIMEOUT_MINUTES', '30') or '30').strip()
    try:
        minutes = int(raw)
    except Exception:
        minutes = 30
    if minutes < 1:
        minutes = 1
    return minutes * 60


app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=get_session_timeout_seconds())


def get_auth_config():
    """Read auth settings from environment variables."""
    return {
        'username': os.environ.get('RECIPES_AUTH_USER', 'admin'),
        'password_hash': os.environ.get('RECIPES_AUTH_PASSWORD_HASH', '').strip(),
        'password_plain': os.environ.get('RECIPES_AUTH_PASSWORD', 'change-me').strip(),
    }


def ensure_users_table_and_bootstrap(db):
    """Create users table if needed and bootstrap initial admin from env."""
    db.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created TEXT,
            modified TEXT
        )
        '''
    )

    count_row = db.execute('SELECT COUNT(*) AS c FROM users').fetchone()
    if int(count_row['c'] or 0) > 0:
        return

    conf = get_auth_config()
    username = (conf.get('username') or 'admin').strip() or 'admin'
    password_hash = (conf.get('password_hash') or '').strip()
    if not password_hash:
        password_hash = generate_password_hash(conf.get('password_plain') or 'change-me')

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute(
        '''
        INSERT INTO users (username, password_hash, is_admin, is_active, created, modified)
        VALUES (?, ?, 1, 1, ?, ?)
        ''',
        (username, password_hash, now_str, now_str),
    )
    db.commit()


def ensure_recipes_valid_column(db):
    """Ensure recipes table has an is_valid soft-delete flag."""
    cols = db.execute('PRAGMA table_info(recipes)').fetchall()
    names = {str(c['name']).lower() for c in cols}
    if 'is_valid' not in names:
        db.execute('ALTER TABLE recipes ADD COLUMN is_valid INTEGER NOT NULL DEFAULT 1')
        db.commit()


def get_current_user():
    user_id = session.get('auth_user_id')
    if not user_id:
        return None

    db = get_db()
    row = db.execute(
        'SELECT id, username, is_admin, is_active FROM users WHERE id=?',
        (user_id,),
    ).fetchone()
    if not row or int(row['is_active'] or 0) != 1:
        return None
    return row


def is_authenticated():
    return get_current_user() is not None


def is_admin_user() -> bool:
    u = get_current_user()
    return bool(u and int(u['is_admin'] or 0) == 1)


def verify_credentials(username: str, password: str) -> bool:
    if not username or not password:
        return False

    db = get_db()
    row = db.execute(
        'SELECT id, username, password_hash, is_admin, is_active FROM users WHERE lower(username)=lower(?)',
        (username,),
    ).fetchone()
    if not row or int(row['is_active'] or 0) != 1:
        return False

    try:
        return bool(check_password_hash(row['password_hash'], password))
    except Exception:
        return False


def fetch_user_for_login(username: str):
    if not username:
        return None
    db = get_db()
    row = db.execute(
        'SELECT id, username, is_admin, is_active FROM users WHERE lower(username)=lower(?)',
        (username,),
    ).fetchone()
    if not row or int(row['is_active'] or 0) != 1:
        return None
    return row


def is_safe_next(target: str) -> bool:
    return bool(target) and target.startswith('/') and not target.startswith('//')


@app.before_request
def enforce_session_timeout():
    """Expire authenticated sessions after inactivity timeout."""
    if 'auth_user_id' not in session:
        return

    now = int(time.time())
    timeout = get_session_timeout_seconds()
    last_seen = session.get('last_seen_at')

    try:
        last_seen_int = int(last_seen)
    except Exception:
        last_seen_int = now

    if now - last_seen_int > timeout:
        session.pop('auth_user_id', None)
        session.pop('auth_user', None)
        session.pop('auth_is_admin', None)
        session.pop('last_seen_at', None)
        return

    if get_current_user() is None:
        session.pop('auth_user_id', None)
        session.pop('auth_user', None)
        session.pop('auth_is_admin', None)
        session.pop('last_seen_at', None)
        return

    session['last_seen_at'] = now
    session.modified = True


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if is_authenticated():
            return view_func(*args, **kwargs)

        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for('login', next=next_url))

    return wrapped


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            next_url = request.full_path if request.query_string else request.path
            return redirect(url_for('login', next=next_url))
        if not is_admin_user():
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_auth_state():
    u = get_current_user()
    return {
        'is_authenticated': bool(u),
        'auth_user': u['username'] if u else None,
        'auth_is_admin': bool(u and int(u['is_admin'] or 0) == 1),
    }


def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        db = g._db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        ensure_users_table_and_bootstrap(db)
        ensure_recipes_valid_column(db)
    return db


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_db', None)
    if db is not None:
        db.close()


@app.route('/logo_header_chez_michel.png')
def logo_header():
    return send_from_directory(
        os.path.join(app.root_path, 'static', 'images'),
        'logo_header_chez_michel.png'
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    next_url = request.values.get('next', '').strip()
    if not is_safe_next(next_url):
        next_url = '/'

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if verify_credentials(username, password):
            user = fetch_user_for_login(username)
            if not user:
                error = 'Invalid username or password'
                return render_template('login.html', error=error, next_url=next_url)
            session['auth_user_id'] = int(user['id'])
            session['auth_user'] = username
            session['auth_is_admin'] = int(user['is_admin'] or 0)
            session['last_seen_at'] = int(time.time())
            session.permanent = True
            return redirect(next_url or '/')
        error = 'Invalid username or password'

    return render_template('login.html', error=error, next_url=next_url)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('auth_user_id', None)
    session.pop('auth_user', None)
    session.pop('auth_is_admin', None)
    session.pop('last_seen_at', None)
    return redirect('/')


@app.route('/users', methods=['GET'])
@admin_required
def manage_users():
    db = get_db()
    users = db.execute(
        'SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)'
    ).fetchall()
    return render_template('users.html', users=users)


@app.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    db = get_db()
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    confirm = request.form.get('confirm_password') or ''
    is_admin = 1 if request.form.get('is_admin') == 'on' else 0

    if not re.match(r'^[A-Za-z0-9_.\-]{3,50}$', username):
        users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
        return render_template('users.html', users=users, error='Username must be 3-50 chars and use letters, numbers, ., _, or -.')

    if len(password) < 8:
        users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
        return render_template('users.html', users=users, error='Password must be at least 8 characters.')

    if password != confirm:
        users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
        return render_template('users.html', users=users, error='Password confirmation does not match.')

    existing = db.execute('SELECT id FROM users WHERE lower(username)=lower(?)', (username,)).fetchone()
    if existing:
        users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
        return render_template('users.html', users=users, error='Username already exists.')

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute(
        '''
        INSERT INTO users (username, password_hash, is_admin, is_active, created, modified)
        VALUES (?, ?, ?, 1, ?, ?)
        ''',
        (username, generate_password_hash(password), is_admin, now_str, now_str),
    )
    db.commit()

    users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
    return render_template('users.html', users=users, success=f'User "{username}" created.')


@app.route('/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    db = get_db()
    target = db.execute('SELECT id, username, is_admin FROM users WHERE id=?', (uid,)).fetchone()
    users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
    if not target:
        return render_template('users.html', users=users, error='User not found.')

    current = get_current_user()
    if current and int(current['id']) == int(target['id']):
        return render_template('users.html', users=users, error='You cannot delete your own account while logged in.')

    total_row = db.execute('SELECT COUNT(*) AS c FROM users').fetchone()
    if int(total_row['c'] or 0) <= 1:
        return render_template('users.html', users=users, error='Cannot delete the last user account.')

    if int(target['is_admin'] or 0) == 1:
        admin_row = db.execute('SELECT COUNT(*) AS c FROM users WHERE is_admin=1').fetchone()
        if int(admin_row['c'] or 0) <= 1:
            return render_template('users.html', users=users, error='Cannot delete the last admin account.')

    db.execute('DELETE FROM users WHERE id=?', (uid,))
    db.commit()
    users = db.execute('SELECT id, username, is_admin, is_active, created, modified FROM users ORDER BY lower(username)').fetchall()
    return render_template('users.html', users=users, success=f'User "{target["username"]}" deleted.')


def format_display_lines(lines, strip_method_numbers=False):
    """Format display lines without modifying persisted database content."""
    if not lines:
        return []

    formatted = []
    indent_following = False

    for raw in lines:
        text = str(raw or '').strip()
        if not text:
            continue

        dash_match = re.match(r'^\s*-\s*(.+)$', text)
        if dash_match:
            heading = dash_match.group(1).strip()
            if heading:
                formatted.append({'kind': 'heading', 'text': heading, 'indented': False})
                indent_following = True
            continue

        if strip_method_numbers:
            # Strip a leading number token when followed by non-letters
            # (e.g. "1.", "2/", "3)" or "4 -") for display only.
            text = re.sub(r'^\s*\d+(?:[^A-Za-z]+|$)\s*', '', text)
            # Strip single-letter counters like "a)", "A/", "c." etc.
            # but keep normal words such as "Add onions" unchanged.
            text = re.sub(r'^\s*[A-Za-z][\)\]\.,/:;\-"\']+\s*', '', text)
            text = text.strip()
            if not text:
                continue

        formatted.append({'kind': 'item', 'text': text, 'indented': indent_following})

    return formatted


@app.route('/')
def index():
    q = request.args.get('q', '').strip()
    field = request.args.get('field', 'any')
    sort = (request.args.get('sort', 'title') or 'title').strip().lower()
    if sort not in ('title', 'filename', 'created', 'modified'):
        sort = 'title'
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
    # Fetch valid rows and apply word-based filtering in Python so search
    # matches all terms regardless of order.
    cur = db.execute('SELECT id,title,filename,created,modified,ingredients_text FROM recipes WHERE COALESCE(is_valid,1)=1')
    all_rows = cur.fetchall()

    terms = re.findall(r"[A-Za-z0-9']+", q.lower())

    def has_all_terms(text_value):
        text = (text_value or '').lower()
        return all(term in text for term in terms)

    filtered_rows = []
    if not terms:
        filtered_rows = all_rows
    else:
        for r in all_rows:
            title_text = r['title'] or ''
            ingredients_text = r['ingredients_text'] or ''

            if field == 'title':
                ok = has_all_terms(title_text)
            elif field == 'ingredients':
                ok = has_all_terms(ingredients_text)
            else:
                ok = all(
                    (term in (title_text or '').lower()) or (term in (ingredients_text or '').lower())
                    for term in terms
                )

            if ok:
                filtered_rows.append(r)

    # Convert sqlite rows to dicts and normalize title case for display
    rows_list = []

    def date_only(value):
        text = (value or '').strip()
        if not text:
            return ''
        return text.split(' ', 1)[0]

    for r in filtered_rows:
        d = dict(r)
        t = d.get('title') or ''
        d['title'] = t.title()
        d['created'] = date_only(d.get('created'))
        d['modified'] = date_only(d.get('modified'))
        d.pop('ingredients_text', None)
        rows_list.append(d)

    # sort in Python so behavior is consistent for all sort options.
    def parse_dt(value):
        if not value:
            return datetime.min
        text = str(value).strip()
        if not text:
            return datetime.min
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return datetime.min

    if sort == 'filename':
        rows_list.sort(key=lambda x: (x.get('filename') or '').lower())
    elif sort == 'created':
        rows_list.sort(key=lambda x: parse_dt(x.get('created')), reverse=True)
    elif sort == 'modified':
        rows_list.sort(key=lambda x: parse_dt(x.get('modified')), reverse=True)
    else:
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

    return render_template('index.html', rows=rows, q=q, field=field, sort=sort, page=page, per_page=per_page, total_count=total_count, total_pages=total_pages)


@app.route('/recipe/<int:rid>')
def recipe(rid):
    db = get_db()
    cur = db.execute('SELECT * FROM recipes WHERE id=?', (rid,))
    row = cur.fetchone()
    if not row:
        abort(404)
    recipe_is_valid = int(row['is_valid'] or 1) == 1
    if not recipe_is_valid and not is_authenticated():
        abort(404)
    # parse JSON fields for display
    import json
    ingredients = json.loads(row['ingredients_json'] or '[]')
    method = json.loads(row['method_json'] or '[]')
    notes = json.loads(row['notes_json'] or '[]')
    details = json.loads(row['details_json'] or '[]')
    raw = json.loads(row['raw_json'] or '{}')
    ingredients_display = format_display_lines(ingredients, strip_method_numbers=False)
    method_display = format_display_lines(method, strip_method_numbers=True)

    def date_only(value):
        text = (value or '').strip()
        if not text:
            return ''
        return text.split(' ', 1)[0]

    created_date = date_only(row['created'])
    modified_date = date_only(row['modified'])

    return render_template(
        'recipe.html',
        r=row,
        ingredients=ingredients_display,
        method=method_display,
        notes=notes,
        details=details,
        raw=raw,
        created_date=created_date,
        modified_date=modified_date,
        recipe_is_valid=recipe_is_valid,
    )


@app.route('/recipes/invalid')
@login_required
def invalid_recipes():
    db = get_db()
    rows = db.execute(
        'SELECT id, title, filename, created, modified FROM recipes WHERE COALESCE(is_valid,1)=0 ORDER BY lower(title)'
    ).fetchall()
    msg = (request.args.get('msg') or '').strip()
    return render_template('invalid_recipes.html', rows=rows, msg=msg)


@app.route('/recipe/<int:rid>/invalidate', methods=['POST'])
@login_required
def invalidate_recipe(rid):
    db = get_db()
    row = db.execute('SELECT id, title FROM recipes WHERE id=?', (rid,)).fetchone()
    if not row:
        abort(404)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute('UPDATE recipes SET is_valid=0, modified=? WHERE id=?', (now_str, rid))
    db.commit()
    return redirect(url_for('invalid_recipes', msg=f'Invalidated: {row["title"] or "recipe"}'))


@app.route('/recipe/<int:rid>/restore', methods=['POST'])
@login_required
def restore_recipe(rid):
    db = get_db()
    row = db.execute('SELECT id, title FROM recipes WHERE id=?', (rid,)).fetchone()
    if not row:
        abort(404)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.execute('UPDATE recipes SET is_valid=1, modified=? WHERE id=?', (now_str, rid))
    db.commit()
    return redirect(url_for('recipe', rid=rid))


@app.route('/import', methods=['GET', 'POST'])
@login_required
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
            'ingredients': ['ingredient', 'ingredients', 'key ingredients', 'item', 'items'],
            'method': ['method', 'methods', 'instruction', 'instructions', 'quick cooking steps', 'steps', 'procedure'],
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
@login_required
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
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cur = db.cursor()
    cur.execute('''
            INSERT INTO recipes (filename,title,preamble,ingredients_json,ingredients_text,method_json,notes_json,details_json,raw_json,created,modified)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        fname,
        title,
        preamble,
        json.dumps(ingredients, ensure_ascii=False),
        ingredients_text,
        json.dumps(method, ensure_ascii=False),
        json.dumps(notes, ensure_ascii=False),
        json.dumps(details, ensure_ascii=False),
        json.dumps(raw_post, ensure_ascii=False) if raw_post is not None else None,
        now_str,
        now_str,
    ))
    db.commit()
    rid = cur.lastrowid
    return render_template('import_saved.html', id=rid, title=title)


@app.route('/recipe/<int:rid>/edit', methods=['GET', 'POST'])
@login_required
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
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    db.execute('''
          UPDATE recipes
          SET title=?,
          preamble=?,
          ingredients_json=?,
          ingredients_text=?,
          method_json=?,
          notes_json=?,
          details_json=?,
          created=COALESCE(created, ?),
          modified=?
          WHERE id=?
    ''', (
        title,
        preamble,
        json.dumps(ingredients, ensure_ascii=False),
        ingredients_text,
        json.dumps(method, ensure_ascii=False),
        json.dumps(notes, ensure_ascii=False),
        json.dumps(details, ensure_ascii=False),
        now_str,
        now_str,
        rid
    ))
    db.commit()
    return render_template('import_saved.html', id=rid, title=title)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
