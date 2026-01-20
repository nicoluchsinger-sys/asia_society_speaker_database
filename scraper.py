"""
Web scraper for Asia Society events
Scrapes event pages and stores them in the database
"""

import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
from database import SpeakerDatabase

class EventScraper:
    def __init__(self, base_url="https://asiasociety.org/switzerland/events"):
        self.base_url = base_url
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def fetch_page(self, url):
        """Fetch a web page"""
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_event_links(self, html):
        """Extract event page URLs from the events listing page"""
        soup = BeautifulSoup(html, 'html.parser')
        event_links = []
        
        # Find all links that look like event pages
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            
            # Look for event-specific URLs
            # Common patterns: /events/event-name, /switzerland/events/event-name, etc.
            if '/event' in href.lower() and href not in event_links:
                # Convert relative URLs to absolute
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = f"https://asiasociety.org{href}"
                else:
                    full_url = f"https://asiasociety.org/switzerland/{href}"
                
                # Avoid duplicate URLs and listing pages
                if full_url not in event_links and full_url != self.base_url:
                    event_links.append(full_url)
        
        return event_links
    
    def parse_event_page(self, html, url):
        """Extract event information from an event page"""
        soup = BeautifulSoup(html, 'html.parser')
        
        event_data = {
            'url': url,
            'title': '',
            'event_date': None,
            'body_text': '',
            'raw_html': html
        }
        
        # Extract title
        title_tag = soup.find('h1')
        if title_tag:
            event_data['title'] = title_tag.get_text(strip=True)
        else:
            # Fallback to page title
            title_tag = soup.find('title')
            if title_tag:
                event_data['title'] = title_tag.get_text(strip=True)
        
        # Try to extract date
        # Look for common date patterns and HTML elements
        date_patterns = [
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b'
        ]
        
        # Check meta tags and specific date elements
        date_elements = soup.find_all(['time', 'span', 'div'], class_=re.compile('date', re.I))
        for elem in date_elements:
            date_text = elem.get_text(strip=True)
            for pattern in date_patterns:
                match = re.search(pattern, date_text)
                if match:
                    event_data['event_date'] = match.group(0)
                    break
            if event_data['event_date']:
                break
        
        # Extract main content
        # Try to find the main content area
        content_selectors = [
            ('article', None),
            ('div', re.compile('content|body|description|detail|main', re.I)),
            ('section', re.compile('content|body|description|detail|main', re.I)),
        ]
        
        body_texts = []
        for tag, class_pattern in content_selectors:
            if class_pattern:
                areas = soup.find_all(tag, class_=class_pattern)
            else:
                areas = soup.find_all(tag)
            
            for area in areas:
                # Remove script and style elements
                for script in area(['script', 'style', 'nav', 'footer', 'header']):
                    script.decompose()
                
                text = area.get_text(separator=' ', strip=True)
                if len(text) > 100:  # Only include substantial text blocks
                    body_texts.append(text)
        
        # If no content found, get all paragraph text
        if not body_texts:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50:
                    body_texts.append(text)
        
        event_data['body_text'] = '\n\n'.join(body_texts)
        
        return event_data
    
    def scrape_events(self, db: SpeakerDatabase, limit=None):
        """
        Main scraping workflow
        
        Args:
            db: SpeakerDatabase instance
            limit: Maximum number of events to scrape (None for all)
        """
        print("="*70)
        print("Starting scrape of Asia Society Switzerland events")
        print("="*70)
        
        # Fetch events listing page
        print(f"\n1. Fetching events listing page: {self.base_url}")
        html = self.fetch_page(self.base_url)
        
        if not html:
            print("❌ Failed to fetch events page. Check your internet connection.")
            return 0
        
        # Extract event links
        print("\n2. Extracting event links...")
        event_links = self.extract_event_links(html)
        print(f"   Found {len(event_links)} potential event links")
        
        if limit:
            event_links = event_links[:limit]
            print(f"   Limiting to {limit} events for this run")
        
        # Scrape each event
        print(f"\n3. Scraping individual event pages...")
        scraped_count = 0
        
        for i, event_url in enumerate(event_links, 1):
            print(f"\n   [{i}/{len(event_links)}] {event_url}")
            
            event_html = self.fetch_page(event_url)
            if not event_html:
                print("      ⚠ Failed to fetch")
                continue
            
            # Parse event data
            event_data = self.parse_event_page(event_html, event_url)
            
            if not event_data['body_text'] or len(event_data['body_text']) < 100:
                print("      ⚠ Insufficient content found")
                continue
            
            # Save to database
            try:
                event_id = db.add_event(
                    url=event_data['url'],
                    title=event_data['title'],
                    body_text=event_data['body_text'],
                    raw_html=event_data['raw_html'],
                    event_date=event_data['event_date']
                )
                print(f"      ✓ Saved (Event ID: {event_id})")
                print(f"        Title: {event_data['title'][:60]}...")
                if event_data['event_date']:
                    print(f"        Date: {event_data['event_date']}")
                print(f"        Content length: {len(event_data['body_text'])} chars")
                scraped_count += 1
                
            except Exception as e:
                print(f"      ❌ Database error: {e}")
            
            # Be polite to the server
            time.sleep(1)
        
        print("\n" + "="*70)
        print(f"Scraping complete: {scraped_count} events saved to database")
        print("="*70)
        
        return scraped_count


if __name__ == "__main__":
    # Test the scraper
    with SpeakerDatabase() as db:
        scraper = EventScraper()
        scraper.scrape_events(db, limit=5)
        
        # Show statistics
        stats = db.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"  Total events: {stats['total_events']}")
        print(f"  Processed: {stats['processed_events']}")
        print(f"  Pending: {stats['total_events'] - stats['processed_events']}")
