#!/usr/bin/env python3
"""Backfill the created/modified columns from the existing details_json data."""

import argparse
import json
import re
import sqlite3
from datetime import datetime
from typing import Iterable, List, Optional


def add_column_if_missing(conn: sqlite3.Connection, column_name: str, column_type: str = "DATETIME") -> None:
    existing = conn.execute(
        "PRAGMA table_info(recipes)"
    ).fetchall()
    if any(row[1] == column_name for row in existing):
        return
    conn.execute(f"ALTER TABLE recipes ADD COLUMN {column_name} {column_type}")
    conn.commit()


def normalize_detail_value(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return value


def get_detail_entries(details_value) -> List[str]:
    if details_value is None:
        return []
    if isinstance(details_value, str):
        try:
            parsed = json.loads(details_value)
        except Exception:
            parsed = details_value
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        if isinstance(parsed, str):
            return [parsed]
        return []
    if isinstance(details_value, list):
        return [str(x) for x in details_value]
    return []


def parse_datetime(value: str) -> Optional[datetime]:
    if value is None:
        return None
    candidate = normalize_detail_value(value).strip()
    if not candidate:
        return None

    # Common ISO date/time forms
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass

    candidate = candidate.replace(" at ", " ")
    candidate = candidate.replace("T", " ")
    candidate = candidate.replace("UTC", "")
    candidate = candidate.strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d %B %Y %H:%M:%S",
        "%d %B %Y %H:%M",
        "%d %B %Y",
        "%d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M",
        "%d %b %Y",
        "%d %B %Y, %H:%M",
        "%d %B %Y, %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def extract_detail_datetime(details_value, field: str) -> Optional[str]:
    field = (field or "").lower().strip()
    if field == "created":
        prefixes = ("created", "date created")
    elif field == "modified":
        prefixes = ("modified", "last modified", "last updated", "updated")
    else:
        prefixes = ()

    for raw_line in get_detail_entries(details_value):
        line = normalize_detail_value(raw_line)
        lower = line.lower()
        if not any(lower.startswith(prefix) for prefix in prefixes):
            continue

        value = line.split(":", 1)[-1].strip() if ":" in line else line
        value = re.sub(r"^(?:created|date created|modified|last modified|last updated|updated)\s*[:-]?\s*", "", value, flags=re.I)
        value = value.strip()
        if not value:
            continue

        parsed = parse_datetime(value)
        if parsed is None:
            continue
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    return None


def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
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
        """
    )
    add_column_if_missing(conn, "created", "DATETIME")
    add_column_if_missing(conn, "modified", "DATETIME")
    conn.commit()


def migrate_all(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    cur = conn.cursor()
    updated = 0

    rows = cur.execute(
        "SELECT id, details_json FROM recipes WHERE details_json IS NOT NULL"
    ).fetchall()

    for row_id, details_json in rows:
        created_value = extract_detail_datetime(details_json, "created")
        modified_value = extract_detail_datetime(details_json, "modified")
        if created_value is None and modified_value is None:
            continue

        cur.execute(
            "UPDATE recipes SET created = ?, modified = ? WHERE id = ?",
            (created_value, modified_value, row_id),
        )
        updated += 1

    conn.commit()
    conn.close()
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill created/modified timestamps from details_json")
    parser.add_argument("--db", default="recipes.db", help="SQLite database path")
    args = parser.parse_args()

    count = migrate_all(args.db)
    print(f"Updated {count} rows")


if __name__ == "__main__":
    main()
