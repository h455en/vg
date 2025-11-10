"""

pour chaque lundi changer la date pour le prochain weekend
archiver le weekend passé
Scrapy
python scra.py
open EventsViewer.html
select best manifs
Paste to route planner, generate routes
generate pdfs
clean pdfs (remove duplicates)
merge pdfs
put in ondrive
calculate route
"""

import re
import json
from datetime import datetime, timedelta
import os, html
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


# -------------------------------------
# //////////////////  CONFIG
# -------------------------------------
# vérifier la meteo
# vérifier si la manif est annulée
# marché le samedi si pluie ou vg pas trop important

# BACKLOG in https://dev.azure.com/arctik/VG

# https://www.spam.fr/evenements.php?type=Vide-grenier
# https://www.bidf.fr/nos-vide-greniers
# https://www.paris.fr/pages/brocantes-et-vide-greniers-chiner-a-paris-18730
# https://www.ohvl-international.com/type_evenement/vide-greniers/
# https://www.francebrocante.fr/
# https://brocabrac.fr/ile-de-france/vide-grenier/
# https://www.info-brocantes.com/reg-ile-de-france.html
# https://www.mybrocante.fr/agenda/list/ile-de-france/hauts-de-seine

#===========CONFIG==========================================
year="2025"
min_date = f"{year}-11-10"
max_date = f"{year}-12-31"
MASTER_URL = f"https://vide-greniers.org/evenements/Ile-de-France?min={min_date}&max={max_date}&tags%5B0%5D=1"
#MASTER_URL = f"https://vide-greniers.org/evenements/Paris-75?distance=50&min=2025-11-10&max=2025-12-31&tags%5B0%5D=1"
OUTPUT_DIR = r"C:\Users\hdoghmen\OneDrive\VNTD_LBC_25\0.Warehouse\1.Route"  # change to desired folder
OUTPUT_PREFIX = "vg_manifs__"
HTML_OUTPUT = "vg.html"
#=================================================================

FALLBACK_DATE = "01.01.0001"
# French weekday and month names for formatting
WEEKDAY_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTH_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}

# -----------------------
# Helpers: date parsing & formatting
# ------------------------
def format_date_fr(dt: datetime) -> str:
    if not isinstance(dt, datetime):
        return FALLBACK_DATE
    weekday = WEEKDAY_FR[dt.weekday()]
    month = MONTH_FR[dt.month]
    return f"{weekday} {dt.day} {month} {dt.year}" #Return date in 'Dimanche 5 Octobre 2025' format

def parse_iso_date_str(s: str):
    if not s:
        return None
    # Attempt to find YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d)
        except:
            return None    
    m2 = re.search(r"(\d{4})/(\d{2})/(\d{2})", s) # Try basic YYYY/MM/DD
    if m2:
        y, mo, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            return datetime(y, mo, d)
        except:
            return None
    return None

def parse_fr_date_string(s: str):
    if not s or s == FALLBACK_DATE:
        return None
    pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})"
    m = re.search(pattern, s, flags=re.IGNORECASE)
    if not m:
        return None
    day = int(m.group(2))
    month_name = m.group(3).capitalize()
    year = int(m.group(4))
    # map month_name to number
    month_num = None
    for num, name in MONTH_FR.items():
        if name.lower() == month_name.lower():
            month_num = num
            break
    if not month_num:
        return None
    try:
        return datetime(year, month_num, day)
    except:
        return None

# ----------------------------
# Technique A: time tag
# ----------------------------
def date_from_time_tag(soup):
    time_tag = soup.find("time")
    if not time_tag:
        return FALLBACK_DATE
    text = time_tag.get_text(" ", strip=True)
    # If text contains a French date, return the matched part
    fr_pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
    m = re.search(fr_pattern, text, flags=re.IGNORECASE)
    if m:
        return m.group(0).strip()
    # try datetime attribute or text iso
    dt_attr = time_tag.get("datetime") or text
    dt = parse_iso_date_str(dt_attr)
    if dt:
        return format_date_fr(dt)
    return FALLBACK_DATE

# ----------------------------
# Technique B: JSON-LD or page-wide regex
# ----------------------------
def extract_startdate_from_jsonld(soup):
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            text = s.string
            if not text:
                continue
            data = json.loads(text)
        except Exception:
            # sometimes script contains multiple JSON objects or trailing commas; try to fix loosely
            try:
                cleaned = re.sub(r"(\n|\r)", "", s.string or "")
                data = json.loads(cleaned)
            except Exception:
                continue

        # recursive search for startDate keys
        def find_startdate(obj):
            if isinstance(obj, dict):
                if "startDate" in obj and obj["startDate"]:
                    return obj["startDate"]
                for k, v in obj.items():
                    res = find_startdate(v)
                    if res:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = find_startdate(item)
                    if res:
                        return res
            return None

        sd = find_startdate(data)
        if sd:
            dt = parse_iso_date_str(sd)
            if dt:
                return format_date_fr(dt)
            # sometimes startDate may already be human readable
            if isinstance(sd, str):
                m = re.search(r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}", sd, flags=re.IGNORECASE)
                if m:
                    return m.group(0).strip()
    return FALLBACK_DATE

def extract_date_via_regex_whole_page(soup):
    text = soup.get_text(" ", strip=True)
    pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return FALLBACK_DATE

# ----------------------------
# Master extract_date using two techniques
# ----------------------------
def extract_date(soup):
    # Technique A
    date_a = date_from_time_tag(soup)
    if date_a and date_a != FALLBACK_DATE:
        return date_a

    # Technique B (JSON-LD)
    date_b = extract_startdate_from_jsonld(soup)
    if date_b and date_b != FALLBACK_DATE:
        return date_b

    # Technique B fallback: whole page regex
    date_b2 = extract_date_via_regex_whole_page(soup)
    if date_b2 and date_b2 != FALLBACK_DATE:
        return date_b2

    return FALLBACK_DATE

# ----------------------------
# Other extractors (title, exposants, address)
# ----------------------------
def extract_title(soup):  
    title = None
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(" ", strip=True)
    if not title:
        h2 = soup.find("h2")
        if h2 and h2.get_text(strip=True):
            title = h2.get_text(" ", strip=True)
    return title or "NA"

def extract_exposants(soup):
    txt = soup.get_text(" ", strip=True)
    m = re.search(r"(\d+)\s*exposants", txt, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except:
            return -1
    return -1

#--------------------------------------

def _normalize_paris_zip(city_part: str) -> str:
    """
    Converts 'Paris XX' (e.g., 'Paris 16') into '750XX Paris'.
    If the part already contains a 750XX zip code, it is returned as is.
    """
    city_part_stripped = city_part.strip()
    
    # 1. Check if it's already a good format (e.g., '75015 Paris' or '85, 75015 Paris')
    if re.search(r"750\d{2}\s*Paris", city_part_stripped, re.IGNORECASE):       
        return city_part_stripped
        
    # 2. Check for the old 'Paris XX' format
    match = re.search(r"Paris\s*(\d+)", city_part_stripped, re.IGNORECASE)
    if match:
        district_num = int(match.group(1))
        if 1 <= district_num <= 20:
            # Format the zip code: 75001, 75002, ..., 75010, ..., 75020
            zip_code = f"750{district_num:02d}"
            return f"{zip_code} Paris"
            
    return city_part_stripped

def clean_address_text(raw_text: str) -> str:
    if not raw_text:
        return "NA"
        
    # 1. Context Slicing (Original logic)
    if "Accès" in raw_text and "Itinéraire" in raw_text:
        try:
            raw_text = raw_text.split("Accès", 1)[1].split("Itinéraire", 1)[0].strip()
        except:
            pass
            
    # 2. Normalize and Split
    raw_text = raw_text.replace(" ,", ",").strip()
    parts = [p.strip() for p in raw_text.split(",") if p.strip()]
    
    if parts:
        last_part_normalized = _normalize_paris_zip(parts[-1])
        
        if last_part_normalized != parts[-1]:
            parts[-1] = last_part_normalized
        
        if len(parts) >= 2:
            second_to_last = parts[-2]
           
            if re.search(r"750\d{2}\s*Paris", parts[-1], re.IGNORECASE):
                 # Check if the second-to-last part is just a redundant city name
                if second_to_last.strip().lower() == "paris":
                    parts.pop(-2) # Remove the redundant 'Paris' part
    
    raw_text = ", ".join(parts)
    
    parts = [p.strip() for p in raw_text.split(",") if p.strip()]
    
    seen = set()
    dedup = []
    for p in parts:
        if p not in seen:
            # An extra check to avoid adding a street name AND a zip/city if they are identical
            if not (len(dedup) > 0 and dedup[-1] == p and re.search(r"750\d{2}", p)):
                dedup.append(p)
            seen.add(p)
            
    return ", ".join(dedup) if dedup else (raw_text or "NA")


def extract_address(soup):
    section = soup.find("section", attrs={"x-ref": "locationSection"})
    if section:
        return clean_address_text(section.get_text(" ", strip=True))
        
    # fallback: try to find element with 'Adresse' word around it
    node = soup.find(string=re.compile(r"Adresse", flags=re.IGNORECASE))
    if node:
        parent = node.find_parent()
        if parent:
            return clean_address_text(parent.get_text(" ", strip=True))
            
    return "NA"

def extract_ville_from_address(address: str):
    if not address or address == "NA":
        return "NA"
        
    parts = [p.strip() for p in address.split(",") if p.strip()]
    
    if parts:
        # The last part should be the city and zip (e.g., '75002 Paris')
        return parts[-1] 
        
    return "NA"
# ----------------------------
# Playwright page fetcher
# ----------------------------
def fetch_page_content(url, wait_ms=1000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        # small wait for Alpine.js to finish
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
        return html
# ----------------------------
# Display helper
# ----------------------------
def display_manif(manif: dict):
    # Print properties one per line, no labels
    # Order: Title, Exposants, Adresse, Ville, ManifDate, ManifLink
    print(manif.get("Titre", "NA"))
    print(manif.get("Exposants", -1))
    print(manif.get("Adresse", "NA"))
    print(manif.get("Ville", "NA"))
    print(manif.get("ManifDate", FALLBACK_DATE))
    print(manif.get("ManifLink", "NA"))
    print("-" * 50)
# ----------------------------
# Grouping and saving
# ----------------------------
def group_and_sort(manifs: list):
    grouped = defaultdict(list)
    for m in manifs:
        grouped[m["ManifDate"]].append(m)

    # sort groups by date (most recent first)
    def key_for_date_str(ds: str):
        dt = parse_fr_date_string(ds)
        if dt:
            return dt
        # try parse ISO
        iso_dt = parse_iso_date_str(ds)
        if iso_dt:
            return iso_dt
        return datetime.min

    sorted_dates = sorted(grouped.keys(), key=key_for_date_str, reverse=True)
    grouped_sorted = {date: grouped[date] for date in sorted_dates}
    # also sort items inside each group by Exposants descending
    for date in grouped_sorted:
        grouped_sorted[date] = sorted(grouped_sorted[date], key=lambda x: x.get("Exposants", -1), reverse=True)
    return grouped_sorted

def save_to_json(grouped: dict, output_dir=OUTPUT_DIR, prefix=OUTPUT_PREFIX):
    now = datetime.now()
    # build French-like short month name for filename (capitalize first 3 or full? we use abbreviated month with first letter capital)
    month_name = MONTH_FR[now.month]
    date_str = now.strftime("%d") + "_" + month_name + "_" + now.strftime("%Y_%H%M")
    filename = f"{prefix}_{date_str}.json"
    filepath = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)
    print(f"Saved {filepath}")
    return filepath

# ----------------------------
# HTML generator (Bootstrap)
# ----------------------------

import os
import html
from datetime import datetime, timedelta

#=======================
def generate_html(grouped: dict, output_file="manifs.html"):
    # Find next Saturday or Sunday
    today = datetime.today()
    next_weekend = None
    for i in range(7):
        candidate = today + timedelta(days=i)
        if candidate.weekday() in [5, 6]:  # Saturday=5, Sunday=6
            next_weekend = candidate.strftime("%A %d %B %Y")
            break

    parts = []
    parts.append('<!doctype html>')
    parts.append('<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">')
    parts.append('<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>')
    parts.append('<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />')
    parts.append('<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>')
    parts.append('<title>Manifs</title>')
    parts.append('''
    <style>
        body { font-size: 0.9rem; }
        .list-group-item { font-size: 0.85rem; }
        h5 { font-size: 1rem; }
        #map { height: 600px; }
        .exp-red { color: red; font-weight: bold; }
        .copy-icon { cursor: pointer; margin-left: 8px; color: #0d6efd; }
    </style>
    </head><body><div class="container my-4">''')

    parts.append('<h3>📍 Vg</h3>')

    # Tabs
    parts.append('''
    <ul class="nav nav-tabs" id="viewTabs" role="tablist">
      <li class="nav-item" role="presentation">
        <button class="nav-link active" id="table-tab" data-bs-toggle="tab" data-bs-target="#tableView" type="button" role="tab">Table</button>
      </li>
      <li class="nav-item" role="presentation">
        <button class="nav-link" id="map-tab" data-bs-toggle="tab" data-bs-target="#mapView" type="button" role="tab">Carte</button>
      </li>
    </ul>
    <div class="tab-content mt-3">
      <div class="tab-pane fade show active" id="tableView" role="tabpanel">
    ''')

    # Table view
    for i, (date, events) in enumerate(grouped.items()):
        collapse_id = f"collapse_{i}"
        expanded = "show" if date == next_weekend else ""
        parts.append(f'''
        <section class="mt-4">
          <h5>
            <a class="btn btn-link" data-bs-toggle="collapse" href="#{collapse_id}" role="button">
              {date} ({len(events)} events)
            </a>
          </h5>
          <div id="{collapse_id}" class="collapse {expanded}">
            <div class="list-group">
        ''')

        for e in events:
            title_words = (e.get("Titre") or "").split()[:5]
            title_display = " ".join(title_words)
            exp_value = e.get("Exposants", "")
            exp_display = f'<span class="exp-red">{exp_value}</span>' if isinstance(exp_value, int) and exp_value >= 400 else str(exp_value)
            address = html.escape(e.get("Adresse", ""))
            link = e.get("ManifLink", "#")

            html_item = f'''
            <div class="list-group-item">
                <h6><a href="{link}" target="_blank" rel="noopener noreferrer">{title_display}</a></h6>
                <p class="mb-0">{exp_display} | {address}
                <span class="copy-icon" onclick="copyText('{address}')">📋</span></p>
            </div>
            '''
            parts.append(html_item)

        parts.append('</div></div></section>')

    # Close table view
    parts.append('</div>')

    # Map tab
    parts.append('''
      <div class="tab-pane fade" id="mapView" role="tabpanel">
        <div id="map"></div>
      </div>
    </div>
    ''')

    # JS scripts
    parts.append('''
    <script>
      function copyText(text) {
        navigator.clipboard.writeText(text).then(function() {
          alert("Adresse copiée: " + text);
        }, function(err) {
          alert("Erreur de copie: " + err);
        });
      }

      // Init map
      const homeCoords = [48.8256, 2.3259]; // 5 rue Victor Considérant, Paris
      const map = L.map("map").setView(homeCoords, 12);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors"
      }).addTo(map);

      // Home marker + circle
      L.marker(homeCoords).addTo(map).bindPopup("🏠 Domicile");
      L.circle(homeCoords, {
        radius: 5000,
        color: "purple",
        fillColor: "#b19cd9",
        fillOpacity: 0.2
      }).addTo(map).bindPopup("Rayon 5 km");

      const events = [];
    ''')

    # Push events from Python → JS
    for date, events in grouped.items():
        for e in events:
            lat = e.get("lat")
            lon = e.get("lon")
            if not lat or not lon:
                continue
            title = (e.get("Titre") or "").replace("'", "\\'")
            exp = e.get("Exposants", "")
            addr = (e.get("Adresse") or "").replace("'", "\\'")
            parts.append(f"events.push({{name: '{title}', exposants: '{exp}', address: '{addr}', date: '{date}', lat: {lat}, lon: {lon} }});\n")

    # Add markers
    parts.append('''
      events.forEach(ev => {
        L.marker([ev.lat, ev.lon]).addTo(map)
          .bindPopup("<b>" + ev.name + "</b><br>" + ev.exposants + " exposants<br>" + ev.date + "<br>" + ev.address);
      });

      // Fix map rendering after tab change
      document.getElementById('map-tab').addEventListener('shown.bs.tab', () => {
        map.invalidateSize();
      });
    </script>
    ''')

    parts.append('</div></body></html>')

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"Generated HTML: {output_file}")
    return output_file

# ----------------------------
# Main flow
# ----------------------------
def main(master_url=MASTER_URL, output_dir=OUTPUT_DIR):
    print("Fetching master page and extracting links...")
    master_html = fetch_page_content(master_url)
    master_soup = BeautifulSoup(master_html, "html.parser")
    links = []
    for a in master_soup.find_all("a", href=True):
        href = a["href"]
        if "/evenement/" in href:
            full = href if href.startswith("http") else "https://vide-greniers.org" + href
            if full not in links:
                links.append(full)
    print(f"[{len(links)}] Found event links")

    manifs = []
    for link in links:
        try:
            page_html = fetch_page_content(link)
            page_soup = BeautifulSoup(page_html, "html.parser")

            date_str = extract_date(page_soup)  # uses technique A then B
            titre = extract_title(page_soup)
            exposants = extract_exposants(page_soup)
            adresse = extract_address(page_soup)
            ville = extract_ville_from_address(adresse)

            manif = {
                "Titre": titre,
                "Exposants": exposants,
                "Adresse": adresse,
                "Ville": ville,
                "ManifDate": date_str,
                "ManifLink": link
            }

            display_manif(manif)
            manifs.append(manif)
        except Exception as e:
            print(f"Error extracting {link}: {e}")

    grouped = group_and_sort(manifs)
    save_to_json(grouped, output_dir=output_dir, prefix=OUTPUT_PREFIX)
    generate_html(grouped, output_file=os.path.join(output_dir, HTML_OUTPUT))
    

if __name__ == "__main__":
    main()
