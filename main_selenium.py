"""
Main script to scrape events and extract speaker information (Selenium version)
"""

import os
import argparse
from database import SpeakerDatabase
from selenium_scraper import SeleniumEventScraper
from speaker_extractor import SpeakerExtractor
import json

def load_api_key():
    """Load API key from .env file or environment"""
    # Try to load from .env file
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ANTHROPIC_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    os.environ['ANTHROPIC_API_KEY'] = key
                    return key
    
    # Try environment variable
    return os.getenv('ANTHROPIC_API_KEY')


def scrape_events(limit=None, headless=True, max_pages=1):
    """Step 1: Scrape events from website using Selenium and save to database"""
    print("\n" + "🌐 STEP 1: SCRAPING EVENTS FROM WEBSITE (SELENIUM)")
    print("="*70)

    with SpeakerDatabase() as db:
        scraper = SeleniumEventScraper(headless=headless)
        count = scraper.scrape_events(db, limit=limit, max_pages=max_pages)
        
        stats = db.get_statistics()
        print(f"\n📊 Current Database Status:")
        print(f"   Total events in database: {stats['total_events']}")
        print(f"   Unprocessed events: {stats['total_events'] - stats['processed_events']}")
        
        return count


def extract_speakers():
    """Step 2: Use AI to extract speakers from scraped events"""
    print("\n\n" + "🤖 STEP 2: EXTRACTING SPEAKERS WITH AI")
    print("="*70)
    
    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found!")
        print("   Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        return 0
    
    print("✓ API key loaded")
    
    with SpeakerDatabase() as db:
        # Get unprocessed events
        unprocessed = db.get_unprocessed_events()
        
        if not unprocessed:
            print("\n✓ All events have been processed!")
            return 0
        
        print(f"\nFound {len(unprocessed)} unprocessed event(s)")
        print("-"*70)
        
        # Initialize AI extractor
        extractor = SpeakerExtractor(api_key=api_key)
        
        # Process each event
        total_speakers = 0
        
        for event_id, url, title, body_text in unprocessed:
            print(f"\n📄 Processing Event ID {event_id}")
            print(f"   Title: {title[:70]}...")
            
            # Extract speakers using AI
            result = extractor.extract_speakers(title, body_text)
            
            if result['success']:
                speakers = result['speakers']
                print(f"   ✓ Found {len(speakers)} speaker(s)")
                
                # Save each speaker to database
                for speaker_data in speakers:
                    # Add speaker to speakers table
                    speaker_id = db.add_speaker(
                        name=speaker_data.get('name'),
                        title=speaker_data.get('title'),
                        affiliation=speaker_data.get('affiliation'),
                        primary_affiliation=speaker_data.get('primary_affiliation'),
                        bio=speaker_data.get('bio')
                    )
                    
                    # Link speaker to event
                    db.link_speaker_to_event(
                        event_id=event_id,
                        speaker_id=speaker_id,
                        role_in_event=speaker_data.get('role_in_event'),
                        extracted_info=json.dumps(speaker_data)
                    )
                    
                    print(f"     - {speaker_data.get('name')} ({speaker_data.get('role_in_event', 'participant')})")
                    total_speakers += 1
                
                # Mark event as processed
                db.mark_event_processed(event_id, 'completed')
                
            else:
                print(f"   ❌ Error: {result['error']}")
                db.mark_event_processed(event_id, 'failed')
        
        print("\n" + "="*70)
        print(f"✓ Extraction complete: {total_speakers} speaker records created")
        
        return total_speakers


def show_statistics():
    """Display database statistics and sample data"""
    print("\n\n" + "📊 DATABASE STATISTICS")
    print("="*70)
    
    with SpeakerDatabase() as db:
        stats = db.get_statistics()
        
        print(f"\nEvents:")
        print(f"  Total events: {stats['total_events']}")
        print(f"  Processed: {stats['processed_events']}")
        print(f"  Pending: {stats['total_events'] - stats['processed_events']}")
        
        print(f"\nSpeakers:")
        print(f"  Total unique speakers: {stats['total_speakers']}")
        print(f"  Total speaker-event connections: {stats['total_connections']}")
        
        # Show some sample speakers
        speakers = db.get_all_speakers()
        if speakers:
            print(f"\n📋 Sample Speakers (showing first 10):")
            print("-"*70)
            for speaker in speakers[:10]:
                speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker
                print(f"\n  {name}")
                if title:
                    print(f"    Title: {title}")
                if affiliation:
                    print(f"    Affiliation: {affiliation}")
                
                # Get events for this speaker
                events = db.get_speaker_events(speaker_id)
                if events:
                    print(f"    Events: {len(events)}")


def export_speakers_to_csv():
    """Export all speakers to a CSV file"""
    import csv
    from datetime import datetime
    
    print("\n\n" + "💾 EXPORTING SPEAKERS TO CSV")
    print("="*70)
    
    with SpeakerDatabase() as db:
        speakers = db.get_all_speakers()
        
        if not speakers:
            print("No speakers to export")
            return
        
        filename = f"speakers_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['ID', 'Name', 'Title', 'Affiliation', 'Bio', 'First Seen', 'Last Updated', 'Number of Events'])
            
            for speaker in speakers:
                speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker
                events = db.get_speaker_events(speaker_id)
                writer.writerow([speaker_id, name, title or '', affiliation or '', bio or '', first_seen, last_updated, len(events)])
        
        print(f"✓ Exported {len(speakers)} speakers to {filename}")


def main():
    """Main workflow"""
    parser = argparse.ArgumentParser(
        description='Asia Society Switzerland - Speaker Database Builder (Selenium Version)'
    )
    parser.add_argument('-e', '--events', type=str, default='5',
                        help='Number of events to scrape (number or "all", default: 5)')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode (default)')
    parser.add_argument('--no-headless', dest='headless', action='store_false',
                        help='Show browser window while scraping')
    parser.add_argument('--extract', action='store_true', default=True,
                        help='Extract speakers using AI (default)')
    parser.add_argument('--no-extract', dest='extract', action='store_false',
                        help='Skip speaker extraction')
    parser.add_argument('--export', action='store_true', default=False,
                        help='Export speakers to CSV')
    parser.add_argument('--skip-scrape', action='store_true', default=False,
                        help='Skip scraping, only run extraction/export on existing data')
    parser.add_argument('-p', '--pages', type=str, default='1',
                        help='Number of listing pages to scrape (number or "all", default: 1)')

    args = parser.parse_args()

    # Parse events limit
    if args.skip_scrape:
        limit = 0
    elif args.events.lower() == 'all':
        limit = None
    else:
        try:
            limit = int(args.events)
        except ValueError:
            limit = 5
            print(f"Invalid events value, using default: {limit}")

    # Parse pages limit
    if args.pages.lower() == 'all':
        max_pages = None
    else:
        try:
            max_pages = int(args.pages)
        except ValueError:
            max_pages = 1
            print(f"Invalid pages value, using default: {max_pages}")

    print("="*70)
    print("ASIA SOCIETY SWITZERLAND - SPEAKER DATABASE BUILDER")
    print("(Selenium Version - bypasses 403 errors)")
    print("="*70)

    print("\nThis tool will:")
    print("1. Scrape event pages using Selenium (real browser)")
    print("2. Use AI to extract speaker information")
    print("3. Store everything in a SQLite database")

    print("\n" + "-"*70)
    print("NOTE: This requires Chrome browser to be installed.")
    print("-"*70)

    # Step 1: Scrape events
    if args.skip_scrape:
        print("\nSkipping scraping (--skip-scrape)")
        scraped = 0
    else:
        scraped = scrape_events(limit=limit, headless=args.headless, max_pages=max_pages)
        if scraped == 0:
            print("\n⚠ No new events were scraped.")

    # Step 2: Extract speakers
    if args.extract:
        extract_speakers()
    else:
        print("\nSkipping speaker extraction.")

    # Show results
    show_statistics()

    # Export option
    if args.export:
        export_speakers_to_csv()

    print("\n" + "="*70)
    print("✓ COMPLETE")
    print("="*70)
    print(f"\nDatabase saved as: speakers.db")
    print("You can:")
    print("  - Run this script again to scrape more events")
    print("  - View the database with SQLite browser")
    print("  - Use the database for further analysis")


if __name__ == "__main__":
    main()
