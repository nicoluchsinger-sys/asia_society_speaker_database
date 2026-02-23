#!/usr/bin/env python3
"""
Diagnostic script to understand Asia Society pagination limits
Tests how many pages of events are available and what dates they cover
"""

from selenium_scraper import SeleniumEventScraper
from database import SpeakerDatabase
import os

def diagnose_pagination():
    """Check how far back the Asia Society pagination goes"""

    # Use production DB path if on Railway, else local
    db_path = '/data/speakers.db' if os.path.exists('/data') else 'speakers.db'

    print("="*70)
    print("PAGINATION DIAGNOSTIC")
    print("="*70)

    scraper = SeleniumEventScraper(headless=True)
    db = SpeakerDatabase(db_path)

    try:
        # Get already-scraped URLs
        cursor = db.conn.cursor()
        cursor.execute('SELECT url FROM events')
        already_scraped = set(row[0] for row in cursor.fetchall())
        print(f"Already scraped: {len(already_scraped)} events\n")

        # Test first 10 pages to see what's available
        print("Testing pagination (first 10 pages)...")
        print("-"*70)

        total_events_found = 0
        total_new_events = 0
        empty_pages = 0

        for page in range(10):
            page_url = f"{scraper.base_url}?page={page}"
            print(f"\nPage {page}: {page_url}")

            html = scraper.fetch_page(page_url, wait_time=5)
            if not html:
                print("  ❌ Failed to fetch page")
                empty_pages += 1
                continue

            # Extract events from this page
            event_links = scraper.extract_event_links(html)

            if not event_links:
                print("  ⚠ No events found on page")
                empty_pages += 1
                continue

            new_events = [l for l in event_links if l not in already_scraped]
            total_events_found += len(event_links)
            total_new_events += len(new_events)

            print(f"  Events on page: {len(event_links)}")
            print(f"  New (unscraped): {len(new_events)}")
            print(f"  Already scraped: {len(event_links) - len(new_events)}")

            # Show sample URLs
            if new_events:
                print(f"  Sample new event: {new_events[0]}")

        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Pages tested: 10")
        print(f"Empty pages: {empty_pages}")
        print(f"Total events found: {total_events_found}")
        print(f"New events found: {total_new_events}")
        print(f"Already scraped: {total_events_found - total_new_events}")

        if total_new_events == 0:
            print("\n⚠ WARNING: No new events found in first 10 pages!")
            print("This suggests you may have reached the limit of available")
            print("historical events on the Asia Society website.")
            print("\nPossible solutions:")
            print("1. The website may only show recent events (last ~1 year)")
            print("2. Try scraping location-specific pages for older events")
            print("3. Contact Asia Society for historical event data")

    finally:
        scraper.close()
        db.close()

if __name__ == '__main__':
    diagnose_pagination()
