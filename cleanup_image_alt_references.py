#!/usr/bin/env python3
"""
Remove image/alt HTML references from recipe text fields.

- Removes <img ...> tags and escaped &lt;img ...&gt; tags.
- Removes alt=... attributes (and escaped variants) from remaining text.
- Applies cleanup to scalar text columns and JSON text columns.
- Creates a SQLite backup file before applying changes (unless --dry-run).
"""

import argparse
import datetime as dt
import json
import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any


IMG_TAG_RE = re.compile(r"<\s*img\b[^>]*>", flags=re.IGNORECASE | re.DOTALL)
ESCAPED_IMG_TAG_RE = re.compile(r"&lt;\s*img\b.*?&gt;", flags=re.IGNORECASE | re.DOTALL)
ALT_ATTR_RE = re.compile(r"\s+alt\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", flags=re.IGNORECASE)
ESCAPED_ALT_ATTR_RE = re.compile(
    r"\s+alt\s*=\s*(?:&quot;.*?&quot;|\"[^\"]*\"|'[^']*'|[^\s>]+)",
    flags=re.IGNORECASE | re.DOTALL,
)
SRC_ATTR_RE = re.compile(
    r"\s+src(?:set)?\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    flags=re.IGNORECASE,
)
ESCAPED_SRC_ATTR_RE = re.compile(
    r"\s+src(?:set)?\s*=\s*(?:&quot;.*?&quot;|\"[^\"]*\"|'[^']*'|[^\s>]+)",
    flags=re.IGNORECASE | re.DOTALL,
)
LINE_WITH_IMAGE_REF_RE = re.compile(
    r"(<\s*img\b|&lt;\s*img\b|\balt\s*=|\bsrc(?:set)?\s*=)",
    flags=re.IGNORECASE,
)

TEXT_COLUMNS = ("title", "preamble", "ingredients_text", "raw_json")
JSON_COLUMNS = ("ingredients_json", "method_json", "notes_json", "details_json")


def clean_text(value: str) -> tuple[str, int]:
    if not value:
        return value, 0

    text = str(value)
    removed_hits = 0

    for pattern in (
        IMG_TAG_RE,
        ESCAPED_IMG_TAG_RE,
        ALT_ATTR_RE,
        ESCAPED_ALT_ATTR_RE,
        SRC_ATTR_RE,
        ESCAPED_SRC_ATTR_RE,
    ):
        text, n = pattern.subn(" ", text)
        removed_hits += n

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if LINE_WITH_IMAGE_REF_RE.search(line):
            removed_hits += 1
            continue
        line = " ".join(line.split())
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned, removed_hits


def clean_json_value(value: Any) -> tuple[Any, int]:
    removed = 0
    if isinstance(value, str):
        cleaned, n = clean_text(value)
        return cleaned, n
    if isinstance(value, list):
        out = []
        for item in value:
            cleaned_item, n = clean_json_value(item)
            removed += n
            out.append(cleaned_item)
        return out, removed
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            cleaned_v, n = clean_json_value(v)
            removed += n
            out[k] = cleaned_v
        return out, removed
    return value, 0


def clean_json_text(json_text: str) -> tuple[str, int]:
    if not json_text:
        return json_text, 0
    try:
        parsed = json.loads(json_text)
    except Exception:
        return clean_text(json_text)

    cleaned, removed = clean_json_value(parsed)
    if removed <= 0:
        return json_text, 0
    return json.dumps(cleaned, ensure_ascii=False), removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove image/alt HTML references from recipe text fields")
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
        SELECT id, title, preamble, ingredients_text, ingredients_json, method_json, notes_json, details_json, raw_json
        FROM recipes
        """
    ).fetchall()

    recipes_changed = 0
    fields_changed = 0
    refs_removed = 0
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if not args.dry_run:
            conn.execute("BEGIN")

        for row in rows:
            updates: dict[str, Any] = {}
            row_field_changes = 0
            row_removed = 0

            for col in TEXT_COLUMNS:
                old = row[col]
                if not old:
                    continue
                new, removed = clean_text(old)
                if removed > 0 and new != old:
                    updates[col] = new
                    row_field_changes += 1
                    row_removed += removed

            for col in JSON_COLUMNS:
                old = row[col]
                if not old:
                    continue
                new, removed = clean_json_text(old)
                if removed > 0 and new != old:
                    updates[col] = new
                    row_field_changes += 1
                    row_removed += removed

            if not updates:
                continue

            recipes_changed += 1
            fields_changed += row_field_changes
            refs_removed += row_removed

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
        f"fields changed={fields_changed}, image/alt refs removed={refs_removed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
