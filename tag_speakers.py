"""
Standalone script to tag speakers with topical expertise tags AND enrich their profiles

Enrichment includes:
- Expertise tags (3 per speaker with confidence scores)
- Updated job titles (from web search if more current)
- Enriched biographies (from web search if more comprehensive)
"""

import os
import argparse
from database import SpeakerDatabase
from speaker_tagger import SpeakerTagger


def load_api_key():
    """Load API key from .env file or environment"""
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ANTHROPIC_API_KEY='):
                    key = line.split('=', 1)[1].strip()
                    os.environ['ANTHROPIC_API_KEY'] = key
                    return key

    return os.getenv('ANTHROPIC_API_KEY')


def tag_speakers(limit=None, retag=False):
    """Tag speakers with expertise tags AND enrich profiles using web search and Claude AI"""
    print("\n" + "="*70)
    print("🏷️  SPEAKER TAGGING & ENRICHMENT MODULE")
    print("="*70)

    # Load API key
    api_key = load_api_key()
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found!")
        print("   Please create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        return

    print("✓ API key loaded")

    # Determine database path - use /data/speakers.db on Railway
    db_path = '/data/speakers.db' if os.path.exists('/data') else 'speakers.db'
    print(f"Using database: {db_path}")

    with SpeakerDatabase(db_path) as db:
        # Reset tagging status if retag is requested
        if retag:
            print("\n⚠️  Resetting tagging status for all speakers...")
            db.reset_speaker_tagging_status()
            print("✓ All speakers reset to pending")

        # Get statistics
        stats = db.get_statistics()
        untagged = db.get_untagged_speakers()

        print(f"\n📊 Current Status:")
        print(f"   Total speakers: {stats['total_speakers']}")
        print(f"   Already tagged: {stats['tagged_speakers']}")
        print(f"   Untagged: {len(untagged)}")

        if not untagged:
            print("\n✓ All speakers have been tagged!")
            return

        if limit:
            print(f"\n🔢 Limiting to {limit} speaker(s)")

        print("\n" + "-"*70)
        print("Starting tagging & enrichment process...")
        print("(Web search + Claude AI for tags, bio, and title)")
        print("-"*70)

        # Initialize tagger
        tagger = SpeakerTagger(api_key=api_key)

        # Tag speakers
        results = tagger.tag_all_speakers(db, limit=limit)

        # Print summary
        print("\n" + "="*70)
        print("📊 TAGGING SUMMARY")
        print("="*70)
        print(f"   Total processed: {results['total_processed']}")
        print(f"   Successful: {results['successful']}")
        print(f"   Failed: {results['failed']}")

        # Show updated statistics
        stats = db.get_statistics()
        print(f"\n📊 Updated Database Status:")
        print(f"   Total speakers: {stats['total_speakers']}")
        print(f"   Tagged speakers: {stats['tagged_speakers']}")
        print(f"   Total tags: {stats['total_tags']}")


def show_tagged_speakers():
    """Display all tagged speakers and their tags"""
    print("\n" + "="*70)
    print("📋 TAGGED SPEAKERS")
    print("="*70)

    with SpeakerDatabase() as db:
        speakers = db.get_all_speakers()

        for speaker in speakers:
            speaker_id = speaker[0]
            name = speaker[1]
            tags = db.get_speaker_tags(speaker_id)

            if tags:
                tags_str = ', '.join([t[0] for t in tags])
                print(f"\n  {name}")
                print(f"    Tags: {tags_str}")


def main():
    parser = argparse.ArgumentParser(
        description='Tag speakers with expertise tags AND enrich profiles (bio, title) using web search and AI'
    )
    parser.add_argument('-l', '--limit', type=int, default=None,
                        help='Limit number of speakers to tag/enrich')
    parser.add_argument('--retag', action='store_true', default=False,
                        help='Reset and re-tag/re-enrich ALL speakers (overwrites existing tags and enrichment)')
    parser.add_argument('--show', action='store_true', default=False,
                        help='Show all tagged speakers and exit')

    args = parser.parse_args()

    if args.show:
        show_tagged_speakers()
    else:
        tag_speakers(limit=args.limit, retag=args.retag)

    print("\n✓ Done")


if __name__ == "__main__":
    main()
