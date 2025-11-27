import requests
from bs4 import BeautifulSoup

def fetch_page_content(url: str) -> str:
    """
    Fetch the HTML content from the given URL.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch page: {e}")

def is_event_cancelled(html_content: str) -> bool:
    """
    Check if the event is cancelled by looking for 'Annulé' in the specific location:
    After the date and before the favorites button comment.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Method 1: Look for the favorites button comment and check what comes before it
    favorites_comment = soup.find(string=lambda text: text and 'Bouton favoris' in text)
    
    if favorites_comment:
        # Look for spans that are before the favorites comment and contain "Annulé"
        previous_elements = favorites_comment.find_all_previous('span')
        for element in previous_elements:
            if element.get_text(strip=True) == 'Annulé':
                return True
    
    # Method 2: Look for the specific structure - date followed by Annulé followed by favorites button
    # Find all spans and check their order and content
    all_spans = soup.find_all('span')
    
    for i, span in enumerate(all_spans):
        if span.get_text(strip=True) == 'Annulé':
            # Check if this span is in red (cancelled events are typically red)
            style = span.get('style', '').lower()
            parent_style = span.parent.get('style', '').lower() if span.parent else ''
            if 'color:red' in style or 'color: red' in style or 'color:#' in style or 'color:red' in parent_style:
                return True
            
            # Check if it's positioned near date elements and before favorites
            # Look at surrounding spans for context
            if i > 0:
                prev_span = all_spans[i-1]
                prev_text = prev_span.get_text(strip=True)
                # If previous span looks like a date (contains numbers and slashes)
                if any(char.isdigit() for char in prev_text) and ('/' in prev_text or '-' in prev_text):
                    return True
    
    # Method 3: Look for the exact pattern you described
    # Search for elements that contain both date-like patterns and are near "Annulé"
    date_patterns = ['/', '-', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 
                    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    
    for i, span in enumerate(all_spans):
        span_text = span.get_text(strip=True)
        if any(pattern in span_text.lower() for pattern in date_patterns):
            # Check next span for "Annulé"
            if i + 1 < len(all_spans):
                next_span = all_spans[i + 1]
                if next_span.get_text(strip=True) == 'Annulé':
                    return True
    
    return False

def get_event_cancellation_info(url: str) -> dict:
    """
    Get cancellation information for an event.
    """
    try:
        html_content = fetch_page_content(url)
        cancelled = is_event_cancelled(html_content)
        
        return {
            'url': url,
            'success': True,
            'is_cancelled': cancelled,
            'status': 'CANCELLED' if cancelled else 'ACTIVE',
            'error': None
        }
        
    except Exception as e:
        return {
            'url': url,
            'success': False,
            'is_cancelled': None,
            'status': 'ERROR',
            'error': str(e)
        }

def main():
    """Test with the provided URLs."""
    test_urls = [
        "https://vide-greniers.org/evenement/920292/20251123",  # Cancelled
        "https://vide-greniers.org/evenement/936432/20251123",  # Not cancelled
        "https://vide-greniers.org/evenement/936423/20251130",
        "https://vide-greniers.org/evenement/935010/20251129", # cancelled
        "https://vide-greniers.org/evenement/941827/20251122", 
        "https://vide-greniers.org/evenement/512674/20251123"
    ]
    
    print("Event Cancellation Detection - TARGETED LOCATION")
    print("=" * 50)
    
    for url in test_urls:
        print(f"\nChecking: {url}")
        info = get_event_cancellation_info(url)
        
        if info['success']:
            status = "❌ CANCELLED" if info['is_cancelled'] else "✅ ACTIVE"
            print(f"Result: {status}")
        else:
            print(f"❌ ERROR: {info['error']}")
        
        print("-" * 50)

if __name__ == "__main__":
    main()