#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scrape pages, build single HTML with:
- Merriweather for French, Amiri for Arabic
- Tag tabs (underline) for filtering
- Carousel per article (French/Arabic slides)
- Pagination (10 items per page)
Usage:
  python scrape_cards.py <urls_path> --output output/french_arabic_cards.html
urls_path: repo-relative path OR full raw URL to urls.txt
"""

import requests
from bs4 import BeautifulSoup
import random
import os
import sys
import argparse
import pathlib
import json
from urllib.parse import urlparse

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

def extract_title_near_metadata(soup):
    # Find the node containing "Publié le" and look for a preceding heading (h1/h2/h3)
    meta = soup.find(string=lambda t: t and "Publié le" in t)
    if meta:
        # walk up to parent and search previous siblings for title tags
        node = meta.parent
        for _ in range(6):
            # look for immediate previous heading siblings
            prev = node.find_previous_sibling()
            if not prev:
                node = node.parent
                if not node:
                    break
                continue
            if prev.name and prev.name.lower() in ("h1", "h2", "h3"):
                return prev.get_text(strip=True)
            node = prev
        # fallback: find first h1 or h2 in document
    h = soup.find(["h1","h2"])
    return h.get_text(strip=True) if h else ""

def extract_text_blocks(url):
    try:
        print(f"Processing: {url}")
        r = requests.get(url, timeout=15)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, "html.parser")

        title = extract_title_near_metadata(soup)

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
                return None, None, title, url, []
            content_div = max(divs, key=lambda d: len(d.find_all("p")), default=None)

        if not content_div or len(content_div.find_all("p")) == 0:
            print("  -> Could not find main paragraphs")
            return None, None, title, url, []

        french_pars = []
        arabic_pars = []
        ignore_next = False
        for p in content_div.find_all("p"):
            text = p.get_text(strip=True)
            if not text:
                continue

            # Skip everything starting from "Partager cet article"
            if "Partager cet article" in text:
                ignore_next = True
                continue
            if ignore_next:
                continue

            # Skip "Publié le ... par 3ilm char3i"
            if text.startswith("Publié le") and "3ilm char3i" in text:
                continue

            # classify
            if any('\u0600' <= c <= '\u06FF' for c in text):
                arabic_pars.append(text)
            else:
                french_pars.append(text)

        french_text = "<p>" + "</p><p>".join(french_pars) + "</p>" if french_pars else ""
        arabic_text = "<p>" + "</p><p>".join(arabic_pars) + "</p>" if arabic_pars else ""

        # Tags after "Publié dans"
        tags = []
        published_tag = soup.find(string=lambda t: t and "Publié dans" in t)
        if published_tag:
            parent = published_tag.parent
            if parent:
                for a in parent.find_all("a"):
                    tt = a.get_text(strip=True)
                    if tt:
                        tags.append(tt)

        print("  -> Extraction succeeded")
        return french_text or None, arabic_text or None, title, url, tags

    except Exception as e:
        print(f"  -> Error: {e}")
        return None, None, "", url, []

def build_html(articles, out_file):
    # articles: list of dicts {id, title, french, arabic, url, tags}
    unique_tags = []
    for a in articles:
        for t in a["tags"]:
            if t not in unique_tags:
                unique_tags.append(t)
    # assign colors
    for t in unique_tags:
        get_tag_color(t)

    # generate cards markup
    cards = []
    for idx, a in enumerate(articles):
        tags_html = ""
        for t in a["tags"]:
            color = tag_colors.get(t, random.choice(TAILWIND_COLORS))
            tags_html += f'<span class="inline-block px-2 py-1 mr-1 mb-1 text-sm rounded {color} hover:opacity-90 card-tag tag" data-tag="{t}" onclick="toggleTag(`{t}`)">{t}</span>'
        french_block = a["french"] or '<p class="text-gray-400">Not available</p>'
        arabic_block = a["arabic"] or '<p class="text-gray-400">Not available</p>'
        title_html = f'<h2 class="text-xl font-semibold mb-2">{a["title"]}</h2>' if a["title"] else ''
        url_small = f'<div class="mt-2 text-xs text-gray-400 break-words"><a href="{a["url"]}" target="_blank" rel="noopener">{a["url"]}</a></div>'

        card = f'''
<div class="my-6 card-wrap border-2 card-border pb-4 rounded-lg" data-tags='{json.dumps(a["tags"])}' data-article-index="{idx}">
  <div class="p-4">
    {title_html}
    <div class="carousel" data-idx="{idx}">
      <div class="carousel-track relative overflow-hidden">
        <div class="slide w-full p-4 bg-white rounded-lg card-inner" data-slide="0">
          <button onclick="copyText(this)" class="absolute top-3 right-3 text-gray-500 hover:text-gray-800">📋</button>
          <div class="font-merri text-base leading-relaxed">{french_block}</div>
        </div>
        <div class="slide w-full p-4 bg-white rounded-lg card-inner" data-slide="1">
          <button onclick="copyText(this)" class="absolute top-3 right-3 text-gray-500 hover:text-gray-800">📋</button>
          <div class="font-amiri text-base leading-relaxed" dir="rtl">{arabic_block}</div>
        </div>
      </div>
      <div class="mt-2 flex items-center gap-2">
        <button class="btn-prev px-3 py-1 border rounded text-sm" onclick="prevSlide({idx})">Prev</button>
        <button class="btn-next px-3 py-1 border rounded text-sm" onclick="nextSlide({idx})">Next</button>
        <div class="ml-4 text-sm text-gray-600">Slide: <span id="slide-ind-{idx}">1</span>/2</div>
      </div>
    </div>
    {url_small}
    <div class="mt-2">{tags_html}</div>
  </div>
</div>
'''
        cards.append(card)

    # Template HTML (single file)
    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>French & Arabic Cards</title>
<!-- Fonts -->
<link href="https://fonts.googleapis.com/css2?family=Amiri&family=Merriweather:wght@300;400;700&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<style>
body {{ background: #f9fafb; font-family: 'Merriweather', serif; }}
.font-merri {{ font-family: 'Merriweather', serif; }}
.font-amiri {{ font-family: 'Amiri', serif; }}
.arabic {{ text-align: right; }}
.card-border {{ border-width: 2px; border-color: #9CA3AF; }}
.slide {{ display: none; position: relative; }}
.slide.active {{ display: block; }}
.carousel-track {{ min-height: 6rem; }}
.tag-tab {{ cursor: pointer; padding: 0.5rem 0.75rem; }}
.tag-tab.active {{ border-bottom-width: 3px; border-bottom-color: #1D4ED8; }}
/* smaller link text */
a {{ color: inherit; }}
</style>
</head>
<body class="flex flex-col min-h-screen">

<header class="bg-gray-200 py-2 text-center text-sm">Thin Header</header>

<main class="flex-1 container mx-auto p-4">
  <!-- Tag tabs -->
  <div id="tag-tabs" class="mb-4 flex gap-2 flex-wrap border-b pb-2">
    <div class="tag-tab text-sm font-medium mr-2 underline-none" onclick="clearTags()">All</div>
'''
    # add tabs
    for t in unique_tags:
        html += f'<div class="tag-tab text-sm font-medium" data-tag-name="{t}" onclick="selectTab(`{t}`)">{t}</div>\n'

    html += '''
  </div>

  <!-- Pagination controls (top) -->
  <div class="mb-4 flex justify-between items-center">
    <div>
      <button onclick="prevPage()" class="px-3 py-1 border rounded text-sm">Prev</button>
      <button onclick="nextPage()" class="px-3 py-1 border rounded text-sm ml-2">Next</button>
    </div>
    <div class="text-sm text-gray-600">Page <span id="page-num">1</span> / <span id="page-total">1</span></div>
  </div>

  <!-- Cards container -->
  <div id="cards-container">
    {''.join(cards)}
  </div>

  <!-- Pagination controls (bottom) -->
  <div class="mt-6 flex justify-between items-center">
    <div>
      <button onclick="prevPage()" class="px-3 py-1 border rounded text-sm">Prev</button>
      <button onclick="nextPage()" class="px-3 py-1 border rounded text-sm ml-2">Next</button>
    </div>
    <div class="text-sm text-gray-600">Page <span id="page-num-2">1</span> / <span id="page-total-2">1</span></div>
  </div>

</main>

<footer class="bg-gray-200 py-2 text-center text-sm">Thin Footer</footer>

<script>
// Pagination config
const ITEMS_PER_PAGE = 10;
const cards = Array.from(document.querySelectorAll('.card-wrap'));
let currentPage = 1;
let filteredIndexes = null; // null => no filter

function initPagination() {{
  document.getElementById('page-total').innerText = Math.max(1, Math.ceil(cards.length / ITEMS_PER_PAGE));
  document.getElementById('page-total-2').innerText = document.getElementById('page-total').innerText;
  showPage(1);
}}

// show a page considering filtering
function showPage(page) {{
  const list = filteredIndexes ? filteredIndexes : cards.map((c,i)=>i);
  const total = Math.max(1, Math.ceil(list.length / ITEMS_PER_PAGE));
  if(page < 1) page = 1;
  if(page > total) page = total;
  currentPage = page;
  document.getElementById('page-num').innerText = page;
  document.getElementById('page-num-2').innerText = page;
  document.getElementById('page-total').innerText = total;
  document.getElementById('page-total-2').innerText = total;

  // hide all
  cards.forEach(c => c.style.display = 'none');
  // compute slice
  const start = (page-1) * ITEMS_PER_PAGE;
  const pageItems = list.slice(start, start + ITEMS_PER_PAGE);
  pageItems.forEach(i => cards[i].style.display = '');

  // reinitialize slides for visible items
  pageItems.forEach(i => initCarousel(parseInt(cards[i].dataset.articleIndex)));
}}

function prevPage(){ showPage(currentPage-1); }
function nextPage(){ showPage(currentPage+1); }

// Carousel logic per article
function initCarousel(articleIdx) {{
  const wrapper = document.querySelector(`.carousel[data-idx="${articleIdx}"]`);
  if(!wrapper) return;
  const slides = wrapper.querySelectorAll('.slide');
  slides.forEach(s => s.classList.remove('active'));
  slides[0].classList.add('active');
  document.getElementById(`slide-ind-${articleIdx}`).innerText = 1;
}}

function nextSlide(articleIdx){ changeSlide(articleIdx, 1); }
function prevSlide(articleIdx){ changeSlide(articleIdx, -1); }

function changeSlide(articleIdx, delta) {{
  const wrapper = document.querySelector(`.carousel[data-idx="${articleIdx}"]`);
  if(!wrapper) return;
  const slides = wrapper.querySelectorAll('.slide');
  let active = -1;
  slides.forEach((s,i)=> { if(s.classList.contains('active')) active = i; });
  let next = (active + delta + slides.length) % slides.length;
  slides[active].classList.remove('active');
  slides[next].classList.add('active');
  document.getElementById(`slide-ind-${articleIdx}`).innerText = next+1;
}}

// copy text
function copyText(button){ const card = button.closest('.card-inner'); if(!card) return; const txt = card.innerText; navigator.clipboard.writeText(txt).then(()=>{ const old = button.innerText; button.innerText='✅'; setTimeout(()=> button.innerText = old, 1000); }); }

// Tag filtering / tabs
let activeTags = new Set();
function toggleTag(tag){ if(activeTags.has(tag)) activeTags.delete(tag); else activeTags.add(tag); applyFilter(); updateTagTabs(); }
function selectTab(tag){ activeTags = new Set([tag]); applyFilter(); updateTagTabs(); }
function clearTags(){ activeTags = new Set(); applyFilter(); updateTagTabs(); }

function applyFilter(){ 
  if(activeTags.size===0){ filteredIndexes = null; showPage(1); return; }
  const idxs = [];
  cards.forEach((c,i)=>{
    const data = JSON.parse(c.dataset.tags || '[]');
    const match = data.some(t => Array.from(activeTags).includes(t));
    if(match) idxs.push(i);
  });
  filteredIndexes = idxs;
  showPage(1);
}

function updateTagTabs(){ 
  document.querySelectorAll('#tag-tabs .tag-tab').forEach(tab=>{
    const t = tab.dataset.tagName;
    if(!t) return;
    tab.classList.remove('active');
    if(activeTags.has(t)) tab.classList.add('active');
  });
}

// init
document.addEventListener('DOMContentLoaded', function(){ 
  // convert slide container elements into proper slide divs
  document.querySelectorAll('.carousel .carousel-track').forEach(track=>{
    const slides = track.querySelectorAll('.slide');
    slides.forEach((s,i)=> s.classList.toggle('active', i===0));
  });
  // init all carousels (only visible ones will be reinitialized by showPage)
  initPagination();
});
</script>

</body>
</html>
'''
    # write
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote HTML to: {out_file}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("urls_path", help="Repo-relative path or raw URL to urls.txt")
    parser.add_argument("--output", "-o", default="output/french_arabic_cards.html", help="Output HTML file")
    args = parser.parse_args()

    urls = load_urls_from_path(args.urls_path)
    if not urls:
        print("No URLs. Exiting.")
        sys.exit(0)

    articles = []
    for i, u in enumerate(urls):
        french, arabic, title, url, tags = extract_text_blocks(u)
        articles.append({
            "id": i,
            "title": title or "",
            "french": french,
            "arabic": arabic,
            "url": url,
            "tags": tags or []
        })

    build_html(articles, args.output)

if __name__ == "__main__":
    main()
