#!/usr/bin/env python3
"""
filtered_tags.py

Scan a directory of saved HTML files (default: `saved_recipes`) and
extract key parts into JSON files. Extracted fields: title, preamble,
ingredients, method, notes.

Usage:
  python filtered_tags.py --src saved_recipes --out saved_recipes_json

This tries to use BeautifulSoup if available for robust parsing but
falls back to lightweight heuristics if not.
"""
import argparse
import json
import os
import re
import sys
from typing import List, Optional

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


KEYWORDS = {
    "ingredients": ["ingredient", "ingredients"],
    "method": ["method", "methods", "instruction", "instructions", "direction", "directions", "preparation"],
    "notes": ["note", "notes", "serving", "tips"],
    "details": ["detail", "details"],
}


def text_of(elem) -> str:
    if elem is None:
        return ""
    return " ".join(elem.stripped_strings) if hasattr(elem, "stripped_strings") else str(elem)


def extract_section_by_heading(soup, targets: List[str]) -> Optional[List[str]]:
    # Find headings that match any target keyword, then collect following
    # list items or paragraphs until the next heading of same level
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        txt = h.get_text(separator=" ").strip().lower()
        if any(t in txt for t in targets):
            items = []
            # look at next siblings
            sib = h.find_next_sibling()
            while sib is not None and sib.name not in ["h1", "h2", "h3", "h4"]:
                if sib.name in ["ul", "ol"]:
                    for li in sib.find_all("li"):
                        items.append(li.get_text(separator=" ").strip())
                elif sib.name == "p":
                    s = sib.get_text(separator=" ").strip()
                    if s:
                        items.append(s)
                else:
                    # capture text blocks with <br>
                    s = sib.get_text(separator=" ").strip()
                    if s:
                        items.append(s)
                sib = sib.find_next_sibling()
            return items or None
    return None


def extract_details_from_dl(soup) -> Optional[List[str]]:
    # Look for a definition list containing a 'Details' term and collect the following dd entries
    for dl in soup.find_all('dl'):
        children = list(dl.children)
        found = False
        collected = []
        for ch in children:
            if getattr(ch, 'name', None) == 'dt':
                txt = ch.get_text(separator=' ').strip().lower()
                if 'detail' in txt:
                    found = True
                    continue
                # if another dt after we already found details, stop
                if found:
                    break
            if found and getattr(ch, 'name', None) == 'dd':
                txt = ch.get_text(separator=' ').strip()
                if txt:
                    collected.append(txt)
        if found and collected:
            return collected
    return None


def parse_with_bs4(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # title
    title = None
    title_elem = None
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        title_elem = soup.title
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(separator=" ").strip()
            title_elem = h1

    # preamble: text between the title heading and the ingredients heading
    preamble = None
    # find ingredients heading to mark the end
    ing_targets = KEYWORDS["ingredients"]
    def is_ingredients_heading(tag):
        if not tag or not getattr(tag, 'name', None):
            return False
        if tag.name in ["h1", "h2", "h3", "h4"]:
            txt = tag.get_text(separator=" ").strip().lower()
            return any(t in txt for t in ing_targets)
        return False

    # Start from the title element if present, otherwise from article/body
    start_node = title_elem or soup.find("article") or soup.find("main") or soup.body
    if start_node:
        parts = []
        sib = start_node.find_next_sibling() if start_node is not None else None
        # also allow descent into children if title is the only marker
        if sib is None and start_node is not None and start_node is not soup.body:
            sib = start_node.find_next()
        while sib is not None:
            # stop when we reach an ingredients heading
            if is_ingredients_heading(sib):
                break
            # skip menu/navigation/sidebar elements
            if getattr(sib, 'name', None) in ["nav", "header", "footer", "aside"]:
                sib = sib.find_next_sibling()
                continue
            cls = " ".join(sib.get('class') or []) if hasattr(sib, 'get') else ""
            idv = sib.get('id', '') if hasattr(sib, 'get') else ''
            if any(k in cls.lower() for k in ["menu", "nav", "breadcrumb"]) or any(k in idv.lower() for k in ["menu", "nav", "breadcrumb"]):
                sib = sib.find_next_sibling()
                continue
            # collect paragraphs, div text, and lists
            if sib.name == 'p' or sib.name in ['div'] or sib.name in ['ul', 'ol']:
                txt = sib.get_text(separator=" ").strip()
                if txt:
                    parts.append(txt)
            sib = sib.find_next_sibling()
        if parts:
            # join paragraphs into a single preamble string, preserving HTML
            preamble = "\n\n".join(parts)

    # details -> tags
    details = extract_section_by_heading(soup, KEYWORDS.get("details", []))
    if not details:
        details = extract_details_from_dl(soup)

    ingredients = extract_section_by_heading(soup, KEYWORDS["ingredients"])
    method = extract_section_by_heading(soup, KEYWORDS["method"])
    notes = extract_section_by_heading(soup, KEYWORDS["notes"])

    return {
        "title": title,
        "preamble": preamble,
        "ingredients": ingredients,
        "method": method,
        "notes": notes,
        "details": details,
    }


def parse_with_fallback(html: str) -> dict:
    # Very small fallback parser using regexes and simple splits
    title = None
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    else:
        m2 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if m2:
            title = re.sub(r"\s+", " ", m2.group(1)).strip()

    def find_section(keyword_list):
        # look for heading variations
        for kw in keyword_list:
            pat = re.compile(rf"<h[1-4][^>]*>\s*([^<]*{kw}[^<]*)</h[1-4]>", re.I)
            m = pat.search(html)
            if m:
                start = m.end()
                # grab up to next heading
                m2 = re.search(r"<h[1-4][^>]*>", html[start:], re.I)
                block = html[start: start + m2.start()] if m2 else html[start: start + 2000]
                # find li items
                items = re.findall(r"<li[^>]*>(.*?)</li>", block, re.I | re.S)
                if items:
                    return [re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", it)).strip() for it in items]
                # fallback paragraphs
                ps = re.findall(r"<p[^>]*>(.*?)</p>", block, re.I | re.S)
                if ps:
                    return [re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", p)).strip() for p in ps]
        return None

    ingredients = find_section(KEYWORDS["ingredients"])
    method = find_section(KEYWORDS["method"])
    notes = find_section(KEYWORDS["notes"])
    # details -> tags (fallback)
    details = find_section(["details", "detail"]) 
    if not details:
        # look for a <dl> with a <dt>Details</dt> and collect following <dd> entries
        m_dl = re.search(r"<dl[^>]*>([\s\S]*?)</dl>", html, re.I)
        if m_dl:
            dl_block = m_dl.group(1)
            # find dt that contains 'details'
            if re.search(r"<dt[^>]*>\s*[^<]*details[^<]*</dt>", dl_block, re.I):
                dd_items = re.findall(r"<dd[^>]*>([\s\S]*?)</dd>", dl_block, re.I)
                if dd_items:
                    clean = [re.sub(r"<[^>]+>", "", re.sub(r"\s+", " ", d)).strip() for d in dd_items]
                    details = clean

    # preamble: text between title and ingredients heading, stripped of menu/nav blocks
    preamble = None
    # find title end
    title_end = None
    m_title = re.search(r"<h1[^>]*>.*?</h1>", html, re.I | re.S)
    if m_title:
        title_end = m_title.end()
    else:
        m_title2 = re.search(r"<title[^>]*>.*?</title>", html, re.I | re.S)
        if m_title2:
            title_end = m_title2.end()

    # find ingredients heading start
    ing_start = None
    for kw in KEYWORDS['ingredients']:
        m = re.search(rf"<h[1-4][^>]*>[^<]*{kw}[^<]*</h[1-4]>", html, re.I)
        if m:
            ing_start = m.start()
            break

    if title_end is not None:
        end_pos = ing_start if ing_start is not None else title_end + 1000
        block = html[title_end:end_pos]
        # remove nav/menu blocks
        block = re.sub(r"<nav[\s\S]*?</nav>", "", block, flags=re.I)
        block = re.sub(r"<ul[^>]*class=[\'\"]?[^>]*menu[^>]*>[\s\S]*?</ul>", "", block, flags=re.I)
        # extract first paragraphs from block
        ps = re.findall(r"<p[^>]*>(.*?)</p>", block, re.I | re.S)
        if ps:
            # convert paragraphs to plain text (strip tags)
            clean = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", p)).strip() for p in ps]
            preamble = "\n\n".join([c for c in clean if c]) or None
        else:
            # fallback: keep block HTML but trim whitespace
            txt = re.sub(r"<[^>]+>", "", block).strip()
            preamble = txt or None

    return {"title": title, "preamble": preamble, "ingredients": ingredients, "method": method, "notes": notes, "details": details}


def parse_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()
    if BeautifulSoup:
        try:
            return parse_with_bs4(html)
        except Exception:
            return parse_with_fallback(html)
    else:
        return parse_with_fallback(html)


def main():
    parser = argparse.ArgumentParser(description="Extract recipe sections from saved HTML into JSON files")
    parser.add_argument("--src", default="saved_recipes", help="Source folder with HTML files")
    parser.add_argument("--out", default="saved_recipes_json", help="Output folder for JSON files")
    parser.add_argument("--pattern", default=".html", help="Filename pattern (suffix) to process")
    args = parser.parse_args()

    src = args.src
    out = args.out
    pat = args.pattern

    if not os.path.isdir(src):
        print(f"Source folder does not exist: {src}")
        sys.exit(1)
    os.makedirs(out, exist_ok=True)

    files = [p for p in sorted(os.listdir(src)) if p.lower().endswith(pat.lower())]
    if not files:
        print("No matching files found in", src)
        return

    for fname in files:
        inpath = os.path.join(src, fname)
        data = parse_file(inpath)
        # attach source filename
        data["source_file"] = fname
        # write json
        base = os.path.splitext(fname)[0]
        outpath = os.path.join(out, base + ".json")
        with open(outpath, "w", encoding="utf-8") as outfd:
            json.dump(data, outfd, ensure_ascii=False, indent=2)
        print(f"Wrote: {outpath}")


if __name__ == "__main__":
    main()
