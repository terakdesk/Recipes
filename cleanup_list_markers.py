#!/usr/bin/env python3
"""
Remove list-marker prefixes from recipe text stored in SQLite.

This keeps the app's display formatting from showing double list markers.
Important: in ingredients, quantity lines like "3 onions" are preserved.
"""

import argparse
import datetime as dt
import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any


BULLET_PREFIX_RE = re.compile(
    r"^\s*(?:[-*•◦▪▫‣⁃∙●○◆◇■□▶▷►▸]+)\s+"
)
LETTER_LIST_PREFIX_RE = re.compile(r"^\s*[A-Za-z][\)\]\.:/-]+\s+")
NUMBER_LIST_PREFIX_RE = re.compile(r"^\s*\d+[\)\]\.:/-]+\s+")
PAREN_NUMBER_PREFIX_RE = re.compile(r"^\s*\(\d+\)\s+")
ROMAN_LIST_PREFIX_RE = re.compile(
    r"^\s*(?:[ivxlcdm]+)[\)\]\.:/-]+\s+",
    flags=re.IGNORECASE,
)


def clean_line(line: str, is_ingredients: bool) -> tuple[str, bool]:
    original = line
    text = str(line or "")

    # Strip symbol bullets first.
    text = BULLET_PREFIX_RE.sub("", text)

    # Remove classic list numbering markers.
    # Keep ingredient quantity lines such as "3 onions" (no punctuation marker).
    text = PAREN_NUMBER_PREFIX_RE.sub("", text)
    text = ROMAN_LIST_PREFIX_RE.sub("", text)
    text = LETTER_LIST_PREFIX_RE.sub("", text)
    text = NUMBER_LIST_PREFIX_RE.sub("", text)

    text = text.strip()
    changed = text != str(original).strip()
    return text, changed


def clean_text_block(text: str, is_ingredients: bool) -> tuple[str, int]:
    if not text:
        return text, 0
    changed = 0
    out_lines: list[str] = []
    for raw in str(text).splitlines():
        cleaned, line_changed = clean_line(raw, is_ingredients=is_ingredients)
        if line_changed:
            changed += 1
        if cleaned:
            out_lines.append(cleaned)
    return "\n".join(out_lines), changed


def clean_list(items: list[Any], is_ingredients: bool) -> tuple[list[Any], int]:
    changed = 0
    out = []
    for item in items:
        if item is None:
            continue
        cleaned, item_changed = clean_line(str(item), is_ingredients=is_ingredients)
        if item_changed:
            changed += 1
        if cleaned:
            out.append(cleaned)
    return out, changed


def clean_json_list(json_text: str, is_ingredients: bool) -> tuple[str, int]:
    if not json_text:
        return json_text, 0
    try:
        parsed = json.loads(json_text)
    except Exception:
        cleaned, changed = clean_text_block(json_text, is_ingredients=is_ingredients)
        return cleaned, changed
    if not isinstance(parsed, list):
        return json_text, 0
    cleaned_list, changed = clean_list(parsed, is_ingredients=is_ingredients)
    if changed <= 0 and cleaned_list == parsed:
        return json_text, 0
    return json.dumps(cleaned_list, ensure_ascii=False), changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove list-marker prefixes from recipe text")
    parser.add_argument("--db", default="recipes.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without updating DB")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    if not args.dry_run:
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.with_suffix(db_path.suffix + f".bak_{ts}")
        shutil.copy2(db_path, backup_path)
        print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, preamble, ingredients_json, ingredients_text, method_json, notes_json, details_json
        FROM recipes
        """
    ).fetchall()

    recipes_changed = 0
    fields_changed = 0
    markers_removed = 0
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if not args.dry_run:
            conn.execute("BEGIN")

        for row in rows:
            updates: dict[str, Any] = {}

            preamble_clean, preamble_removed = clean_text_block(row["preamble"] or "", is_ingredients=False)
            if preamble_removed > 0 and preamble_clean != (row["preamble"] or ""):
                updates["preamble"] = preamble_clean
                fields_changed += 1
                markers_removed += preamble_removed

            ingredients_clean_json, ingredients_removed = clean_json_list(row["ingredients_json"] or "", is_ingredients=True)
            if ingredients_removed > 0 and ingredients_clean_json != (row["ingredients_json"] or ""):
                updates["ingredients_json"] = ingredients_clean_json
                try:
                    items = json.loads(ingredients_clean_json)
                except Exception:
                    items = []
                updates["ingredients_text"] = " ".join([str(x).strip().lower() for x in (items or []) if x])
                fields_changed += 2
                markers_removed += ingredients_removed

            method_clean_json, method_removed = clean_json_list(row["method_json"] or "", is_ingredients=False)
            if method_removed > 0 and method_clean_json != (row["method_json"] or ""):
                updates["method_json"] = method_clean_json
                fields_changed += 1
                markers_removed += method_removed

            notes_clean_json, notes_removed = clean_json_list(row["notes_json"] or "", is_ingredients=False)
            if notes_removed > 0 and notes_clean_json != (row["notes_json"] or ""):
                updates["notes_json"] = notes_clean_json
                fields_changed += 1
                markers_removed += notes_removed

            details_clean_json, details_removed = clean_json_list(row["details_json"] or "", is_ingredients=False)
            if details_removed > 0 and details_clean_json != (row["details_json"] or ""):
                updates["details_json"] = details_clean_json
                fields_changed += 1
                markers_removed += details_removed

            if not updates:
                continue

            recipes_changed += 1
            if not args.dry_run:
                set_cols = ", ".join([f"{k}=?" for k in updates.keys()])
                vals = list(updates.values()) + [now_str, row["id"]]
                conn.execute(f"UPDATE recipes SET {set_cols}, modified=? WHERE id=?", vals)

        if not args.dry_run:
            conn.commit()
    except Exception:
        if not args.dry_run:
            conn.rollback()
        raise
    finally:
        conn.close()

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(
        f"{mode}: recipes changed={recipes_changed}, "
        f"fields changed={fields_changed}, list markers removed={markers_removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
