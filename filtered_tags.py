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
import html as html_lib
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
    "ingredients": ["ingredient", "ingredients", "key ingredients"],
    "method": ["method", "methods", "instruction", "instructions", "direction", "directions", "preparation", "quick cooking steps", "steps"],
    "notes": ["note", "notes", "serving", "tips"],
    "details": ["detail", "details"],
}


def clean_text_preserving_newlines(value: Optional[str]) -> str:
    """Convert HTML fragments to plain text while preserving line breaks."""
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # preserve common HTML line breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(
        r"</?(p|div|li|ul|ol|h[1-6]|section|article|tr|td|th|blockquote)[^>]*>",
        "\n",
        text,
        flags=re.I,
    )

    # remove any remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)

    # tidy whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()
    return text


def clean_text_list(items: Optional[List[str]]) -> Optional[List[str]]:
    if not items:
        return None

    cleaned = []
    for item in items:
        text = clean_text_preserving_newlines(item)
        if text:
            cleaned.append(text)
    return cleaned or None


def extract_section_by_heading(soup, targets: List[str]) -> Optional[List[str]]:
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        txt = h.get_text(separator=" ").strip().lower()
        if any(t in txt for t in targets):
            items = []
            sib = h.find_next_sibling()
            while sib is not None and sib.name not in ["h1", "h2", "h3", "h4"]:
                if sib.name in ["ul", "ol"]:
                    for li in sib.find_all("li"):
                        value = clean_text_preserving_newlines(li.get_text(separator=" ", strip=True))
                        if value:
                            items.append(value)
                elif sib.name == "p":
                    s = clean_text_preserving_newlines(sib.get_text(separator=" ", strip=True))
                    if s:
                        items.append(s)
                else:
                    s = clean_text_preserving_newlines(sib.get_text(separator=" ", strip=True))
                    if s:
                        items.append(s)
                sib = sib.find_next_sibling()
            return clean_text_list(items) or None
    return None


def extract_details_from_dl(soup) -> Optional[List[str]]:
    for dl in soup.find_all("dl"):
        children = list(dl.children)
        found = False
        collected = []
        for ch in children:
            if getattr(ch, "name", None) == "dt":
                txt = ch.get_text(separator=" ").strip().lower()
                if "detail" in txt:
                    found = True
                    continue
                if found:
                    break
            if found and getattr(ch, "name", None) == "dd":
                txt = clean_text_preserving_newlines(ch.get_text(separator=" ", strip=True))
                if txt:
                    collected.append(txt)
        if found and collected:
            return collected
    return None


def extract_preamble_from_article(soup) -> Optional[str]:
    article_body = (
        soup.find("div", attrs={"itemprop": "articleBody"})
        or soup.find("article")
        or soup.find("main")
        or soup.body
    )

    if not article_body:
        return None

    # Remove obvious non-content blocks
    for selector in [
        "script", "style", "nav", "header", "footer", "aside",
        ".icons", ".pager", ".breadcrumb", "dl.article-info",
        ".mod-search", ".search"
    ]:
        for node in article_body.select(selector):
            node.decompose()

    candidates = []
    my_area = article_body.find(class_="my_area")

    if my_area:
        nodes = my_area.find_all(["p", "div", "li"], recursive=True)
    else:
        nodes = article_body.find_all(["p", "div"], recursive=True)

    for node in nodes:
        text = " ".join(node.stripped_strings).strip()
        if not text:
            continue

        lower = text.lower()
        if any(key in lower for key in ["ingredients", "method", "notes", "details", "written by", "category:", "published:", "created:", "last updated:", "hits:"]):
            continue

        # skip very short junk
        if len(text) < 12:
            continue

        candidates.append(text)

        if len(candidates) >= 5:
            break

    if candidates:
        return "\n\n".join(candidates)

    # Last fallback: use the first meaningful paragraphs at all
    fallback = []
    for node in (article_body.find_all(["p", "div"], recursive=True)[:10]):
        text = " ".join(node.stripped_strings).strip()
        if text and len(text) >= 12 and not any(key in text.lower() for key in ["ingredients", "method", "notes", "details"]):
            fallback.append(text)
    if fallback:
        return "\n\n".join(fallback)

    return None


def parse_with_bs4(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = None
    title_elem = None

    # Prefer article headline over document title
    headline = soup.find("h2", itemprop="headline")
    if headline:
        title = clean_text_preserving_newlines(headline.get_text(" ", strip=True))
        title_elem = headline
    elif soup.title and soup.title.string:
        title = clean_text_preserving_newlines(soup.title.string)
        title_elem = soup.title

    preamble = extract_preamble_from_article(soup)

    details = extract_section_by_heading(soup, KEYWORDS.get("details", []))
    if not details:
        details = extract_details_from_dl(soup)

    ingredients = clean_text_list(extract_section_by_heading(soup, KEYWORDS["ingredients"]))
    method = clean_text_list(extract_section_by_heading(soup, KEYWORDS["method"]))
    notes = clean_text_list(extract_section_by_heading(soup, KEYWORDS["notes"]))

    return {
        "title": title,
        "preamble": preamble,
        "ingredients": ingredients,
        "method": method,
        "notes": notes,
        "details": clean_text_list(details),
    }


def parse_with_fallback(html: str) -> dict:
    title = None
    m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if m:
        title = clean_text_preserving_newlines(m.group(1))
    else:
        m2 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if m2:
            title = clean_text_preserving_newlines(m2.group(1))

    def find_section(keyword_list):
        for kw in keyword_list:
            pat = re.compile(rf"<h[1-4][^>]*>\s*([^<]*{kw}[^<]*)</h[1-4]>", re.I)
            m = pat.search(html)
            if m:
                start = m.end()
                m2 = re.search(r"<h[1-4][^>]*>", html[start:], re.I)
                block = html[start: start + m2.start()] if m2 else html[start: start + 2000]
                items = re.findall(r"<li[^>]*>(.*?)</li>", block, re.I | re.S)
                if items:
                    cleaned = [clean_text_preserving_newlines(item) for item in items]
                    return [item for item in cleaned if item]

                ps = re.findall(r"<p[^>]*>(.*?)</p>", block, re.I | re.S)
                if ps:
                    cleaned = [clean_text_preserving_newlines(p) for p in ps]
                    return [item for item in cleaned if item]
        return None

    ingredients = clean_text_list(find_section(KEYWORDS["ingredients"]))
    method = clean_text_list(find_section(KEYWORDS["method"]))
    notes = clean_text_list(find_section(KEYWORDS["notes"]))
    details = clean_text_list(find_section(["details", "detail"]))

    if not details:
        m_dl = re.search(r"<dl[^>]*>([\\s\\S]*?)</dl>", html, re.I)
        if m_dl:
            dl_block = m_dl.group(1)
            if re.search(r"<dt[^>]*>\\s*[^<]*details[^<]*</dt>", dl_block, re.I):
                dd_items = re.findall(r"<dd[^>]*>([\\s\\S]*?)</dd>", dl_block, re.I)
                if dd_items:
                    cleaned = [clean_text_preserving_newlines(d) for d in dd_items]
                    details = [item for item in cleaned if item] or None

    # regex fallback for preamble
    preamble = None

    article_block = None
    match = re.search(r"<div[^>]*itemprop=['\\\"]articleBody['\\\"][^>]*>([\\s\\S]*?)</div>", html, re.I)
    if match:
        article_block = match.group(1)
    else:
        m_art = re.search(r"<article[^>]*>([\\s\\S]*?)</article>", html, re.I)
        if m_art:
            article_block = m_art.group(1)

    if article_block:
        cleaned = re.sub(r"<script[\\s\\S]*?</script>", "", article_block, flags=re.I)
        cleaned = re.sub(r"<style[\\s\\S]*?</style>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<nav[\\s\\S]*?</nav>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<header[\\s\\S]*?</header>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<footer[\\s\\S]*?</footer>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<aside[\\s\\S]*?</aside>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<dl[^>]*class=['\\\"]article-info[^>]*>[\\s\\S]*?</dl>", "", cleaned, flags=re.I)
        cleaned = re.sub(r"<br\\s*/?>", "\\n", cleaned, flags=re.I)
        cleaned = re.sub(r"</?(p|div|li|ul|ol|h[1-6])[^>]*>", "\\n", cleaned, flags=re.I)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        preamble = clean_text_preserving_newlines(cleaned) or None

    return {
        "title": title,
        "preamble": preamble,
        "ingredients": ingredients,
        "method": method,
        "notes": notes,
        "details": details,
    }


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
        data["source_file"] = fname
        base = os.path.splitext(fname)[0]
        outpath = os.path.join(out, base + ".json")
        with open(outpath, "w", encoding="utf-8") as outfd:
            json.dump(data, outfd, ensure_ascii=False, indent=2)
        print(f"Wrote: {outpath}")


if __name__ == "__main__":
    main()