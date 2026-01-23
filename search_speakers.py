"""
CLI interface for natural language speaker search
"""

import argparse
from speaker_search import SpeakerSearch
from database import SpeakerDatabase


def format_speaker_result(speaker: dict, index: int, show_explanation: bool = False) -> str:
    """
    Format a speaker search result for display

    Args:
        speaker: Speaker dictionary with search results
        index: Result position (1-indexed)
        show_explanation: Include match explanations

    Returns:
        Formatted string for display
    """
    lines = []

    # Header with name and score
    lines.append(f"\n{index}. {speaker['name']} (Score: {speaker['score']:.2f})")

    # Title and affiliation
    if speaker.get('title') and speaker.get('affiliation'):
        lines.append(f"   {speaker['title']}, {speaker['affiliation']}")
    elif speaker.get('title'):
        lines.append(f"   {speaker['title']}")
    elif speaker.get('affiliation'):
        lines.append(f"   {speaker['affiliation']}")

    # Tags
    tags = speaker.get('tags', [])
    if tags:
        # Show top 5 tags with confidence scores
        top_tags = tags[:5]
        tag_strs = [f"{tag[0]} ({tag[1]:.2f})" for tag in top_tags]
        lines.append(f"   Tags: {', '.join(tag_strs)}")

    # Event count
    event_count = speaker.get('event_count', 0)
    if event_count:
        lines.append(f"   Speaking engagements: {event_count}")

    # Bio excerpt (first 150 chars)
    bio = speaker.get('bio', '')
    if bio:
        bio_excerpt = bio[:150] + ('...' if len(bio) > 150 else '')
        lines.append(f"   Bio: {bio_excerpt}")

    # Explanation (if requested)
    if show_explanation and speaker.get('explanation'):
        lines.append(f"   Match reasons: {', '.join(speaker['explanation'])}")

    return '\n'.join(lines)


def search_command(args):
    """Execute search command"""
    search = SpeakerSearch(provider='openai')

    try:
        # Perform search
        results = search.search(
            args.query,
            top_k=args.limit,
            explain=args.explain
        )

        # Display results
        print("\n" + "=" * 70)
        print(f"Search Results for: \"{args.query}\"")
        print("=" * 70)

        if not results:
            print("\nNo speakers found matching your query.")
            print("\nTips:")
            print("  - Try using different keywords")
            print("  - Make your query more general")
            print("  - Check if embeddings have been generated (run generate_embeddings.py)")
            return

        print(f"\nFound {len(results)} speaker(s)")

        for i, speaker in enumerate(results, 1):
            print(format_speaker_result(speaker, i, args.explain))

        print("\n" + "=" * 70)

        # Show statistics if requested
        if args.stats:
            db = SpeakerDatabase()
            db_stats = db.get_statistics()
            db.close()

            print("\nDatabase Statistics:")
            print(f"  Total speakers: {db_stats['total_speakers']}")
            print(f"  Tagged speakers: {db_stats['tagged_speakers']}")
            print(f"  Total events: {db_stats['total_events']}")

    except Exception as e:
        print(f"\nError: {e}")
        print("\nPlease ensure:")
        print("  1. Embeddings have been generated (run generate_embeddings.py)")
        print("  2. Your ANTHROPIC_API_KEY is set in .env")
        print("  3. Your VOYAGE_API_KEY is set in .env")

    finally:
        search.close()


def list_command(args):
    """List all speakers (optionally filtered)"""
    db = SpeakerDatabase()

    try:
        speakers = db.get_all_speakers()

        print("\n" + "=" * 70)
        print(f"All Speakers ({len(speakers)} total)")
        print("=" * 70)

        for speaker_id, name, title, affiliation, bio, first_seen, last_updated in speakers[:args.limit]:
            print(f"\n{name}")
            if title and affiliation:
                print(f"  {title}, {affiliation}")
            elif title:
                print(f"  {title}")
            elif affiliation:
                print(f"  {affiliation}")

            # Get tags
            tags = db.get_speaker_tags(speaker_id)
            if tags:
                top_tags = tags[:3]
                tag_strs = [f"{tag[0]} ({tag[1]:.2f})" for tag in top_tags]
                print(f"  Tags: {', '.join(tag_strs)}")

        if len(speakers) > args.limit:
            print(f"\n... and {len(speakers) - args.limit} more")

        print("\n" + "=" * 70)

    finally:
        db.close()


def speaker_command(args):
    """Show detailed information about a specific speaker"""
    db = SpeakerDatabase()

    try:
        # Search by name or ID
        if args.speaker_id:
            speaker_data = db.get_speaker_by_id(args.speaker_id)
            if not speaker_data:
                print(f"\nNo speaker found with ID: {args.speaker_id}")
                return
            speaker_id = args.speaker_id
        else:
            # Search by name
            speakers = db.get_all_speakers()
            matches = [s for s in speakers if args.name.lower() in s[1].lower()]

            if not matches:
                print(f"\nNo speaker found matching: {args.name}")
                return

            if len(matches) > 1:
                print(f"\nMultiple speakers found matching '{args.name}':")
                for i, (sid, name, title, affiliation, _, _, _) in enumerate(matches, 1):
                    print(f"{i}. {name}")
                    if title or affiliation:
                        print(f"   {title or ''}{', ' + affiliation if affiliation else ''}")
                print("\nPlease be more specific or use --id")
                return

            speaker_data = db.get_speaker_by_id(matches[0][0])
            speaker_id = matches[0][0]

        # Display detailed information
        speaker_id, name, title, affiliation, primary_affiliation, bio = speaker_data

        print("\n" + "=" * 70)
        print(f"Speaker Details: {name}")
        print("=" * 70)

        print(f"\nID: {speaker_id}")
        if title:
            print(f"Title: {title}")
        if affiliation:
            print(f"Affiliation: {affiliation}")
        if bio:
            print(f"\nBio: {bio}")

        # Tags
        tags = db.get_speaker_tags(speaker_id)
        if tags:
            print(f"\nExpertise Tags ({len(tags)}):")
            for tag_text, confidence, source, created_at in tags:
                print(f"  - {tag_text} (confidence: {confidence:.2f})")

        # Events
        events = db.get_speaker_events(speaker_id)
        if events:
            print(f"\nSpeaking Engagements ({len(events)}):")
            for event_id, event_title, event_date, event_url, role in events[:10]:
                print(f"  - {event_title}")
                if event_date:
                    print(f"    Date: {event_date}")
                if role:
                    print(f"    Role: {role}")

            if len(events) > 10:
                print(f"  ... and {len(events) - 10} more")

        # Demographics (if available)
        demographics = db.get_speaker_demographics(speaker_id)
        if demographics:
            gender, gender_conf, nationality, nationality_conf, birth_year, enriched_at = demographics
            print(f"\nDemographics:")
            if gender:
                print(f"  Gender: {gender} (confidence: {gender_conf:.2f})")
            if nationality:
                print(f"  Nationality: {nationality} (confidence: {nationality_conf:.2f})")
            if birth_year:
                print(f"  Birth year: {birth_year}")

        # Locations (if available)
        locations = db.get_speaker_locations(speaker_id)
        if locations:
            print(f"\nLocations:")
            for loc_id, loc_type, city, country, region, is_primary, confidence, source, created_at in locations:
                loc_str = f"  - {loc_type}"
                if city:
                    loc_str += f": {city}"
                if country:
                    loc_str += f", {country}"
                if region:
                    loc_str += f" ({region})"
                if is_primary:
                    loc_str += " [PRIMARY]"
                print(loc_str)

        # Languages (if available)
        languages = db.get_speaker_languages(speaker_id)
        if languages:
            print(f"\nLanguages:")
            for language, proficiency, confidence, source, created_at in languages:
                lang_str = f"  - {language}"
                if proficiency:
                    lang_str += f" ({proficiency})"
                print(lang_str)

        print("\n" + "=" * 70)

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Natural language speaker search for Asia Society database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python search_speakers.py "3 speakers on chinese economy, ideally women based in Europe"
  python search_speakers.py "climate policy experts" --limit 10
  python search_speakers.py "technology policy specialists" --explain
  python search_speakers.py --list
  python search_speakers.py --speaker "Jane Doe"
        """
    )

    # Search command (default)
    parser.add_argument('query', nargs='?', help='Natural language search query')
    parser.add_argument('--limit', type=int, default=10,
                       help='Maximum number of results to return (default: 10)')
    parser.add_argument('--explain', action='store_true',
                       help='Show explanation of why each speaker matched')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')

    # List command
    parser.add_argument('--list', action='store_true',
                       help='List all speakers')

    # Speaker detail command
    parser.add_argument('--speaker', dest='name', type=str,
                       help='Show details for a specific speaker by name')
    parser.add_argument('--id', dest='speaker_id', type=int,
                       help='Show details for a specific speaker by ID')

    args = parser.parse_args()

    # Route to appropriate command
    if args.list:
        list_command(args)
    elif args.name or args.speaker_id:
        speaker_command(args)
    elif args.query:
        search_command(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
