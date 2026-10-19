#!/usr/bin/env python3
"""
Normalize recipe details_json so it keeps only:
- Written...
- Category...

Removes metadata lines such as Published/Created/Last Updated/Hits and any
other non-written/category detail lines.
"""

import argparse
import datetime as dt
import json
import re
import shutil
import sqlite3
from pathlib import Path


KEEP_RE = re.compile(r"^\s*(written\b|category\b)", flags=re.IGNORECASE)
DROP_TARGET_RE = re.compile(
    r"^\s*(published\b|created\b|last\s*updated\b|hits?\b)",
    flags=re.IGNORECASE,
)


def clean_details_list(items):
    kept = []
    removed_target = 0
    removed_other = 0
    for item in items or []:
        line = str(item or "").strip()
        if not line:
            removed_other += 1
            continue
        if KEEP_RE.search(line):
            kept.append(line)
            continue
        if DROP_TARGET_RE.search(line):
            removed_target += 1
        else:
            removed_other += 1
    return kept, removed_target, removed_other


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep only Written/Category lines in details_json")
    parser.add_argument("--db", default="recipes.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without updating DB")
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
    rows = conn.execute("SELECT id, details_json FROM recipes").fetchall()

    changed = 0
    removed_target_total = 0
    removed_other_total = 0
    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if not args.dry_run:
            conn.execute("BEGIN")

        for row in rows:
            raw = row["details_json"]
            if not raw:
                continue
            try:
                arr = json.loads(raw)
            except Exception:
                continue
            if not isinstance(arr, list):
                continue

            cleaned, removed_target, removed_other = clean_details_list(arr)
            if cleaned == arr:
                continue

            changed += 1
            removed_target_total += removed_target
            removed_other_total += removed_other

            if not args.dry_run:
                conn.execute(
                    "UPDATE recipes SET details_json=?, modified=? WHERE id=?",
                    (json.dumps(cleaned, ensure_ascii=False), now_str, row["id"]),
                )

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
        f"{mode}: recipes changed={changed}, "
        f"removed target lines={removed_target_total}, removed other lines={removed_other_total}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
