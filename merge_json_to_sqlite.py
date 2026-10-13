#!/usr/bin/env python3
import sqlite3
import json
import glob
import os

DB = 'recipes.db'
SRC_GLOB = 'saved_recipes_json/*.json'


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
          (filename,title,preamble,ingredients_json,ingredients_text,method_json,notes_json,details_json,raw_json)
          VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            os.path.basename(path),
            data.get('title'),
            data.get('preamble'),
            json.dumps(data.get('ingredients') or []),
            ingredients_text,
            json.dumps(data.get('method') or []),
            json.dumps(data.get('notes') or []),
            json.dumps(data.get('details') or []),
            json.dumps(data)
        ))
        count += 1

    conn.commit()
    conn.close()
    print(f'Imported {count} files into {DB}')


if __name__ == '__main__':
    import_all()
