#!/usr/bin/env python3
import sqlite3
import json
import glob
import os

DB = 'recipes.db'
SRC_GLOB = 'saved_recipes_json/*.json'


def add_column_if_missing(conn, column_name, column_type='DATETIME'):
    existing = conn.execute('PRAGMA table_info(recipes)').fetchall()
    if any(row[1] == column_name for row in existing):
        return
    conn.execute(f'ALTER TABLE recipes ADD COLUMN {column_name} {column_type}')


def ensure_schema(conn):
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS recipes (
      id INTEGER PRIMARY KEY,
      filename TEXT UNIQUE,
      title TEXT,
      preamble TEXT,
      ingredients_json TEXT,
      ingredients_text TEXT,
      method_json TEXT,
      notes_json TEXT,
      details_json TEXT,
      raw_json TEXT
    )
    ''')
    add_column_if_missing(conn, 'created', 'DATETIME')
    add_column_if_missing(conn, 'modified', 'DATETIME')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_recipes_title ON recipes(title)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_recipes_ingredients ON recipes(ingredients_text)')
    conn.commit()


def import_all():
    files = glob.glob(SRC_GLOB)
    conn = sqlite3.connect(DB)
    ensure_schema(conn)
    cur = conn.cursor()
    count = 0
    for path in files:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print('Failed to load', path, e)
            continue

        ingredients = data.get('ingredients') or []
        if isinstance(ingredients, str):
            # sometimes a single string
            ingredients = [ingredients]
        ingredients_text = ' '.join([str(x).strip().lower() for x in ingredients if x])

        cur.execute('''
          INSERT OR REPLACE INTO recipes
          (filename,title,preamble,ingredients_json,ingredients_text,method_json,notes_json,details_json,raw_json,created,modified)
          VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            os.path.basename(path),
            data.get('title'),
            data.get('preamble'),
            json.dumps(data.get('ingredients') or []),
            ingredients_text,
            json.dumps(data.get('method') or []),
            json.dumps(data.get('notes') or []),
            json.dumps(data.get('details') or []),
            json.dumps(data),
            None,
            None,
        ))
        count += 1

    conn.commit()
    conn.close()
    print(f'Imported {count} files into {DB}')


if __name__ == '__main__':
    import_all()
