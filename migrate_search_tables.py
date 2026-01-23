"""
Database migration script for natural language search system
Adds tables for embeddings, demographics, locations, languages, and freshness tracking
"""

import sqlite3
from datetime import datetime

def migrate_database(db_path='speakers.db', verbose=True):
    """
    Run migration to add new tables for search functionality
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    migrations = []

    # Migration 1: Speaker embeddings table
    migrations.append({
        'name': 'speaker_embeddings',
        'sql': '''
            CREATE TABLE IF NOT EXISTS speaker_embeddings (
                speaker_id INTEGER PRIMARY KEY,
                embedding_model TEXT NOT NULL DEFAULT 'voyage-3',
                embedding BLOB NOT NULL,
                embedding_text TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        '''
    })

    # Migration 2: Speaker demographics table
    migrations.append({
        'name': 'speaker_demographics',
        'sql': '''
            CREATE TABLE IF NOT EXISTS speaker_demographics (
                speaker_id INTEGER PRIMARY KEY,
                gender TEXT,
                gender_confidence REAL,
                nationality TEXT,
                nationality_confidence REAL,
                birth_year INTEGER,
                enriched_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        '''
    })

    # Migration 3: Speaker locations table
    migrations.append({
        'name': 'speaker_locations',
        'sql': '''
            CREATE TABLE IF NOT EXISTS speaker_locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_id INTEGER NOT NULL,
                location_type TEXT NOT NULL,
                city TEXT,
                country TEXT,
                region TEXT,
                is_primary BOOLEAN DEFAULT 0,
                confidence REAL,
                source TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        '''
    })

    # Migration 4: Speaker languages table
    migrations.append({
        'name': 'speaker_languages',
        'sql': '''
            CREATE TABLE IF NOT EXISTS speaker_languages (
                language_id INTEGER PRIMARY KEY AUTOINCREMENT,
                speaker_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                proficiency TEXT,
                confidence REAL,
                source TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE,
                UNIQUE(speaker_id, language)
            )
        '''
    })

    # Migration 5: Speaker freshness tracking table
    migrations.append({
        'name': 'speaker_freshness',
        'sql': '''
            CREATE TABLE IF NOT EXISTS speaker_freshness (
                speaker_id INTEGER PRIMARY KEY,
                last_enrichment_date TEXT,
                staleness_score REAL DEFAULT 0.0,
                needs_refresh BOOLEAN DEFAULT 0,
                priority_score REAL DEFAULT 0.0,
                next_refresh_date TEXT,
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id) ON DELETE CASCADE
            )
        '''
    })

    # Execute migrations
    for migration in migrations:
        if verbose:
            print(f"Creating table: {migration['name']}")

        cursor.execute(migration['sql'])
        conn.commit()

        if verbose:
            # Check if table was created successfully
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{migration['name']}'")
            if cursor.fetchone():
                print(f"  ✓ Table {migration['name']} created successfully")
            else:
                print(f"  ✗ Table {migration['name']} already existed or failed to create")

    # Create indexes for better query performance
    indexes = [
        ('idx_embeddings_speaker', 'speaker_embeddings', 'speaker_id'),
        ('idx_demographics_speaker', 'speaker_demographics', 'speaker_id'),
        ('idx_locations_speaker', 'speaker_locations', 'speaker_id'),
        ('idx_locations_primary', 'speaker_locations', 'is_primary'),
        ('idx_languages_speaker', 'speaker_languages', 'speaker_id'),
        ('idx_freshness_needs_refresh', 'speaker_freshness', 'needs_refresh'),
        ('idx_freshness_priority', 'speaker_freshness', 'priority_score'),
    ]

    if verbose:
        print("\nCreating indexes for performance...")

    for idx_name, table_name, column_name in indexes:
        try:
            cursor.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name}({column_name})')
            if verbose:
                print(f"  ✓ Index {idx_name} created")
        except sqlite3.Error as e:
            if verbose:
                print(f"  ✗ Index {idx_name} failed: {e}")

    conn.commit()

    # Print summary
    if verbose:
        print("\n" + "="*50)
        print("Migration Summary")
        print("="*50)

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"\nTotal tables in database: {len(tables)}")
        print("\nNew search-related tables:")
        search_tables = [t for t in tables if t in ['speaker_embeddings', 'speaker_demographics',
                                                      'speaker_locations', 'speaker_languages',
                                                      'speaker_freshness']]
        for table in search_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count} records")

        print("\n✓ Migration completed successfully!")

    conn.close()

def rollback_migration(db_path='speakers.db', verbose=True):
    """
    Rollback migration - drop all search-related tables
    WARNING: This will delete all search data!
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables_to_drop = [
        'speaker_freshness',
        'speaker_languages',
        'speaker_locations',
        'speaker_demographics',
        'speaker_embeddings'
    ]

    if verbose:
        print("Rolling back migration - dropping tables...")

    for table in tables_to_drop:
        try:
            cursor.execute(f'DROP TABLE IF EXISTS {table}')
            if verbose:
                print(f"  ✓ Dropped table: {table}")
        except sqlite3.Error as e:
            if verbose:
                print(f"  ✗ Failed to drop {table}: {e}")

    conn.commit()
    conn.close()

    if verbose:
        print("\n✓ Rollback completed!")

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--rollback':
        response = input("WARNING: This will delete all search data. Are you sure? (yes/no): ")
        if response.lower() == 'yes':
            rollback_migration()
        else:
            print("Rollback cancelled.")
    else:
        migrate_database()
