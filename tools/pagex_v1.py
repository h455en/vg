import requests
from bs4 import BeautifulSoup
import random
import html
from collections import defaultdict
import re
import argparse
from pathlib import Path
import sys

# --- Configuration ---
# Bootstrap Color Classes for Tags
COLORS = ["bg-primary", "bg-success", "bg-info", "bg-warning", "bg-danger", "bg-secondary", "bg-dark"]
tag_colors = {}

def get_tag_color(tag):
    """Assigns a consistent color class to each unique tag."""
    if tag not in tag_colors:
        tag_colors[tag] = random.choice(COLORS)
    return tag_colors[tag]

def extract_article(url):
    """
    Scrapes the given URL to extract the article title, French text, Arabic text, and tags.
    Applies filtering for unwanted headers/footers.
    """
    try:
        print(f"Processing: {url}")
        r = requests.get(url, timeout=15)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, "html.parser")

        # 1. Find the main content div
        selectors = [
            {"class_": "post-body entry-content"},
            {"class_": "post-body"},
            {"id": "main-content"}
        ]
        content_div = None
        for sel in selectors:
            content_div = soup.find("div", **sel)
            if content_div: break
        
        if not content_div:
            divs = soup.find_all("div")
            content_div = max(divs, key=lambda d: len(d.find_all("p")), default=None)
        
        if not content_div:
            return {"url": url, "title": "Error", "french": "<p>Text could not be extracted</p>", "arabic": "<p>Text could not be extracted</p>", "tags": []}

        # 2. Extract Title (Logic simplified for robust extraction)
        title = ""
        h_tags = content_div.find_all(re.compile(r'^h[1-4]$'))
        if h_tags:
            title = h_tags[0].get_text(strip=True)
        
        if not title:
            # Fallback to the first non-empty text before known header content
            for elem in content_div.find_all(text=True):
                if "Publié le" in elem or "3ilm char3i" in elem: break
                if elem.strip() and len(elem.strip()) > 10: 
                    title = elem.strip()
                    break

        # 3. Extract French and Arabic content and apply filters
        french, arabic = [], []
        ignore_next = False
        arabic_regex = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
        
        # Keywords for filtering unwanted content
        UNWANTED_HEADINGS = ["La science légiférée - العلم الشرعي", "3ilm char3i", "Publié par", "Partager cet article"]
        FRENCH_FOOTER_KEYWORDS = ["Catégories", "Newsletter", "Abonnez-vous", "Contre le terrorisme", "copié sans aucune modification"]

        for p in content_div.find_all("p"):
            t = p.get_text(strip=True)
            if not t: continue
            
            # Filter 1: Stop processing after reaching the known footer keywords
            if any(keyword in t for keyword in FRENCH_FOOTER_KEYWORDS): 
                break 
            
            # Filter 2: Remove known unwanted header/publishing info (Skip current paragraph)
            if t.startswith("Publié le") and "3ilm char3i" in t: continue
            if any(ut in t for ut in UNWANTED_HEADINGS): continue

            if arabic_regex.search(t):
                arabic.append(html.escape(t))
            else:
                french.append(html.escape(t))

        french_html = "<p>" + "</p><p>".join(french) + "</p>" if french else "<p>Not available</p>"
        arabic_html = "<p>" + "</p><p>".join(arabic) + "</p>" if arabic else "<p>Not available</p>"

        # 4. Extract Tags - Only take the French part 
        tags = []
        published_tag = soup.find(string=lambda t: t and "Publié dans" in t)
        if published_tag:
            parent = published_tag.parent
            for a in parent.find_all("a"):
                tag_text = a.get_text(strip=True)
                if tag_text:
                    # Extract only the French part before ' - '
                    cleaned_tag = tag_text.split(' - ')[0].strip()
                    if cleaned_tag:
                        tags.append(cleaned_tag)

        return {"url": url, "title": title or "No title", "french": french_html, "arabic": arabic_html, "tags": tags}
    except Exception as e:
        print(f"Error processing {url}: {e}", file=sys.stderr)
        return {"url": url, "title": "Error", "french": "<p>Text could not be extracted</p>", "arabic": "<p>Text could not be extracted</p>", "tags": []}

def generate_html_content(tags_html, carousel_items):
    """Generates the full HTML content string using .format() and double braces."""
    return """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Articles Carousel</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Literata:wght@400;700&family=Amiri:wght@400;700&display=swap" rel="stylesheet">
    <style>
        /* General Styles */
        body {{font-family: Arial, sans-serif;}}
        .card-rounded {{border-radius: 1rem;}}
        
        /* Font Styles (Literata for French, Amiri for Arabic) */
        .french-text {{ 
            font-family: 'Literata', serif; 
            font-size: 1rem;
            line-height: 1.6;
            max-height: 50vh;
        }}
        .arabic-text {{ 
            font-family: 'Amiri', serif; 
            direction: rtl; 
            text-align: right; 
            font-size: 1.1rem;
            line-height: 1.8;
            max-height: 50vh;
        }}
        
        /* Carousel/Tag Styles */
        .tag-tab {{ 
            cursor: pointer;
            text-decoration: underline; 
            transition: opacity 0.2s;
        }}
        /* Style for the active/selected tab */
        .tag-tab.active-filter {{
            font-weight: bold;
            box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.5), 0 0 0 4px #000; 
            opacity: 1;
        }}
        .carousel-item {{ min-height: 80vh; }}
        
        /* Pagination Styling */
        .pagination-container {{ padding: 1rem 0; }}
        
        .copy-btn {{ border: none; }}
        .text-truncate {{ overflow: hidden; white-space: nowrap; }}
    </style>
</head>
<body>
    <header class="bg-light py-2 border-bottom shadow-sm sticky-top">
        <div class="container d-flex flex-wrap align-items-center">
            <strong class="me-3 text-secondary">Tags:</strong>
            <div id="tag-container" class="d-flex flex-wrap">
                {tags_html}
            </div>
        </div>
    </header>

    <div id="articleCarousel" class="carousel slide" data-bs-interval="false" data-bs-keyboard="true">
        
        <div class="carousel-inner">
            {carousel_items}
        </div>
        
        <button class="carousel-control-prev" type="button" data-bs-target="#articleCarousel" data-bs-slide="prev">
            <span class="carousel-control-prev-icon" aria-hidden="true"></span>
            <span class="visually-hidden">Previous</span>
        </button>
        <button class="carousel-control-next" type="button" data-bs-target="#articleCarousel" data-bs-slide="next">
            <span class="carousel-control-next-icon" aria-hidden="true"></span>
            <span class="visually-hidden">Next</span>
        </button>
    </div>

    <div class="container pagination-container">
        <nav aria-label="Article navigation">
            <ul id="article-pagination" class="pagination justify-content-center">
                </ul>
        </nav>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const articleCarousel = document.getElementById('articleCarousel');
        const paginationUl = document.getElementById('article-pagination');
        // Use a safe check before initialization, in case no articles were scraped
        const carouselItems = articleCarousel ? articleCarousel.querySelectorAll('.carousel-item') : [];
        let carouselInstance;
        if (articleCarousel && carouselItems.length > 0) {{
             carouselInstance = new bootstrap.Carousel(articleCarousel, {{ interval: false, keyboard: true }});
        }}
        
        // --- Core Pagination Logic ---
        function renderPagination() {{
            const visibleItems = Array.from(carouselItems).filter(item => item.style.display !== 'none');
            const visibleCount = visibleItems.length;
            const activeVisibleIndex = visibleItems.findIndex(item => item.classList.contains('active'));

            if (visibleCount === 0 || !carouselInstance) {{
                paginationUl.innerHTML = '';
                return;
            }}

            paginationUl.innerHTML = '';

            function getVisibleSlideIndex(step) {{
                const targetIndex = activeVisibleIndex + step;
                if (targetIndex >= 0 && targetIndex < visibleCount) {{
                    return Array.from(carouselItems).indexOf(visibleItems[targetIndex]);
                }}
                return -1;
            }}

            // 1. Previous Button
            const prevLi = document.createElement('li');
            const prevTargetIndex = getVisibleSlideIndex(-1);
            // JS Template Literal for CSS class with conditional
            prevLi.className = `page-item ${{activeVisibleIndex === 0 ? 'disabled' : ''}}`; 
            prevLi.innerHTML = `<a class="page-link" href="#" aria-label="Previous">Previous</a>`;
            prevLi.addEventListener('click', (e) => {{
                e.preventDefault();
                if (prevTargetIndex !== -1) {{
                    carouselInstance.to(prevTargetIndex);
                }}
            }});
            paginationUl.appendChild(prevLi);

            // 2. Numbered Pages (1, 2, 3...)
            visibleItems.forEach((item, visibleIndex) => {{
                const pageLi = document.createElement('li');
                // JS Template Literal for CSS class with conditional
                pageLi.className = `page-item ${{visibleIndex === activeVisibleIndex ? 'active' : ''}}`;
                const globalIndex = Array.from(carouselItems).indexOf(item);

                // JS Template Literal for injected number
                pageLi.innerHTML = `<a class="page-link" href="#">${{visibleIndex + 1}}</a>`;
                pageLi.addEventListener('click', (e) => {{
                    e.preventDefault();
                    carouselInstance.to(globalIndex);
                }});
                paginationUl.appendChild(pageLi);
            }});

            // 3. Next Button
            const nextLi = document.createElement('li');
            const nextTargetIndex = getVisibleSlideIndex(1);
            // JS Template Literal for CSS class with conditional
            nextLi.className = `page-item ${{activeVisibleIndex === visibleCount - 1 ? 'disabled' : ''}}`;
            nextLi.innerHTML = `<a class="page-link" href="#" aria-label="Next">Next</a>`;
            nextLi.addEventListener('click', (e) => {{
                e.preventDefault();
                if (nextTargetIndex !== -1) {{
                    carouselInstance.to(nextTargetIndex);
                }}
            }});
            paginationUl.appendChild(nextLi);
        }}

        // --- Event Listener to Sync Pagination and Carousel ---
        if (articleCarousel) {{
            articleCarousel.addEventListener('slid.bs.carousel', function (e) {{
                renderPagination(); 
            }});
        }}

        // --- Initial Load ---
        document.addEventListener('DOMContentLoaded', () => {{
            renderPagination(); 
        }});


        // --- Other Utility Functions (Copy and Tag Filtering) ---
        function copyText(id){{
            const el = document.getElementById(id);
            const text = el.innerText;
            navigator.clipboard.writeText(text).then(() => {{
                const copyButton = document.querySelector(`#${{id}}`).closest('.card').querySelector('.copy-btn');
                const originalContent = copyButton.innerHTML;
                copyButton.innerHTML = '<span class="text-success">Copié!</span>';
                setTimeout(() => {{ copyButton.innerHTML = originalContent; }}, 1500);
            }}).catch(err => {{
                console.error('Could not copy text: ', err);
                alert("Échec de la copie du texte.");
            }});
        }}
        window.copyText = copyText;

        // Tag Filtering Logic (Mutually Exclusive Tabs)
        document.querySelectorAll('.tag-tab').forEach(tag => {{
            tag.addEventListener('click', function() {{
                const selectedTag = this.getAttribute('data-tag');
                
                // 1. Mutually Exclusive Tab Activation
                document.querySelectorAll('.tag-tab').forEach(t => t.classList.remove('active-filter'));
                this.classList.add('active-filter');
                const isAll = (selectedTag === 'all');

                // 2. Filter Articles and Find First Match
                let firstVisibleIndex = -1;
                carouselItems.forEach((item, index) => {{
                    const itemTags = item.getAttribute('data-tags');
                    const tagsArray = itemTags ? itemTags.split(',') : [];
                    
                    const matchesFilter = isAll || tagsArray.includes(selectedTag);

                    if (matchesFilter) {{
                        item.style.display = 'block';
                        if (firstVisibleIndex === -1) {{
                            firstVisibleIndex = index;
                        }}
                    }} else {{
                        item.style.display = 'none'; // Hide article
                    }}
                }});
                
                // 3. Update Carousel and Pagination
                carouselItems.forEach(item => item.classList.remove('active'));
                
                if (firstVisibleIndex !== -1) {{
                    const firstVisibleItem = carouselItems[firstVisibleIndex];
                    firstVisibleItem.classList.add('active');
                    if (carouselInstance) {{
                        carouselInstance.to(firstVisibleIndex); 
                    }}
                }}
                renderPagination(); 
            }});
        }});
    </script>
</body>
</html>
""".format(
        tags_html=tags_html, 
        carousel_items=carousel_items
    )

def main():
    parser = argparse.ArgumentParser(description="Scrape URLs from a text file and generate a Bootstrap carousel HTML page.")
    # The input file will be relative to where the script is run, e.g., 'data/links_abab.txt'
    parser.add_argument("input_file", type=str, help="Path to the input text file containing URLs (e.g., data/links_abab.txt).")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    
    # 1. Determine Output Path
    # Input: data/links_abab.txt
    # Output Path: data/abab.html
    
    input_filename = input_path.name
    
    # Strip the 'links_' prefix if it exists
    if input_filename.startswith('links_'):
        base_name_without_prefix = input_filename[len('links_'):]
    else:
        # Fallback if the naming convention is not strictly followed
        base_name_without_prefix = input_filename
    
    # Change the extension to .html
    output_filename = Path(base_name_without_prefix).with_suffix('.html').name
    
    # Ensure output goes to the same directory as the input file (e.g., 'data' folder)
    output_path = input_path.parent / output_filename
    
    # 2. Read URLs
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: Input file '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    if not urls:
        print(f"No URLs found in '{input_path}'. HTML generation skipped.", file=sys.stderr)
        sys.exit(0)

    # 3. Extract Articles
    articles = [extract_article(u) for u in urls]

    # 4. Prepare HTML parts
    tag_counts = defaultdict(int)
    for a in articles:
        for t in a['tags']:
            tag_counts[t] += 1

    all_tags = sorted(tag_counts.keys())

    # Tags HTML (with 'All' tag)
    total_articles_count = len(articles)
    tags_html = f'<span class="tag-tab active-filter bg-secondary px-2 py-1 text-white rounded-pill me-2 mb-1" data-tag="all">All ({total_articles_count})</span>'

    for t in all_tags:
        color = get_tag_color(t)
        count = tag_counts[t]
        tags_html += f'<span class="tag-tab {color} px-2 py-1 text-white rounded-pill me-2 mb-1" data-tag="{t}">{t} ({count})</span>'

    # Carousel Items HTML
    carousel_items = ""
    for i, a in enumerate(articles):
        active = "active" if i == 0 else ""
        article_tags_html = ""
        for t in a['tags']:
            color = get_tag_color(t)
            article_tags_html += f'<span class="badge {color} text-white me-1 rounded-pill">{t}</span>'

        carousel_items += f"""
<div class="carousel-item {active}" data-article-index="{i}" data-tags="{','.join(a['tags'])}">
    <div class="container py-4">
        <h3 class="mb-3">{a['title']}</h3>
        
        <div class="row g-4">
            <div class="col-md-6">
                <div class="card card-rounded p-3 h-100 shadow-lg">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h5 class="card-title text-primary mb-0">Français</h5>
                        <button class="btn btn-sm btn-outline-secondary copy-btn" onclick="copyText('french-{i}')" title="Copier le contenu français">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-files" viewBox="0 0 16 16">
                                <path d="M13 0H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2m-3 6V2h3a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h3zm-3-3a1 1 0 0 1 1-1H7a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"/>
                            </svg>
                        </button>
                    </div>
                    <div id="french-{i}" class="french-text overflow-auto">{a['french']}</div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card card-rounded p-3 h-100 shadow-lg">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h5 class="card-title text-success mb-0">العربية</h5>
                        <button class="btn btn-sm btn-outline-secondary copy-btn" onclick="copyText('arabic-{i}')" title="Copier le contenu arabe">
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-files" viewBox="0 0 16 16">
                                <path d="M13 0H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2m-3 6V2h3a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h3zm-3-3a1 1 0 0 1 1-1H7a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"/>
                            </svg>
                        </button>
                    </div>
                    <div id="arabic-{i}" class="arabic-text overflow-auto">{a['arabic']}</div>
                </div>
            </div>
        </div>
        
        <div class="mt-3 d-flex justify-content-between align-items-center">
            <small class="text-muted me-3">Tags: {article_tags_html}</small>
            <small class="text-muted text-end">Original URL: <a href="{a['url']}" target="_blank" class="text-decoration-none text-truncate d-inline-block" style="max-width: 300px;">{a['url']}</a></small>
        </div>
    </div>
</div>
"""
    # 5. Generate and Write HTML
    html_content = generate_html_content(tags_html, carousel_items)
    
    try:
        # Create the 'data' directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Success! HTML generated and saved to: {output_path}")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()