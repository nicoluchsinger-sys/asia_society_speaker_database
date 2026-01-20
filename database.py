"""
Database management for Asia Society events and speakers
"""

import sqlite3
from datetime import datetime
import json

class SpeakerDatabase:
    def __init__(self, db_path='speakers.db'):
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # Events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                event_date TEXT,
                location TEXT,
                body_text TEXT,
                raw_html TEXT,
                scraped_at TEXT,
                processed_at TEXT,
                processing_status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Speakers table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS speakers (
                speaker_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                title TEXT,
                affiliation TEXT,
                bio TEXT,
                first_seen TEXT,
                last_updated TEXT,
                UNIQUE(name, affiliation)
            )
        ''')
        
        # Event-Speaker relationship table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS event_speakers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                speaker_id INTEGER,
                role_in_event TEXT,
                extracted_info TEXT,
                FOREIGN KEY (event_id) REFERENCES events(event_id),
                FOREIGN KEY (speaker_id) REFERENCES speakers(speaker_id),
                UNIQUE(event_id, speaker_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_event(self, url, title, body_text, raw_html=None, event_date=None, location='Switzerland'):
        """Add a new event to the database"""
        cursor = self.conn.cursor()
        scraped_at = datetime.now().isoformat()
        
        try:
            cursor.execute('''
                INSERT INTO events (url, title, event_date, location, body_text, raw_html, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (url, title, event_date, location, body_text, raw_html, scraped_at))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Event already exists
            cursor.execute('SELECT event_id FROM events WHERE url = ?', (url,))
            return cursor.fetchone()[0]
    
    def get_unprocessed_events(self):
        """Get all events that haven't been processed for speaker extraction yet"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT event_id, url, title, body_text 
            FROM events 
            WHERE processing_status = 'pending'
        ''')
        return cursor.fetchall()
    
    def add_speaker(self, name, title=None, affiliation=None, bio=None):
        """Add a speaker or return existing speaker_id"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        try:
            cursor.execute('''
                INSERT INTO speakers (name, title, affiliation, bio, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, title, affiliation, bio, now, now))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Speaker already exists, get their ID
            cursor.execute('''
                SELECT speaker_id FROM speakers 
                WHERE name = ? AND (affiliation = ? OR (affiliation IS NULL AND ? IS NULL))
            ''', (name, affiliation, affiliation))
            result = cursor.fetchone()
            if result:
                # Update last_updated
                cursor.execute('''
                    UPDATE speakers SET last_updated = ? WHERE speaker_id = ?
                ''', (now, result[0]))
                self.conn.commit()
                return result[0]
    
    def link_speaker_to_event(self, event_id, speaker_id, role_in_event=None, extracted_info=None):
        """Link a speaker to an event"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO event_speakers (event_id, speaker_id, role_in_event, extracted_info)
                VALUES (?, ?, ?, ?)
            ''', (event_id, speaker_id, role_in_event, extracted_info))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Link already exists, update it
            cursor.execute('''
                UPDATE event_speakers 
                SET role_in_event = ?, extracted_info = ?
                WHERE event_id = ? AND speaker_id = ?
            ''', (role_in_event, extracted_info, event_id, speaker_id))
            self.conn.commit()
    
    def mark_event_processed(self, event_id, status='completed'):
        """Mark an event as processed"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE events 
            SET processing_status = ?, processed_at = ?
            WHERE event_id = ?
        ''', (status, datetime.now().isoformat(), event_id))
        self.conn.commit()
    
    def get_all_speakers(self):
        """Get all speakers from database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT speaker_id, name, title, affiliation, bio, first_seen, last_updated
            FROM speakers
            ORDER BY name
        ''')
        return cursor.fetchall()
    
    def get_speaker_events(self, speaker_id):
        """Get all events for a specific speaker"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT e.event_id, e.title, e.event_date, e.url, es.role_in_event
            FROM events e
            JOIN event_speakers es ON e.event_id = es.event_id
            WHERE es.speaker_id = ?
            ORDER BY e.event_date DESC
        ''', (speaker_id,))
        return cursor.fetchall()
    
    def get_event_speakers(self, event_id):
        """Get all speakers for a specific event"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT s.speaker_id, s.name, s.title, s.affiliation, es.role_in_event
            FROM speakers s
            JOIN event_speakers es ON s.speaker_id = es.speaker_id
            WHERE es.event_id = ?
        ''', (event_id,))
        return cursor.fetchall()
    
    def get_statistics(self):
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        cursor.execute('SELECT COUNT(*) FROM events')
        stats['total_events'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM events WHERE processing_status = "completed"')
        stats['processed_events'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM speakers')
        stats['total_speakers'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM event_speakers')
        stats['total_connections'] = cursor.fetchone()[0]
        
        return stats
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
