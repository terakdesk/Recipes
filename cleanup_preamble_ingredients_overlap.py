#!/usr/bin/env python3
"""
Remove lines from recipe preamble that duplicate ingredient lines.

- Compares line-by-line using normalized text.
- Leaves ingredients data untouched.
- Creates a SQLite backup file before applying changes (unless --dry-run).
"""

import argparse
import datetime as dt
import json
import re
import shutil
import sqlite3
from pathlib import Path


def normalize_line(text: str) -> str:
    s = (text or "").strip().lower()
    # Remove common list markers so matching is more reliable.
    while s.startswith(("-", "*", "•")):
        s = s[1:].strip()
    # Collapse repeated whitespace.
    s = " ".join(s.split())
    return s


def normalize_alnum(text: str) -> str:
    s = normalize_line(text)
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = " ".join(s.split())
    return s


def build_ingredient_line_sets(ingredients_json: str) -> tuple[set[str], set[str]]:
    if not ingredients_json:
        return set(), set()
    try:
        items = json.loads(ingredients_json)
    except Exception:
        return set(), set()

    out: set[str] = set()
    out_alnum: set[str] = set()
    if not isinstance(items, list):
        return out, out_alnum

    for item in items:
        if item is None:
            continue
        for raw_line in str(item).splitlines():
            n = normalize_line(raw_line)
            if n:
                out.add(n)
            n_alnum = normalize_alnum(raw_line)
            if n_alnum:
                out_alnum.add(n_alnum)
    return out, out_alnum


def is_fuzzy_duplicate(
    pre_line_norm: str,
    pre_line_alnum: str,
    ingredient_lines: set[str],
    ingredient_lines_alnum: set[str],
    min_contains_len: int,
) -> bool:
    if pre_line_norm and pre_line_norm in ingredient_lines:
        return True
    if pre_line_alnum and pre_line_alnum in ingredient_lines_alnum:
        return True

    if not pre_line_alnum or len(pre_line_alnum) < min_contains_len:
        return False

    for ing_alnum in ingredient_lines_alnum:
        if len(ing_alnum) < min_contains_len:
            continue
        if pre_line_alnum in ing_alnum or ing_alnum in pre_line_alnum:
            return True

    return False


def clean_preamble(
    preamble: str,
    ingredient_lines: set[str],
    ingredient_lines_alnum: set[str],
    fuzzy_contains: bool,
    min_contains_len: int,
) -> tuple[str, int]:
    if not preamble or not ingredient_lines:
        return preamble, 0

    removed = 0
    kept_lines = []
    for raw_line in str(preamble).splitlines():
        n = normalize_line(raw_line)
        n_alnum = normalize_alnum(raw_line)
        should_remove = False
        if fuzzy_contains:
            should_remove = is_fuzzy_duplicate(
                n,
                n_alnum,
                ingredient_lines,
                ingredient_lines_alnum,
                min_contains_len,
            )
        elif n and n in ingredient_lines:
            should_remove = True

        if should_remove:
            removed += 1
            continue
        kept_lines.append(raw_line)

    # Keep paragraph structure tidy: max 1 consecutive blank line.
    tidied = []
    prev_blank = False
    for line in kept_lines:
        blank = (line.strip() == "")
        if blank and prev_blank:
            continue
        tidied.append(line)
        prev_blank = blank

    cleaned = "\n".join(tidied).strip()
    return cleaned, removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove ingredient lines from preamble text")
    parser.add_argument("--db", default="recipes.db", help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without updating DB")
    parser.add_argument(
        "--fuzzy-contains",
        action="store_true",
        help="Also remove near-duplicates using normalized containment matching.",
    )
    parser.add_argument(
        "--min-contains-len",
        type=int,
        default=12,
        help="Minimum normalized length used for fuzzy containment matching.",
    )
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

    rows = conn.execute("SELECT id, preamble, ingredients_json FROM recipes").fetchall()

    changed_recipes = 0
    removed_lines_total = 0

    now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if not args.dry_run:
            conn.execute("BEGIN")

        for row in rows:
            preamble = row["preamble"]
            if not preamble:
                continue

            ingredient_lines, ingredient_lines_alnum = build_ingredient_line_sets(row["ingredients_json"])
            if not ingredient_lines:
                continue

            cleaned, removed = clean_preamble(
                preamble,
                ingredient_lines,
                ingredient_lines_alnum,
                args.fuzzy_contains,
                args.min_contains_len,
            )
            if removed <= 0:
                continue

            changed_recipes += 1
            removed_lines_total += removed

            if not args.dry_run:
                conn.execute(
                    "UPDATE recipes SET preamble=?, modified=? WHERE id=?",
                    (cleaned, now_str, row["id"]),
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
    strategy = "fuzzy-contains" if args.fuzzy_contains else "exact"
    print(
        f"{mode} ({strategy}): recipes changed={changed_recipes}, "
        f"preamble lines removed={removed_lines_total}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
