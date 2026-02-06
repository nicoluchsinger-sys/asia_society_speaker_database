"""
Generate embeddings for all speakers in the database
Uses Voyage AI to create semantic embeddings for search
"""

import argparse
from database import SpeakerDatabase
from embedding_engine import EmbeddingEngine
from datetime import datetime
import time


def generate_embeddings(batch_size=50, limit=None, provider='openai', verbose=True, db_path=None):
    """
    Generate embeddings for all speakers without embeddings

    Args:
        batch_size: Number of speakers to process in each batch
        limit: Maximum number of speakers to process (None = all)
        provider: Embedding provider ('openai' default, 'gemini', or 'voyage')
        verbose: Print progress messages
        db_path: Path to database (None = auto-detect Railway vs local)
    """
    # Auto-detect database path if not provided
    if db_path is None:
        import os
        if os.path.exists('/data'):
            db_path = '/data/speakers.db'
        else:
            db_path = 'speakers.db'

    # Get speakers list first, then close connection to avoid locking
    db = SpeakerDatabase(db_path)
    speakers_data = db.get_speakers_without_embeddings()

    # Pre-fetch tags for all speakers to avoid repeated connections
    speakers_with_tags = []
    for speaker_data in speakers_data:
        speaker_id = speaker_data[0]
        tags = db.get_speaker_tags(speaker_id)
        speakers_with_tags.append((speaker_data, tags))

    db.close()  # Close initial connection

    # Try to initialize engine with preferred provider, fall back if needed
    try:
        engine = EmbeddingEngine(provider=provider)
    except Exception as e:
        if verbose:
            print(f"⚠ {provider} failed: {e}")
            if provider == 'gemini':
                print("Falling back to OpenAI...")
                provider = 'openai'
            elif provider == 'openai':
                print("Falling back to Voyage...")
                provider = 'voyage'
            else:
                raise
        engine = EmbeddingEngine(provider=provider)

    if limit:
        speakers_with_tags = speakers_with_tags[:limit]

    if not speakers_with_tags:
        if verbose:
            print("✓ All speakers already have embeddings!")
        return

    total = len(speakers_with_tags)
    if verbose:
        print(f"Generating embeddings for {total} speakers")
        print(f"Batch size: {batch_size}")
        print("=" * 60)

    start_time = time.time()
    total_tokens = 0
    processed = 0

    # Process in batches
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = speakers_with_tags[batch_start:batch_end]

        if verbose:
            print(f"\nProcessing batch {batch_start//batch_size + 1} ({batch_start+1}-{batch_end}/{total})...")

        # Prepare batch data
        batch_speakers = []
        batch_texts = []

        for speaker_data, tags in batch:
            speaker_id, name, title, affiliation, primary_affiliation, bio = speaker_data

            # Build speaker dict
            speaker = {
                'speaker_id': speaker_id,
                'name': name,
                'title': title,
                'affiliation': affiliation,
                'primary_affiliation': primary_affiliation,
                'bio': bio,
                'tags': tags
            }

            # Build embedding text
            text = engine.build_embedding_text(speaker)

            batch_speakers.append(speaker)
            batch_texts.append(text)

        # Generate embeddings for batch
        try:
            embeddings = engine.generate_embeddings_batch(batch_texts)

            # Open fresh database connection for saving (prevents locking issues)
            save_db = SpeakerDatabase(db_path)
            try:
                # Save to database
                for speaker, embedding, text in zip(batch_speakers, embeddings, batch_texts):
                    embedding_blob = engine.serialize_embedding(embedding)
                    save_db.save_speaker_embedding(
                        speaker['speaker_id'],
                        embedding_blob,
                        text,
                        model=engine.model
                    )
            finally:
                save_db.close()  # Always close connection after batch

            # Track usage
            usage = engine.get_last_usage()
            if usage:
                total_tokens += usage['total_tokens']

            processed += len(batch)

            if verbose:
                print(f"  ✓ Generated {len(embeddings)} embeddings")
                if usage:
                    print(f"  Tokens: {usage['total_tokens']}")

        except Exception as e:
            if verbose:
                print(f"  ✗ Error processing batch: {e}")
            continue

    elapsed = time.time() - start_time

    # Print summary
    if verbose:
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Speakers processed: {processed}/{total}")
        print(f"Total tokens used: {total_tokens:,}")

        # Calculate cost based on provider
        if engine.provider == 'gemini':
            print(f"Estimated cost: FREE (Gemini)")
        elif engine.provider == 'openai':
            cost = (total_tokens / 1_000_000) * 0.02
            print(f"Estimated cost: ${cost:.4f} (OpenAI)")
        elif engine.provider == 'voyage':
            cost = (total_tokens / 1_000_000) * 0.06
            print(f"Estimated cost: ${cost:.4f} (Voyage)")

        print(f"Time elapsed: {elapsed:.1f}s")
        print(f"Avg time per speaker: {elapsed/processed:.2f}s" if processed > 0 else "")

        # Check database stats (open fresh connection)
        db = SpeakerDatabase()
        total_with_embeddings = db.count_embeddings()
        total_speakers_query = db.get_statistics()['total_speakers']
        db.close()
        print(f"\nTotal speakers with embeddings: {total_with_embeddings}/{total_speakers_query}")

        print("\n✓ Embedding generation complete!")


def regenerate_all_embeddings(batch_size=50, provider='openai', verbose=True):
    """
    Regenerate embeddings for ALL speakers (even those with existing embeddings)
    WARNING: This will overwrite existing embeddings!
    """
    # Get speakers list first, then close connection to avoid locking
    db = SpeakerDatabase()
    speakers_data = db.get_all_speakers()

    # Pre-fetch tags for all speakers to avoid repeated connections
    speakers_with_tags = []
    for speaker_data in speakers_data:
        speaker_id = speaker_data[0]
        tags = db.get_speaker_tags(speaker_id)
        speakers_with_tags.append((speaker_data, tags))

    db.close()  # Close initial connection

    # Try to initialize engine with preferred provider, fall back if needed
    try:
        engine = EmbeddingEngine(provider=provider)
    except Exception as e:
        if verbose:
            print(f"⚠ {provider} failed: {e}")
            if provider == 'gemini':
                print("Falling back to OpenAI...")
                provider = 'openai'
            elif provider == 'openai':
                print("Falling back to Voyage...")
                provider = 'voyage'
            else:
                raise
        engine = EmbeddingEngine(provider=provider)

    if not speakers_with_tags:
        if verbose:
            print("No speakers found in database!")
        return

    total = len(speakers_with_tags)
    if verbose:
        print(f"Regenerating embeddings for {total} speakers")
        print("WARNING: This will overwrite existing embeddings!")
        print("=" * 60)

    start_time = time.time()
    total_tokens = 0
    processed = 0

    # Process in batches
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = speakers_with_tags[batch_start:batch_end]

        if verbose:
            print(f"\nProcessing batch {batch_start//batch_size + 1} ({batch_start+1}-{batch_end}/{total})...")

        # Prepare batch data
        batch_speakers = []
        batch_texts = []

        for speaker_data, tags in batch:
            speaker_id, name, title, affiliation, bio, first_seen, last_updated = speaker_data

            # Build speaker dict
            speaker = {
                'speaker_id': speaker_id,
                'name': name,
                'title': title,
                'affiliation': affiliation,
                'bio': bio,
                'tags': tags
            }

            # Build embedding text
            text = engine.build_embedding_text(speaker)

            batch_speakers.append(speaker)
            batch_texts.append(text)

        # Generate embeddings for batch
        try:
            embeddings = engine.generate_embeddings_batch(batch_texts)

            # Open fresh database connection for saving (prevents locking issues)
            save_db = SpeakerDatabase(db_path)
            try:
                # Save to database
                for speaker, embedding, text in zip(batch_speakers, embeddings, batch_texts):
                    embedding_blob = engine.serialize_embedding(embedding)
                    save_db.save_speaker_embedding(
                        speaker['speaker_id'],
                        embedding_blob,
                        text,
                        model=engine.model
                    )
            finally:
                save_db.close()  # Always close connection after batch

            # Track usage
            usage = engine.get_last_usage()
            if usage:
                total_tokens += usage['total_tokens']

            processed += len(batch)

            if verbose:
                print(f"  ✓ Generated {len(embeddings)} embeddings")
                if usage:
                    print(f"  Tokens: {usage['total_tokens']}")

        except Exception as e:
            if verbose:
                print(f"  ✗ Error processing batch: {e}")
            continue

    elapsed = time.time() - start_time

    # Print summary
    if verbose:
        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Speakers processed: {processed}/{total}")
        print(f"Total tokens used: {total_tokens:,}")

        # Calculate cost based on provider
        if engine.provider == 'gemini':
            print(f"Estimated cost: FREE (Gemini)")
        elif engine.provider == 'openai':
            cost = (total_tokens / 1_000_000) * 0.02
            print(f"Estimated cost: ${cost:.4f} (OpenAI)")
        elif engine.provider == 'voyage':
            cost = (total_tokens / 1_000_000) * 0.06
            print(f"Estimated cost: ${cost:.4f} (Voyage)")

        print(f"Time elapsed: {elapsed:.1f}s")

        print("\n✓ Embedding regeneration complete!")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate embeddings for speaker search')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Number of speakers to process in each batch (default: 50)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum number of speakers to process (default: all)')
    parser.add_argument('--provider', type=str, default='openai',
                       choices=['gemini', 'openai', 'voyage'],
                       help='Embedding provider: openai (default, $0.02/1M), gemini (free), voyage ($0.06/1M)')
    parser.add_argument('--regenerate', action='store_true',
                       help='Regenerate ALL embeddings (overwrite existing)')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress progress messages')

    args = parser.parse_args()

    verbose = not args.quiet

    if args.regenerate:
        response = input("WARNING: This will regenerate ALL embeddings and overwrite existing ones. Continue? (yes/no): ")
        if response.lower() == 'yes':
            regenerate_all_embeddings(
                batch_size=args.batch_size,
                provider=args.provider,
                verbose=verbose
            )
        else:
            print("Regeneration cancelled.")
    else:
        generate_embeddings(
            batch_size=args.batch_size,
            limit=args.limit,
            provider=args.provider,
            verbose=verbose
        )
