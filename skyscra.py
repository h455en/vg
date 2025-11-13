"""
        //////////////////  SKYSCRAPY //////////////////////////
        Scrapes event data and updates JSON hosted on https://jsonhosting.com/
"""


import time
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

# --- JSONHOSTING CONFIG ---
JSON_URL = "https://jsonhosting.com/api/json/c3cdf9e5"   # replace with your own JSONHosting API URL
EDIT_KEY = "01d3d54c95b3039f1758f48e7473dae365f00b03be449da84bd5d0fc237e894e" #os.getenv("EDIT_KEY")                # stored as GitHub secret

# --- SCRAPING CONFIG ---
YEAR = "2025"
MIN_DATE = f"{YEAR}-11-10"
MAX_DATE = f"{YEAR}-12-31"
MASTER_URL = f"https://vide-greniers.org/evenements/Ile-de-France?min=2025-11-13&max=2025-12-28&tags%5B0%5D=1"
#MASTER_URL = f"https://vide-greniers.org/evenements/Paris-75?distance=0&min=2025-11-15&max=2025-11-23&tags%5B0%5D=1"

# --- LOCALE ---
FALLBACK_DATE = "01.01.0001"
WEEKDAY_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTH_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}

# =================================================================
# JSONHOSTING API HANDLER 
# =================================================================

def update_jsonhosting(json_url: str, edit_key: str, data: dict, retries: int = 2, delay: int = 5):
    if not edit_key:
        raise ValueError("❌ EDIT_KEY is missing or empty. Please set it as an environment variable.")

    headers = {
        "X-Edit-Key": edit_key,
        "Content-Type": "application/json",
    }

    json_payload = json.dumps(data, ensure_ascii=False)
    
    for attempt in range(1, retries + 1):
        try:
            print(f"\nAttempting to update JSONHosting at: {json_url} (Attempt {attempt}/{retries})")
            response = requests.patch(json_url, headers=headers, data=json_payload, timeout=15)
            response.raise_for_status()
            print(f"\JsonHosting [{json_url}]")
            print("✅ Successfully updated JSON on jsonhosting.com")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ Update failed on attempt {attempt}: {e}")
            if hasattr(response, "text") and response.text:
                print(f"Response (truncated): {response.text[:300]}")
            if attempt < retries:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("❌ All attempts failed.")
                return False

# =================================================================
#  DATE UTILITIES
# =================================================================

def format_date_fr(dt: datetime) -> str:
    if not isinstance(dt, datetime):
        return FALLBACK_DATE
    weekday = WEEKDAY_FR[dt.weekday()]
    month = MONTH_FR[dt.month]
    return f"{weekday} {dt.day} {month} {dt.year}"

def parse_iso_date_str(s: str):
    if not s:
        return None
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
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
    month_num = next((num for num, name in MONTH_FR.items() if name.lower() == month_name.lower()), None)
    if not month_num:
        return None
    try:
        return datetime(year, month_num, day)
    except ValueError:
        return None

# =================================================================
#  SCRAPING LOGIC
# =================================================================

def fetch_page_content(url, wait_ms=1000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(wait_ms)
        html_content = page.content()
        browser.close()
        return html_content

def extract_title(soup):
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    h2 = soup.find("h2")
    if h2 and h2.get_text(strip=True):
        return h2.get_text(" ", strip=True)
    return "NA"

def extract_exposants(soup):
    txt = soup.get_text(" ", strip=True)
    m = re.search(r"(\d+)\s*exposants", txt, flags=re.IGNORECASE)
    return int(m.group(1)) if m else -1

def _normalize_paris_zip(city_part: str) -> str:
    match = re.search(r"Paris\s*(\d+)", city_part, re.IGNORECASE)
    if match:
        district_num = int(match.group(1))
        if 1 <= district_num <= 20:
            return f"750{district_num:02d} Paris"
    return city_part.strip()

def extract_address(soup):
    section = soup.find("section", attrs={"x-ref": "locationSection"})
    raw_text = section.get_text(" ", strip=True) if section else ""
    if "Accès" in raw_text and "Itinéraire" in raw_text:
        try:
            raw_text = raw_text.split("Accès", 1)[1].split("Itinéraire", 1)[0].strip()
        except Exception:
            pass
    parts = [p.strip() for p in raw_text.split(",") if p.strip()]
    if parts:
        parts[-1] = _normalize_paris_zip(parts[-1])
        dedup = [parts[0]]
        for i in range(1, len(parts)):
            if parts[i] != parts[i-1]:
                dedup.append(parts[i])
        return ", ".join(dedup)
    return "NA"

def extract_ville_from_address(address: str):
    if not address or address == "NA":
        return "NA"
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return parts[-1] if parts else "NA"

def extract_date(soup):
    time_tag = soup.find("time")
    if time_tag:
        text = time_tag.get_text(" ", strip=True)
        fr_pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
        m = re.search(fr_pattern, text, flags=re.IGNORECASE)
        if m:
            return m.group(0).strip()
        dt_attr = time_tag.get("datetime") or text
        dt = parse_iso_date_str(dt_attr)
        if dt:
            return format_date_fr(dt)
    text = soup.get_text(" ", strip=True)
    pattern = r"(Lundi|Mardi|Mercredi|Jeudi|Vendredi|Samedi|Dimanche)\s+\d{1,2}\s+[A-Za-zÀ-ÿ]+\s+\d{4}"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(0).strip() if m else FALLBACK_DATE

def group_and_sort(manifs):
    grouped = defaultdict(list)
    for m in manifs:
        grouped[m["ManifDate"]].append(m)
    def key_for_date_str(ds):
        dt = parse_fr_date_string(ds)
        return dt if dt else datetime.min
    sorted_dates = sorted(grouped.keys(), key=key_for_date_str, reverse=True)
    grouped_sorted = {d: sorted(grouped[d], key=lambda x: x.get("Exposants", -1), reverse=True) for d in sorted_dates}
    return grouped_sorted

# =================================================================
# /////////////////// RUN IT ////////////////////////////////////
# =================================================================

def main():
    print("Starting Vide-Greniers Scraper...")
    print(f"Target URL: {MASTER_URL}")

    master_html = fetch_page_content(MASTER_URL)
    master_soup = BeautifulSoup(master_html, "html.parser")
    links = list({("https://vide-greniers.org" + a["href"]) for a in master_soup.find_all("a", href=True) if "/evenement/" in a["href"]})
    print(f"[{len(links)}] Found event links.")

    manifs = []
    for link in links:
        print(f"\nScraping: {link}")
        try:
            page_html = fetch_page_content(link)
            soup = BeautifulSoup(page_html, "html.parser")
            manif = {
                "Titre": extract_title(soup),
                "Exposants": extract_exposants(soup),
                "Adresse": extract_address(soup),
                "Ville": extract_ville_from_address(extract_address(soup)),
                "ManifDate": extract_date(soup),
                "ManifLink": link
            }
            manifs.append(manif)
            print(f"  -> {manif['Titre']} ({manif['ManifDate']})")
        except Exception as e:
            print(f"Error extracting {link}: {e}")

    grouped_events = group_and_sort(manifs)
    update_jsonhosting(JSON_URL, EDIT_KEY, grouped_events)
    print("\n✅ Scraping complete.")

if __name__ == "__main__":
    main()


