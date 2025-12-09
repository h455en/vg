#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import random
import os
import sys
import argparse

TAILWIND_COLORS = [
    "bg-red-200", "bg-green-200", "bg-blue-200",
    "bg-yellow-200", "bg-pink-200", "bg-purple-200",
    "bg-indigo-200", "bg-teal-200", "bg-orange-200"
]
tag_colors = {}

def get_tag_color(tag):
    if tag not in tag_colors:
        tag_colors[tag] = random.choice(TAILWIND_COLORS)
    return tag_colors[tag]

def load_urls_from_path(path):
    """
    path can be:
      - repo-relative file path (e.g. urls/urls.txt)
      - full raw URL (e.g. https://raw.githubusercontent.com/user/repo/branch/urls.txt)
    Returns list of URLs (strings).
    """
    if path.startswith("http://") or path.startswith("https://"):
        print(f"Downloading URLs from: {path}")
        r = requests.get(path, timeout=20)
        r.raise_for_status()
        content = r.text
    else:
        print(f"Reading URLs from local file: {path}")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    urls = [line.strip() for line in content.splitlines() if line.strip()]
    print(f"Loaded {len(urls)} URL(s).")
    return urls

def extract_text_blocks(url):
    try:
        print(f"Processing: {url}")
        response = requests.get(url, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")

        selectors = [
            {"class": "post-body entry-content"},
            {"class": "post-body"},
            {"id": "main-content"},
        ]
        content_div = None
        for sel in selectors:
            content_div = soup.find("div", sel)
            if content_div:
                break
        if not content_div:
            divs = soup.find_all("div")
            if not divs:
                print("  -> No divs found on page")
                return None, None, url, []
            content_div = max(divs, key=lambda d: len(d.find_all("p")), default=None)

        if not content_div or len(content_div.find_all("p")) == 0:
            print("  -> Could not find main paragraphs")
            return None, None, url, []

        french_paragraphs = []
        arabic_paragraphs = []
        ignore_next = False

        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if not text:
                continue

            # Skip "Partager cet article" and everything following it
            if "Partager cet article" in text:
                ignore_next = True
                continue
            if ignore_next:
                continue

            # Skip "Publié le ... par 3ilm char3i"
            if text.startswith("Publié le") and "3ilm char3i" in text:
                continue

            # classify by Arabic unicode block
            if any('\u0600' <= c <= '\u06FF' for c in text):
                arabic_paragraphs.append(text)
            else:
                french_paragraphs.append(text)

        french_text = "<p>" + "</p><p>".join(french_paragraphs) + "</p>" if french_paragraphs else ""
        arabic_text = "<p>" + "</p><p>".join(arabic_paragraphs) + "</p>" if arabic_paragraphs else ""

        # Tags after "Publié dans"
        tags = []
        published_tag = soup.find(string=lambda t: t and "Publié dans" in t)
        if published_tag:
            parent = published_tag.parent
            if parent:
                for a in parent.find_all("a"):
                    tag_text = a.get_text(strip=True)
                    if tag_text:
                        tags.append(tag_text)

        print("  -> Extraction succeeded")
        return french_text, arabic_text, url, tags

    except Exception as e:
        print(f"  -> Error: {e}")
        return None, None, url, []

def generate_html(cards_html, out_file="cards.html"):
    html_output = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>French & Arabic Cards</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
body {{ background: #f9fafb; font-family: Arial, sans-serif; }}
.arabic {{ text-align: right; }}
.card-border {{ border-width: 2px; border-color: #9CA3AF; }} /* Tailwind slate-400 equivalent */
.tag {{ cursor: pointer; }}
</style>
</head>
<body class="flex flex-col min-h-screen">

<header class="bg-gray-200 py-1 text-center text-sm">Thin Header</header>

<main class="flex-1 container mx-auto p-4">
{cards_html}
</main>

<footer class="bg-gray-200 py-1 text-center text-sm">Thin Footer</footer>

<script>
function copyText(button) {{
    const card = button.closest('.card-inner');
    if(!card) return;
    const text = card.innerText;
    navigator.clipboard.writeText(text).then(() => {{
        const old = button.innerText;
        button.innerText = "✅";
        setTimeout(()=> button.innerText = old, 1000);
    }});
}}

/* Tag filtering: click to toggle filter; multiple tags combine with OR */
let activeTags = new Set();
function toggleTag(tag) {{
    if(activeTags.has(tag)) activeTags.delete(tag);
    else activeTags.add(tag);
    filterCards();
}}

function filterCards() {{
    const cards = document.querySelectorAll('.card-wrap');
    if(activeTags.size === 0) {{
        cards.forEach(c => c.style.display = '');
        return;
    }}
    cards.forEach(card => {{
        const cardTags = Array.from(card.querySelectorAll('.card-tag')).map(t => t.dataset.tag);
        const match = cardTags.some(t => Array.from(activeTags).includes(t));
        card.style.display = match ? '' : 'none';
    }});
}}

</script>

</body>
</html>
"""
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_output)
    print(f"Wrote HTML to: {out_file}")

def main():
    parser = argparse.ArgumentParser(description="Scrape pages and build French/Arabic cards HTML.")
    parser.add_argument("urls_path", help="Path to urls.txt (repo path or full raw URL).")
    parser.add_argument("--output", "-o", default="french_arabic_cards.html", help="Output HTML filename.")
    args = parser.parse_args()

    urls = load_urls_from_path(args.urls_path)
    if not urls:
        print("No URLs to process. Exiting.")
        sys.exit(0)

    cards_html = ""
    for url in urls:
        french_text, arabic_text, original_url, tags = extract_text_blocks(url)

        if not french_text and not arabic_text:
            cards_html += f'''
<div class="my-6 border-2 card-border pb-4 rounded-lg card-wrap">
  <div class="p-4">
    <div class="text-red-600 font-semibold">Text could not be extracted</div>
    <div>Original URL: <a href="{original_url}" target="_blank" rel="noopener">{original_url}</a></div>
  </div>
</div>
'''
            continue

        # tags HTML (clickable, consistent color)
        tag_html = ""
        for tag in tags:
            color = get_tag_color(tag)
            tag_html += f'<span class="inline-block px-2 py-1 mr-1 mb-1 text-sm rounded {color} hover:opacity-80 card-tag tag" data-tag="{tag}" onclick="toggleTag(`{tag}`)">{tag}</span>'

        cards_html += f'''
<div class="my-6 card-wrap border-2 card-border pb-4 rounded-lg">
  <div class="flex gap-4 flex-col md:flex-row card-inner p-4">
    <div class="w-full md:w-1/2 bg-white shadow relative p-4">
      <button onclick="copyText(this)" class="absolute top-2 right-2 text-gray-500 hover:text-gray-800">📋</button>
      <h3 class="text-lg font-semibold mb-2">French</h3>
      {french_text or '<p class="text-gray-400">Not available</p>'}
    </div>
    <div class="w-full md:w-1/2 bg-white shadow relative p-4 arabic" dir="rtl">
      <button onclick="copyText(this)" class="absolute top-2 right-2 text-gray-500 hover:text-gray-800">📋</button>
      <h3 class="text-lg font-semibold mb-2">النص العربي</h3>
      {arabic_text or '<p class="text-gray-400">Not available</p>'}
    </div>
  </div>
  <div class="mt-2 text-sm text-gray-600 p-4">
    Original URL: <a href="{original_url}" target="_blank" rel="noopener">{original_url}</a>
  </div>
  <div class="mt-2 p-4">{tag_html}</div>
</div>
'''

    generate_html(cards_html, out_file=args.output)

if __name__ == "__main__":
    main()
