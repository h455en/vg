import locale
import json
import re
import time
import os
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

#_____________CONFIG_____________________

MASTER_URL = "https://brocabrac.fr/ile-de-france/vide-grenier/?d=2025-11-15,2025-12-21"

JSON_HOSTING_URL = "https://jsonhosting.com/api/json/2ea29f9a"
EDIT_KEY = "7d4982b93df21c740681018af810d5faeda577b5031d33dbb39825ca596635db"  # os.environ.get("JSONHOSTING_EDIT_KEY") 
#________________________________________

REQUEST_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
DEFAULT_DATE = datetime(1, 1, 1)

# Explicitly define French month/weekday names for robust parsing
FRENCH_MONTHS = {
    'janvier': 'January', 'février': 'February', 'mars': 'March', 'avril': 'April',
    'mai': 'May', 'juin': 'June', 'juillet': 'July', 'août': 'August',
    'septembre': 'September', 'octobre': 'October', 'novembre': 'November', 'décembre': 'December'
}
FRENCH_WEEKDAYS = {
    'lundi': '', 'mardi': '', 'mercredi': '', 'jeudi': '', 
    'vendredi': '', 'samedi': '', 'dimanche': ''
}

# --- 0. JSON Hosting Update Function ---
def update_jsonhosting(json_url: str, edit_key: str, data: dict, retries: int = 2, delay: int = 5):
    if not edit_key:
        raise ValueError("❌ EDIT_KEY is missing or empty. Please set it as an environment variable.")

    headers = {
        "X-Edit-Key": edit_key,
        "Content-Type": "application/json",
    }

    # Ensure the data is JSON-formatted string
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
            if 'response' in locals() and hasattr(response, "text") and response.text:
                print(f"Response (truncated): {response.text[:300]}")
            if attempt < retries:
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("❌ All attempts failed.")
                return False

# --- 1. Data Structure (Manif Object) ---
@dataclass
class Manif:
    """The required object structure for each event."""
    Titre: str = "NA"
    Exposants: int = -1
    Ville: str = "NA"
    Adresse: str = "NA"
    ManifDate: datetime = DEFAULT_DATE  # Used internally for sorting/grouping
    ManifLink: str = "NA"

# --- 2. Utility Methods for Extraction and Formatting ---
# (normalize_french_date, parse_french_date, extract_manif_date, extract_titre, extract_exposants, extract_adresse, extract_ville_and_arrondissement remain unchanged)
def normalize_french_date(date_str: str) -> str:
    """Replaces French month and weekday names with English equivalents for parsing."""
    normalized_str = date_str.lower()
    for fr, en in FRENCH_MONTHS.items():
        normalized_str = normalized_str.replace(fr, en)
    for fr in FRENCH_WEEKDAYS.keys():
        normalized_str = normalized_str.replace(fr, '')
    
    normalized_str = re.sub(r'\s+', ' ', normalized_str).strip()
    return normalized_str

def parse_french_date(date_str: str) -> datetime:
    """Converts a French date string to a datetime object robustly."""
    if not date_str: return DEFAULT_DATE
    
    normalized_str = normalize_french_date(date_str)
    
    formats = ['%d %B %Y', '%d %b %Y']
    
    for fmt in formats:
        try: 
            return datetime.strptime(normalized_str, fmt)
        except ValueError: 
            continue
    
    try:
        match = re.search(r'(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})', normalized_str, re.IGNORECASE)
        if match:
             return datetime.strptime(match.group(1).strip(), '%d %B %Y')
    except Exception:
        pass
        
    return DEFAULT_DATE

def extract_manif_date(event_soup: BeautifulSoup) -> datetime:
    """Extracts and parses the ManifDate (datetime) property."""
    try:
        date_element = event_soup.find('time') or event_soup.find(class_='manif-date')
        if date_element:
            return parse_french_date(date_element.text.strip())
        
        body_text = event_soup.get_text()
        date_match = re.search(r'(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}', body_text, re.IGNORECASE)
        if date_match:
            return parse_french_date(date_match.group(0))

        return DEFAULT_DATE
    except Exception:
        return DEFAULT_DATE

def extract_titre(event_soup: BeautifulSoup) -> str:
    """Extracts the Titre, cleans it, and replaces 'vide-grenier' variants with 'Vg'."""
    try:
        title_element = event_soup.find('h1')
        if title_element:
            title = title_element.text.strip()
            # Clean up bullet points and excess whitespace
            title = re.sub(r'[\s•]+', ' ', title).strip() 
            title = re.sub(r'^[\s•]+|[\s•]+$', '', title) 
            title = re.sub(r'\b(?:vide\s*-\s*grenier[s]?|Vide\s*Grenier)\b', 'Vg', title, flags=re.IGNORECASE)
            
            return title
        return "NA"
    except Exception:
        return "NA"

def extract_exposants(event_soup: BeautifulSoup) -> int:
    try:
        text_to_search = event_soup.get_text()
        
        match_plus = re.search(r'Plus\s+de\s*(\d+)', text_to_search, re.IGNORECASE)
        if match_plus: return int(match_plus.group(1))

        match_range = re.search(r'De\s*(\d+)\s*à\s*(\d+)', text_to_search, re.IGNORECASE)
        if match_range: return round((int(match_range.group(1)) + int(match_range.group(2))) / 2)

        match_moins = re.search(r'Moins\s+de\s*(\d+)', text_to_search, re.IGNORECASE)
        if match_moins: return int(match_moins.group(1))

        match_exact = re.search(r'(\d+)\s*exposant[s]?', text_to_search, re.IGNORECASE)
        if match_exact: return int(match_exact.group(1))

        return -1
    except Exception:
        return -1

def extract_adresse(event_soup: BeautifulSoup) -> str:
    try:
        address_block = event_soup.select_one('div.block.event-address')
        
        if address_block:
            lines = [line.strip() for line in address_block.get_text('\n').split('\n') if line.strip()]
            
            if lines:
                full_address = " ".join(lines)
                if full_address.lower().startswith('adresse '):
                    full_address = full_address[len('Adresse '):]
                return full_address.strip()
                
        return "NA"
    except Exception:
        return "NA"

def extract_ville_and_arrondissement(full_address: str) -> str:
    if full_address and full_address != "NA":
        words = [word.strip() for word in re.split(r'[,\s\-]+', full_address) if word.strip()]
        ville = words[-1] if words else "NA"

        if ville.lower() == 'paris':
            match = re.search(r'750(\d{2})', full_address)
            if match:
                arrondissement = int(match.group(1))
                return f"Paris {arrondissement}"

        return ville
    return "NA"


# --- 3. Main Scraping Logic Functions ---
def scrape_master_page(url: str) -> List[Manif]:
    print(f"Step 1: Fetching links from master page: {url}")
    manif_links: List[Manif] = []
    
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching Master URL: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    event_links: list = soup.find_all('a', href=re.compile(r'/\d{1,}/\w+/[0-9]+\-'))

    if not event_links:
        print("Error: Could not find any event links on the master page. Check the regex or selectors.")
        return []

    base_url_parts = url.split('/')
    base_url = '/'.join(base_url_parts[:3])

    for link_element in event_links:
        relative_url = link_element['href']
        full_url = urljoin(base_url, relative_url)
        manif_links.append(Manif(ManifLink=full_url))

    return manif_links

def scrape_event_details(manif: Manif) -> Manif:
    url = manif.ManifLink
    print(f"  > Fetching details for: {url}")
    
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        manif.Adresse = extract_adresse(soup)
        manif.Ville = extract_ville_and_arrondissement(manif.Adresse)
        manif.Titre = extract_titre(soup)
        manif.Exposants = extract_exposants(soup)
        manif.ManifDate = extract_manif_date(soup) 
        
    except requests.RequestException as e:
        print(f"  > Error fetching event URL {url}: {e}. Defaults used.")
        
    time.sleep(0.5) 
    
    return manif

def process_and_output(manifs: List[Manif]):
    """Groups, sorts, prints to screen, and UPDATES the online JSON file."""
    
    manifs_by_date: Dict[datetime, List[Manif]] = defaultdict(list)
    for manif in manifs:
        manifs_by_date[manif.ManifDate].append(manif)

    sorted_dates = sorted([d for d in manifs_by_date if d != DEFAULT_DATE])
    if DEFAULT_DATE in manifs_by_date:
        sorted_dates.append(DEFAULT_DATE)

    json_output_data: Dict[str, Any] = {}
    
    # Set locale for output date formatting (French)
    current_locale = locale.getlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except:
         try: locale.setlocale(locale.LC_TIME, 'fr_FR')
         except: pass

    for date in sorted_dates:
        manifs_list = manifs_by_date[date]
        manifs_list.sort(key=lambda m: m.Exposants, reverse=True)
        
        date_str_formatted = "NA/Unparsed Date (01.01.0001)"
        if date != DEFAULT_DATE:
            date_str_formatted = date.strftime('%A %d %B %Y')
        
        json_group: List[Dict[str, Any]] = []
        
        for manif in manifs_list:
            manif_dict = {
                "Titre": manif.Titre,
                "Exposants": manif.Exposants,
                "Adresse": manif.Adresse, 
                "Ville": manif.Ville,
                "ManifDate": date_str_formatted, 
                "ManifLink": manif.ManifLink
            }
            json_group.append(manif_dict)
        
        json_output_data[date_str_formatted] = json_group

    # Restore original locale
    try: locale.setlocale(locale.LC_TIME, current_locale)
    except: pass
    
    # --- ONLINE UPDATE LOGIC ---
    metadata = {"last_update": datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
    final_data = {"metadata": metadata, "events": json_output_data}
    
    # Use the provided function to update the remote JSON file
    update_jsonhosting(JSON_HOSTING_URL, EDIT_KEY, final_data)

# --- Execution Block ---
if __name__ == "__main__":
    if not EDIT_KEY:
        print("🚨 Warning: JSONHOSTING_EDIT_KEY environment variable is not set locally.")
        print("   The script will attempt to run, but the final update to jsonhosting.com will fail.")
    
    print("--- Starting Brocabrac Scraper ---")
    manifs_with_links = scrape_master_page(MASTER_URL)
    
    if not manifs_with_links:
        print("\nScraping aborted: No event links were found on the master page.")
    else:
        print(f"\nStep 2: Scraping details for {len(manifs_with_links)} events...")
        completed_manifs = [scrape_event_details(manif) for manif in manifs_with_links]
        process_and_output(completed_manifs)