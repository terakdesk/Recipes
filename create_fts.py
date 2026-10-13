#!/usr/bin/env python3
"""Build or rebuild an FTS5 virtual table for fast full-text search.

Creates `recipes_fts` (title, ingredients) and populates it from `recipes`.
Run this after creating or updating `recipes.db`.
"""
import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'recipes.db')


def build_fts():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    # Drop existing FTS table if present
    try:
        cur.execute("DROP TABLE IF EXISTS recipes_fts")
    except Exception:
        pass

    # Create FTS5 virtual table. Use contentless FTS or content option.
    cur.execute("CREATE VIRTUAL TABLE recipes_fts USING fts5(title, ingredients)")

    # Populate from current recipes table
    try:
        cur.execute("INSERT INTO recipes_fts(rowid, title, ingredients) SELECT id, IFNULL(title,''), IFNULL(ingredients_text,'') FROM recipes")
        conn.commit()
        print('FTS table recipes_fts created/updated.')
    except sqlite3.OperationalError as e:
        print('SQLite OperationalError:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    build_fts()


if __name__ == '__main__':
    build_fts()
