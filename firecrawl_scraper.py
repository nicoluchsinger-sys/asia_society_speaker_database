#!/usr/bin/env python3
"""
Firecrawl-based scraper for Asia Society events
Alternative to Selenium - faster and cleaner output
"""

import os
import time
from datetime import datetime
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp
from database import SpeakerDatabase
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class FirecrawlEventScraper:
    def __init__(self, base_url="https://asiasociety.org/events/past", api_key=None):
        """
        Initialize Firecrawl scraper

        Args:
            base_url: Starting URL for events
            api_key: Firecrawl API key (or set FIRECRAWL_API_KEY env var)
        """
        self.base_url = base_url
        self.api_key = api_key or os.getenv('FIRECRAWL_API_KEY')

        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment or parameters")

        self.app = FirecrawlApp(api_key=self.api_key)

        # Detect if scraping globally or specific location
        self.is_global = '/events/past' in base_url and base_url.count('/') == 4

    def extract_location_from_url(self, url):
        """Extract location from URL path (e.g., /switzerland/ -> Switzerland)"""
        if '/switzerland/' in url:
            return 'Switzerland'
        elif '/new-york/' in url:
            return 'New York'
        elif '/hong-kong/' in url:
            return 'Hong Kong'
        elif '/texas/' in url or '/houston/' in url:
            return 'Texas'
        elif '/india/' in url:
            return 'India'
        elif '/japan/' in url:
            return 'Japan'
        elif '/australia/' in url:
            return 'Australia'
        elif '/philippines/' in url:
            return 'Philippines'
        elif '/france/' in url:
            return 'France'
        elif '/seattle/' in url:
            return 'Seattle'
        elif '/northern-california/' in url:
            return 'Northern California'
        elif '/southern-california/' in url:
            return 'Southern California'
        elif '/asian-women-empowered/' in url:
            return 'Asian Women Empowered'
        else:
            return 'Unknown'

    def extract_event_links(self, html):
        """Extract event links from a listing page"""
        soup = BeautifulSoup(html, 'html.parser')

        links = []
        # Find all event links (adjust selector based on actual HTML structure)
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/events/' in href and 'past' not in href:
                # Make absolute URL
                if href.startswith('/'):
                    href = 'https://asiasociety.org' + href
                if href not in links and href != self.base_url:
                    links.append(href)

        return links

    def scrape_event_page(self, url):
        """
        Scrape a single event page using Firecrawl

        Returns:
            dict with event data or None if failed
        """
        try:
            print(f"   Loading: {url}")

            # Use Firecrawl to scrape the page
            result = self.app.scrape(url, formats=['markdown', 'html'], only_main_content=True)

            if not result or not result.markdown:
                print(f"   ❌ Failed to scrape (no content)")
                return None

            # Extract data from Document object
            markdown = result.markdown or ''
            html = result.html or ''
            metadata = result.metadata

            # Get title
            title = metadata.title or 'Untitled Event'

            # Extract date from metadata or content
            # Check for various date fields in metadata
            event_date = (metadata.published_time or
                         metadata.dc_date_created or
                         metadata.dc_date or
                         self.extract_date_from_markdown(markdown))

            # Extract location from URL
            location = self.extract_location_from_url(url)

            return {
                'url': url,
                'title': title,
                'body_text': markdown,  # Clean markdown instead of raw HTML
                'raw_html': html,
                'event_date': event_date,
                'location': location
            }

        except Exception as e:
            print(f"   ❌ Error scraping {url}: {str(e)}")
            return None

    def extract_date_from_markdown(self, markdown):
        """Extract date from markdown content (simple heuristic)"""
        # Look for common date patterns in first 500 chars
        import re
        snippet = markdown[:500]

        # Pattern like "January 21, 2026" or "21 Jan 2026"
        patterns = [
            r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, snippet, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def scrape_events(self, db, limit=None, max_pages=None):
        """
        Scrape events from listing pages and store in database

        Args:
            db: SpeakerDatabase instance
            limit: Maximum number of events to scrape
            max_pages: Maximum number of listing pages to fetch

        Returns:
            Number of events scraped
        """
        print("="*70)
        print("Starting Firecrawl-based scrape of Asia Society events")
        print(f"Source: {self.base_url}")
        print("="*70)

        try:
            # Fetch events from listing pages
            all_event_links = []
            page = 0

            print(f"\n1. Fetching events listing pages...")

            # Get already-scraped URLs from database
            cursor = db.conn.cursor()
            cursor.execute('SELECT url FROM events')
            already_scraped = set(row[0] for row in cursor.fetchall())
            print(f"   Database contains {len(already_scraped)} already-scraped events")

            while True:
                page_url = f"{self.base_url}?page={page}"
                print(f"   Page {page + 1}: {page_url}")

                # Scrape listing page
                result = self.app.scrape(page_url, formats=['html'], only_main_content=False)

                if not result or not result.html:
                    print("   No more pages found")
                    break

                # Extract event links from this page
                page_links = self.extract_event_links(result.html)
                if not page_links:
                    print("   No more events found")
                    break

                new_links = [l for l in page_links if l not in all_event_links]
                all_event_links.extend(new_links)

                # Count how many are actually new (not in DB)
                new_unscraped = [l for l in all_event_links if l not in already_scraped]
                print(f"   Found {len(new_links)} events on page (total: {len(all_event_links)}, new: {len(new_unscraped)})")

                page += 1

                # Stop conditions
                if limit and len(new_unscraped) >= limit:
                    print(f"   Found {len(new_unscraped)} new events, meeting limit of {limit}")
                    break

                if max_pages and page >= max_pages:
                    print(f"   Reached max pages limit ({max_pages})")
                    break

                time.sleep(1)  # Brief pause between pages

            # Filter to only new events
            new_event_links = [l for l in all_event_links if l not in already_scraped]
            print(f"\n2. Total unique events found: {len(all_event_links)} ({len(new_event_links)} new)")

            event_links = new_event_links
            if limit and len(event_links) > limit:
                event_links = event_links[:limit]
                print(f"   Limiting to {limit} new events for this run")
            elif len(event_links) == 0:
                print(f"   No new events to scrape!")
                return 0
            else:
                print(f"   Will scrape {len(event_links)} new events")

            print(f"\n3. Scraping individual event pages...")

            # Scrape each event
            scraped_count = 0
            for i, url in enumerate(event_links, 1):
                print(f"\n   [{i}/{len(event_links)}]")

                event_data = self.scrape_event_page(url)

                if event_data:
                    # Save to database
                    event_id = db.add_event(
                        url=event_data['url'],
                        title=event_data['title'],
                        body_text=event_data['body_text'],
                        raw_html=event_data['raw_html'],
                        event_date=event_data['event_date'],
                        location=event_data['location']
                    )

                    print(f"      ✓ Saved (Event ID: {event_id})")
                    print(f"        Title: {event_data['title'][:60]}...")
                    print(f"        Location: {event_data['location']}")
                    print(f"        Date: {event_data['event_date'] or 'Not found'}")
                    print(f"        Content length: {len(event_data['body_text'])} chars")

                    scraped_count += 1

                # Small delay between events
                time.sleep(0.5)

            print(f"\n{'='*70}")
            print(f"Scraping complete: {scraped_count} events saved to database")
            print(f"{'='*70}")

            return scraped_count

        except Exception as e:
            print(f"\n❌ Error during scraping: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0


def main():
    """Test the Firecrawl scraper"""
    import argparse

    parser = argparse.ArgumentParser(description='Test Firecrawl scraper')
    parser.add_argument('-e', '--events', type=int, default=3, help='Number of events to scrape')
    parser.add_argument('-p', '--pages', type=int, default=1, help='Number of pages to scrape')
    args = parser.parse_args()

    db = SpeakerDatabase()
    scraper = FirecrawlEventScraper()

    count = scraper.scrape_events(db, limit=args.events, max_pages=args.pages)

    print(f"\n✓ Scraped {count} events")

    stats = db.get_statistics()
    print(f"\nDatabase stats:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Processed: {stats['processed_events']}")


if __name__ == '__main__':
    main()
