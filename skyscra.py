import os
import re
import json
import requests
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# =================================================================
# /////////////////// CONFIGURATION
# =================================================================

# --- GIST CONFIG ---
GIST_ID = "1fc699b89c342bacdd3cfdb28aeed2dd"
GIST_FILENAME = "vg_events_nov_2025.json"

# --- SCRAPING CONFIG ---
YEAR = "2025"
MIN_DATE = f"{YEAR}-11-10"
MAX_DATE = f"{YEAR}-12-31"
MASTER_URL = f"https://vide-greniers.org/evenements/Ile-de-France?min={MIN_DATE}&max={MAX_DATE}&tags%5B0%5D=1"

# --- LOCALE AND FALLBACKS ---
FALLBACK_DATE = "01.01.0001"
WEEKDAY_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTH_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}

# =================================================================
# /////////////////// GIST API HANDLER
# =================================================================

def update_gist(gist_id: str, filename: str, data: dict, token: str):
    """
    Serializes data to JSON and updates a file within a GitHub Gist.
    """
    print(f"\nAttempting to update GitHub Gist ID: {gist_id} with file: {filename}...")
    
    # 1. Prepare API URL and Headers
    url = f"https://api.github.com/gists/{gist_id}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "VG-Scraper-Gist-Updater" # GitHub requires a User-Agent
    }

    # 2. Prepare Payload
    # The dictionary of events is dumped to a formatted JSON string
    json_content = json.dumps(data, indent=2, ensure_ascii=False)
    payload = {
        "files": {
            filename: {
                "content": json_content
            }
        }
    }
    
    # 3. Make the PATCH request to update the Gist
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        
        # Success output
        print(f"Successfully updated Gist file '{filename}'.")
        print(f"   View Gist: {response.json().get('html_url', 'URL not found')}")
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to update Gist: {e}")
        if response.text:
            print(f"   GitHub API response error: {response.text[:200]}...") # Print first 200 chars of error
        
# =================================================================
# /////////////////// DATE UTILITIES
# =================================================================

def format_date_fr(dt: datetime) -> str:
    """Formats a datetime object to 'Dimanche 5 Octobre 2025' format."""
    if not isinstance(dt, datetime):
        return FALLBACK_DATE
    weekday = WEEKDAY_FR[dt.weekday()]
    month = MONTH_FR[dt.month]
    return f"{weekday} {dt.day} {month} {dt.year}"

def parse_iso_date_str(s: str):
    """Parses an ISO-like date string (YYYY-MM-DD or YYYY/MM/DD) into a datetime object."""
    if not s: return None
    
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None    
    return None

def parse_fr_date_string(s: str):
    """Parses a French date string ('Dimanche 5 Octobre 2025') into a datetime object."""
    if not s or s == FALLBACK_DATE: return None
    pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})"
    m = re.search(pattern, s, flags=re.IGNORECASE)
    if not m: return None
    
    day = int(m.group(2))
    month_name = m.group(3).capitalize()
    year = int(m.group(4))
    
    # map month_name to number
    month_num = next((num for num, name in MONTH_FR.items() if name.lower() == month_name.lower()), None)
    
    if not month_num: return None
    try:
        return datetime(year, month_num, day)
    except ValueError:
        return None

# =================================================================
# /////////////////// SCRAPING LOGIC (Simplified)
# =================================================================

def fetch_page_content(url, wait_ms=1000):
    """Fetches and returns the HTML content of a URL using Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        # small wait for Alpine.js to finish
        page.wait_for_timeout(wait_ms)
        html_content = page.content()
        browser.close()
        return html_content

def extract_date(soup):
    """Extracts date using time tag, JSON-LD, or page-wide regex fallback."""
    # 1. Time Tag
    time_tag = soup.find("time")
    if time_tag:
        text = time_tag.get_text(" ", strip=True)
        # Check for direct French date in text
        fr_pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
        m = re.search(fr_pattern, text, flags=re.IGNORECASE)
        if m: return m.group(0).strip()
        
        # Try datetime attribute or text iso
        dt_attr = time_tag.get("datetime") or text
        dt = parse_iso_date_str(dt_attr)
        if dt: return format_date_fr(dt)

    # 2. JSON-LD
    scripts = soup.find_all("script", type="application/ld+json")
    for s in scripts:
        try:
            data = json.loads(s.string or "")
            # simple helper for recursive search of 'startDate'
            def find_startdate(obj):
                if isinstance(obj, dict):
                    if "startDate" in obj and obj["startDate"]: return obj["startDate"]
                    for v in obj.values():
                        res = find_startdate(v)
                        if res: return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = find_startdate(item)
                        if res: return res
                return None

            sd = find_startdate(data)
            if sd:
                dt = parse_iso_date_str(sd)
                if dt: return format_date_fr(dt)
        except Exception:
            continue

    # 3. Whole Page Regex
    text = soup.get_text(" ", strip=True)
    pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if m: return m.group(0).strip()

    return FALLBACK_DATE

def extract_title(soup):  
    """Extracts the title from H1 or H2 tags."""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    h2 = soup.find("h2")
    if h2 and h2.get_text(strip=True):
        return h2.get_text(" ", strip=True)
    return "NA"

def extract_exposants(soup):
    """Extracts the number of exhibitors."""
    txt = soup.get_text(" ", strip=True)
    m = re.search(r"(\d+)\s*exposants", txt, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except:
            return -1
    return -1

def _normalize_paris_zip(city_part: str) -> str:
    """Converts 'Paris XX' format to '750XX Paris' if applicable."""
    city_part_stripped = city_part.strip()
    # Check for the 'Paris XX' format
    match = re.search(r"Paris\s*(\d+)", city_part_stripped, re.IGNORECASE)
    if match:
        district_num = int(match.group(1))
        if 1 <= district_num <= 20:
            zip_code = f"750{district_num:02d}"
            return f"{zip_code} Paris"
    return city_part_stripped

def extract_address(soup):
    """Extracts and cleans the event address."""
    section = soup.find("section", attrs={"x-ref": "locationSection"})
    raw_text = section.get_text(" ", strip=True) if section else ""
    
    if "Accès" in raw_text and "Itinéraire" in raw_text:
        try:
            raw_text = raw_text.split("Accès", 1)[1].split("Itinéraire", 1)[0].strip()
        except:
            pass
            
    parts = [p.strip() for p in raw_text.split(",") if p.strip()]
    if parts:
        parts[-1] = _normalize_paris_zip(parts[-1])
        # Simple deduplication based on consecutive identical parts
        dedup = [parts[0]]
        for i in range(1, len(parts)):
            if parts[i] != parts[i-1]:
                dedup.append(parts[i])
        
        return ", ".join(dedup)
    
    return "NA"

def extract_ville_from_address(address: str):
    """Extracts the city and zip from the last part of the address string."""
    if not address or address == "NA":
        return "NA"
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return parts[-1] if parts else "NA"

def group_and_sort(manifs: list):
    """Groups manifs by date and sorts them by date and number of exhibitors."""
    grouped = defaultdict(list)
    for m in manifs:
        grouped[m["ManifDate"]].append(m)

    def key_for_date_str(ds: str):
        dt = parse_fr_date_string(ds)
        return dt if dt else datetime.min

    # Sort dates (most recent first)
    sorted_dates = sorted(grouped.keys(), key=key_for_date_str, reverse=True)
    grouped_sorted = {date: grouped[date] for date in sorted_dates}
    
    # Sort items inside each group by Exposants descending
    for date in grouped_sorted:
        grouped_sorted[date] = sorted(grouped_sorted[date], 
                                      key=lambda x: x.get("Exposants", -1), 
                                      reverse=True)
        
    return grouped_sorted

def display_manif(manif: dict):
    """Helper to display extracted data during runtime."""
    print(f"  Title: {manif.get('Titre', 'NA')}")
    print(f"  Date: {manif.get('ManifDate', FALLBACK_DATE)}")
    print(f"  Exhibitors: {manif.get('Exposants', -1)}")
    print(f"  Address: {manif.get('Adresse', 'NA')}")
    print("-" * 50)

# =================================================================
# /////////////////// MAIN EXECUTION
# =================================================================

def main():
    print("Starting Vide-Greniers Scraper...")
    print(f"Target URL: {MASTER_URL}")
    
    # 1. Fetch master page and extract detail links
    master_html = fetch_page_content(MASTER_URL)
    master_soup = BeautifulSoup(master_html, "html.parser")
    links = []
    
    for a in master_soup.find_all("a", href=True):
        href = a["href"]
        if "/evenement/" in href:
            full = href if href.startswith("http") else "https://vide-greniers.org" + href
            if full not in links:
                links.append(full)
                
    print(f"[{len(links)}] Found event links.")

    # 2. Scrape individual event pages
    manifs = []
    for link in links:
        print(f"\nScraping: {link}")
        try:
            page_html = fetch_page_content(link)
            page_soup = BeautifulSoup(page_html, "html.parser")

            date_str = extract_date(page_soup)
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
            manifs.append(manif)
            display_manif(manif)
            
        except Exception as e:
            print(f"Error extracting {link}: {e}")

    # 3. Group and sort results in memory
    grouped_events = group_and_sort(manifs)
    
    # 4. Update GitHub Gist
    # In gist_scraper.py
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    update_gist(
        gist_id=GIST_ID,
        filename=GIST_FILENAME,
        data=grouped_events,
        token=GITHUB_TOKEN
    )

    print("\nScraping and Gist update complete.")

if __name__ == "__main__":
    main()
