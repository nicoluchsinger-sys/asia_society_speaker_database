"""
Pipeline monitoring and health check module

Provides real-time metrics and health indicators for the speaker database pipeline.
Used by the web dashboard to display pipeline status, backlog trends, and error patterns.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from database import SpeakerDatabase
import os


class PipelineMonitor:
    """
    Monitor pipeline health and provide diagnostic metrics
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize monitor with database connection

        Args:
            db_path: Path to database (None = auto-detect Railway vs local)
        """
        if db_path is None:
            db_path = '/data/speakers.db' if os.path.exists('/data') else 'speakers.db'
        self.db_path = db_path

    def get_health_status(self) -> Dict:
        """
        Get overall pipeline health status

        Returns:
            dict: Health indicators including status, warnings, and critical issues
        """
        db = SpeakerDatabase(self.db_path)
        cursor = db.conn.cursor()

        try:
            # Check pipeline lock status (if table exists)
            is_locked = False
            stale_lock = False
            try:
                cursor.execute('''
                    SELECT locked_at, locked_by
                    FROM pipeline_lock
                    WHERE id = 1 AND is_locked = 1
                ''')
                lock_row = cursor.fetchone()
                is_locked = lock_row is not None

                # Check for stale lock (locked > 30 min)
                if is_locked:
                    locked_at = datetime.fromisoformat(lock_row[0])
                    age_minutes = (datetime.utcnow() - locked_at).total_seconds() / 60
                    stale_lock = age_minutes > 30
            except sqlite3.OperationalError:
                # pipeline_lock table doesn't exist (local dev)
                pass

            # Get last pipeline run (handle both old and new schema)
            last_run = None
            try:
                # Try new schema first (started_at, completed_at, error_message)
                cursor.execute('''
                    SELECT started_at, completed_at, success, error_message
                    FROM pipeline_runs
                    ORDER BY started_at DESC
                    LIMIT 1
                ''')
                last_run = cursor.fetchone()
            except sqlite3.OperationalError:
                # Fall back to old schema (timestamp only, no error_message)
                cursor.execute('''
                    SELECT timestamp, timestamp, success, NULL
                    FROM pipeline_runs
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''')
                last_run = cursor.fetchone()

            last_run_status = None
            last_run_time = None
            time_since_last_run = None

            if last_run:
                last_run_time = last_run[1] or last_run[0]  # completed_at or started_at
                last_run_status = 'success' if last_run[2] else 'failed'
                if last_run_time:
                    last_run_dt = datetime.fromisoformat(last_run_time)
                    time_since_last_run = (datetime.utcnow() - last_run_dt).total_seconds() / 3600

            # Get backlog counts
            cursor.execute('SELECT COUNT(*) FROM events WHERE processing_status = "pending"')
            pending_events = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM events WHERE processing_status = "failed"')
            failed_events = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM speakers WHERE tagging_status IS NULL OR tagging_status = "pending"')
            pending_speakers = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM speakers WHERE tagging_status = "failed"')
            failed_speakers = cursor.fetchone()[0]

            # Determine overall health
            status = 'healthy'
            warnings = []
            critical = []

            if stale_lock:
                critical.append('Pipeline lock is stale (>30 min) - may need force unlock')
                status = 'critical'

            if last_run_status == 'failed':
                warnings.append('Last pipeline run failed')
                if status != 'critical':
                    status = 'warning'

            if time_since_last_run and time_since_last_run > 24:
                warnings.append(f'No pipeline run in {time_since_last_run:.1f} hours')
                if status != 'critical':
                    status = 'warning'

            if pending_events > 100:
                warnings.append(f'High pending event backlog: {pending_events}')
                if status != 'critical':
                    status = 'warning'

            if failed_events > 50:
                warnings.append(f'High failed event count: {failed_events}')
                if status != 'critical':
                    status = 'warning'

            return {
                'status': status,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'pipeline_locked': is_locked,
                'stale_lock': stale_lock,
                'last_run': {
                    'status': last_run_status,
                    'time': last_run_time,
                    'hours_ago': round(time_since_last_run, 1) if time_since_last_run else None
                },
                'backlog': {
                    'pending_events': pending_events,
                    'failed_events': failed_events,
                    'pending_speakers': pending_speakers,
                    'failed_speakers': failed_speakers
                },
                'warnings': warnings,
                'critical': critical
            }

        finally:
            db.close()

    def get_backlog_trends(self, days: int = 7) -> Dict:
        """
        Get backlog trends over time

        Args:
            days: Number of days to look back

        Returns:
            dict: Daily backlog counts and trends
        """
        db = SpeakerDatabase(self.db_path)
        cursor = db.conn.cursor()

        try:
            # Get current backlog
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN processing_status = 'pending' AND (extraction_attempts IS NULL OR extraction_attempts = 0) THEN 1 END) as pending_new,
                    COUNT(CASE WHEN processing_status = 'pending' AND extraction_attempts > 0 THEN 1 END) as pending_retries,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed
                FROM events
            ''')
            row = cursor.fetchone()
            current_events = {
                'pending_new': row[0],
                'pending_retries': row[1],
                'failed': row[2],
                'total_pending': row[0] + row[1]
            }

            # Get events by extraction attempts
            cursor.execute('''
                SELECT
                    COALESCE(extraction_attempts, 0) as attempts,
                    COUNT(*) as count
                FROM events
                WHERE processing_status = 'pending'
                GROUP BY attempts
                ORDER BY attempts
            ''')
            events_by_attempts = {row[0]: row[1] for row in cursor.fetchall()}

            # Get speaker backlog
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN tagging_status IS NULL OR tagging_status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN tagging_status = 'failed' THEN 1 END) as failed
                FROM speakers
            ''')
            row = cursor.fetchone()
            current_speakers = {
                'pending': row[0],
                'failed': row[1]
            }

            # Get historical trends from pipeline_runs (handle both schemas)
            since = datetime.utcnow() - timedelta(days=days)
            try:
                # Try new schema (started_at)
                cursor.execute('''
                    SELECT
                        DATE(started_at) as date,
                        AVG(events_scraped) as avg_scraped,
                        AVG(speakers_extracted) as avg_extracted,
                        COUNT(*) as runs
                    FROM pipeline_runs
                    WHERE started_at >= ?
                    GROUP BY DATE(started_at)
                    ORDER BY date DESC
                ''', (since.isoformat(),))
            except sqlite3.OperationalError:
                # Fall back to old schema (timestamp)
                cursor.execute('''
                    SELECT
                        DATE(timestamp) as date,
                        AVG(events_scraped) as avg_scraped,
                        AVG(speakers_extracted) as avg_extracted,
                        COUNT(*) as runs
                    FROM pipeline_runs
                    WHERE timestamp >= ?
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                ''', (since.isoformat(),))

            daily_stats = []
            for row in cursor.fetchall():
                daily_stats.append({
                    'date': row[0],
                    'avg_scraped': round(row[1], 1) if row[1] else 0,
                    'avg_extracted': round(row[2], 1) if row[2] else 0,
                    'runs': row[3]
                })

            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'current_events': current_events,
                'events_by_attempts': events_by_attempts,
                'current_speakers': current_speakers,
                'daily_stats': daily_stats
            }

        finally:
            db.close()

    def get_success_rates(self, hours: int = 24) -> Dict:
        """
        Calculate success rates for various pipeline operations

        Args:
            hours: Time window in hours

        Returns:
            dict: Success rates for extraction, enrichment, embedding
        """
        db = SpeakerDatabase(self.db_path)
        cursor = db.conn.cursor()

        try:
            since = datetime.utcnow() - timedelta(hours=hours)

            # Event extraction success rate (events marked completed vs failed recently)
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed
                FROM events
                WHERE last_processed_at >= ?
            ''', (since.isoformat(),))
            row = cursor.fetchone()
            extraction_completed = row[0]
            extraction_failed = row[1]
            extraction_total = extraction_completed + extraction_failed
            extraction_rate = (extraction_completed / extraction_total * 100) if extraction_total > 0 else None

            # Speaker enrichment success rate
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN tagging_status = 'completed' THEN 1 END) as completed,
                    COUNT(CASE WHEN tagging_status = 'failed' THEN 1 END) as failed
                FROM speakers
                WHERE last_updated >= ?
            ''', (since.isoformat(),))
            row = cursor.fetchone()
            enrichment_completed = row[0]
            enrichment_failed = row[1]
            enrichment_total = enrichment_completed + enrichment_failed
            enrichment_rate = (enrichment_completed / enrichment_total * 100) if enrichment_total > 0 else None

            # Embedding generation (speakers with embeddings vs total)
            cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_embeddings')
            speakers_with_embeddings = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM speakers')
            total_speakers = cursor.fetchone()[0]

            embedding_rate = (speakers_with_embeddings / total_speakers * 100) if total_speakers > 0 else 0

            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'time_window_hours': hours,
                'extraction': {
                    'success_rate': round(extraction_rate, 1) if extraction_rate is not None else None,
                    'completed': extraction_completed,
                    'failed': extraction_failed,
                    'total': extraction_total
                },
                'enrichment': {
                    'success_rate': round(enrichment_rate, 1) if enrichment_rate is not None else None,
                    'completed': enrichment_completed,
                    'failed': enrichment_failed,
                    'total': enrichment_total
                },
                'embeddings': {
                    'coverage_rate': round(embedding_rate, 1),
                    'speakers_with_embeddings': speakers_with_embeddings,
                    'total_speakers': total_speakers
                }
            }

        finally:
            db.close()

    def get_cost_metrics(self, days: int = 7) -> Dict:
        """
        Get cost metrics and trends

        Args:
            days: Number of days to look back

        Returns:
            dict: Cost metrics and trends
        """
        db = SpeakerDatabase(self.db_path)
        cursor = db.conn.cursor()

        try:
            since = datetime.utcnow() - timedelta(days=days)

            # Get cost trends from pipeline_runs (handle both schemas)
            try:
                # Try new schema (started_at)
                cursor.execute('''
                    SELECT
                        DATE(started_at) as date,
                        SUM(total_cost) as total_cost,
                        AVG(total_cost) as avg_cost,
                        COUNT(*) as runs
                    FROM pipeline_runs
                    WHERE started_at >= ? AND total_cost IS NOT NULL
                    GROUP BY DATE(started_at)
                    ORDER BY date DESC
                ''', (since.isoformat(),))
            except sqlite3.OperationalError:
                # Fall back to old schema (timestamp)
                cursor.execute('''
                    SELECT
                        DATE(timestamp) as date,
                        SUM(total_cost) as total_cost,
                        AVG(total_cost) as avg_cost,
                        COUNT(*) as runs
                    FROM pipeline_runs
                    WHERE timestamp >= ? AND total_cost IS NOT NULL
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                ''', (since.isoformat(),))

            daily_costs = []
            total_cost = 0
            for row in cursor.fetchall():
                cost = round(row[1], 4) if row[1] else 0
                total_cost += cost
                daily_costs.append({
                    'date': row[0],
                    'total_cost': cost,
                    'avg_per_run': round(row[2], 4) if row[2] else 0,
                    'runs': row[3]
                })

            # Get average cost per speaker/event (handle both schemas)
            try:
                # Try new schema (started_at, events_processed)
                cursor.execute('''
                    SELECT
                        AVG(CASE WHEN speakers_extracted > 0 THEN total_cost / speakers_extracted END) as cost_per_speaker,
                        AVG(CASE WHEN events_processed > 0 THEN total_cost / events_processed END) as cost_per_event
                    FROM pipeline_runs
                    WHERE started_at >= ? AND total_cost IS NOT NULL
                ''', (since.isoformat(),))
            except sqlite3.OperationalError:
                # Fall back to old schema (timestamp, use events_scraped instead of events_processed)
                cursor.execute('''
                    SELECT
                        AVG(CASE WHEN speakers_extracted > 0 THEN total_cost / speakers_extracted END) as cost_per_speaker,
                        AVG(CASE WHEN events_scraped > 0 THEN total_cost / events_scraped END) as cost_per_event
                    FROM pipeline_runs
                    WHERE timestamp >= ? AND total_cost IS NOT NULL
                ''', (since.isoformat(),))
            row = cursor.fetchone()

            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'days': days,
                'total_cost': round(total_cost, 4),
                'avg_cost_per_speaker': round(row[0], 4) if row[0] else None,
                'avg_cost_per_event': round(row[1], 4) if row[1] else None,
                'daily_costs': daily_costs
            }

        finally:
            db.close()

    def get_error_patterns(self, limit: int = 20) -> Dict:
        """
        Analyze error patterns and common failure modes

        Args:
            limit: Number of recent errors to analyze

        Returns:
            dict: Error patterns and statistics
        """
        db = SpeakerDatabase(self.db_path)
        cursor = db.conn.cursor()

        try:
            # Get recent failed events with error messages
            cursor.execute('''
                SELECT event_id, title, url, error_message, extraction_attempts, last_processed_at
                FROM events
                WHERE processing_status = 'failed'
                ORDER BY last_processed_at DESC
                LIMIT ?
            ''', (limit,))

            failed_events = []
            for row in cursor.fetchall():
                failed_events.append({
                    'event_id': row[0],
                    'title': row[1],
                    'url': row[2],
                    'error': row[3],
                    'attempts': row[4],
                    'last_attempt': row[5]
                })

            # Get events stuck in retry loop (3 attempts, still pending)
            cursor.execute('''
                SELECT COUNT(*)
                FROM events
                WHERE processing_status = 'pending' AND extraction_attempts >= 3
            ''')
            stuck_in_retry = cursor.fetchone()[0]

            # Get recent failed speakers
            cursor.execute('''
                SELECT speaker_id, name, tagging_status
                FROM speakers
                WHERE tagging_status = 'failed'
                ORDER BY last_updated DESC
                LIMIT ?
            ''', (limit,))

            failed_speakers = []
            for row in cursor.fetchall():
                failed_speakers.append({
                    'speaker_id': row[0],
                    'name': row[1],
                    'status': row[2]
                })

            # Analyze error message patterns (group similar errors)
            cursor.execute('''
                SELECT error_message, COUNT(*) as count
                FROM events
                WHERE processing_status = 'failed' AND error_message IS NOT NULL
                GROUP BY error_message
                ORDER BY count DESC
                LIMIT 10
            ''')

            error_messages = []
            for row in cursor.fetchall():
                error_messages.append({
                    'message': row[0],
                    'count': row[1]
                })

            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'failed_events': failed_events,
                'failed_speakers': failed_speakers,
                'stuck_in_retry': stuck_in_retry,
                'common_errors': error_messages
            }

        finally:
            db.close()

    def get_performance_metrics(self, days: int = 7) -> Dict:
        """
        Get performance metrics and trends

        Args:
            days: Number of days to look back

        Returns:
            dict: Performance metrics including duration, throughput
        """
        db = SpeakerDatabase(self.db_path)
        cursor = db.conn.cursor()

        try:
            since = datetime.utcnow() - timedelta(days=days)

            # Get pipeline run durations (handle both schemas)
            try:
                # Try new schema (started_at, speakers_enriched)
                cursor.execute('''
                    SELECT
                        started_at,
                        duration_seconds,
                        events_scraped,
                        speakers_extracted,
                        speakers_enriched,
                        embeddings_generated
                    FROM pipeline_runs
                    WHERE started_at >= ? AND duration_seconds IS NOT NULL
                    ORDER BY started_at DESC
                ''', (since.isoformat(),))
            except sqlite3.OperationalError:
                # Fall back to old schema (timestamp, new_speakers_enriched + existing_speakers_enriched)
                cursor.execute('''
                    SELECT
                        timestamp,
                        duration_seconds,
                        events_scraped,
                        speakers_extracted,
                        COALESCE(new_speakers_enriched, 0) + COALESCE(existing_speakers_enriched, 0) as speakers_enriched,
                        embeddings_generated
                    FROM pipeline_runs
                    WHERE timestamp >= ? AND duration_seconds IS NOT NULL
                    ORDER BY timestamp DESC
                ''', (since.isoformat(),))

            runs = []
            for row in cursor.fetchall():
                duration = row[1]
                events = row[2] or 0
                speakers = row[3] or 0

                runs.append({
                    'timestamp': row[0],
                    'duration_seconds': duration,
                    'duration_minutes': round(duration / 60, 1),
                    'events_scraped': events,
                    'speakers_extracted': speakers,
                    'speakers_enriched': row[4] or 0,
                    'embeddings_generated': row[5] or 0,
                    'events_per_minute': round(events / (duration / 60), 1) if duration > 0 and events > 0 else None,
                    'speakers_per_minute': round(speakers / (duration / 60), 1) if duration > 0 and speakers > 0 else None
                })

            # Calculate averages
            if runs:
                avg_duration = sum(r['duration_seconds'] for r in runs) / len(runs)
                avg_events = sum(r['events_scraped'] for r in runs) / len(runs)
                avg_speakers = sum(r['speakers_extracted'] for r in runs) / len(runs)
            else:
                avg_duration = avg_events = avg_speakers = None

            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'days': days,
                'total_runs': len(runs),
                'averages': {
                    'duration_seconds': round(avg_duration, 1) if avg_duration else None,
                    'duration_minutes': round(avg_duration / 60, 1) if avg_duration else None,
                    'events_scraped': round(avg_events, 1) if avg_events else None,
                    'speakers_extracted': round(avg_speakers, 1) if avg_speakers else None
                },
                'recent_runs': runs[:10]  # Last 10 runs
            }

        finally:
            db.close()

    def get_all_metrics(self) -> Dict:
        """
        Get all monitoring metrics in one call

        Returns:
            dict: All metrics combined
        """
        return {
            'health': self.get_health_status(),
            'backlog': self.get_backlog_trends(days=7),
            'success_rates': self.get_success_rates(hours=24),
            'costs': self.get_cost_metrics(days=7),
            'errors': self.get_error_patterns(limit=10),
            'performance': self.get_performance_metrics(days=7)
        }


# CLI interface for quick health checks
if __name__ == '__main__':
    import json
    import argparse

    parser = argparse.ArgumentParser(description='Pipeline monitoring and health checks')
    parser.add_argument('--metric', type=str, choices=['health', 'backlog', 'success', 'costs', 'errors', 'performance', 'all'],
                       default='health', help='Metric to display')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    monitor = PipelineMonitor()

    if args.metric == 'health':
        result = monitor.get_health_status()
    elif args.metric == 'backlog':
        result = monitor.get_backlog_trends()
    elif args.metric == 'success':
        result = monitor.get_success_rates()
    elif args.metric == 'costs':
        result = monitor.get_cost_metrics()
    elif args.metric == 'errors':
        result = monitor.get_error_patterns()
    elif args.metric == 'performance':
        result = monitor.get_performance_metrics()
    elif args.metric == 'all':
        result = monitor.get_all_metrics()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Pretty print for terminal
        if args.metric == 'health':
            health = result
            status_emoji = '✅' if health['status'] == 'healthy' else '⚠️' if health['status'] == 'warning' else '❌'
            print(f"\n{status_emoji} Pipeline Health: {health['status'].upper()}")
            print(f"   Locked: {health['pipeline_locked']}")
            if health['last_run']['status']:
                print(f"   Last run: {health['last_run']['status']} ({health['last_run']['hours_ago']}h ago)")
            print(f"\n📊 Backlog:")
            print(f"   Pending events: {health['backlog']['pending_events']}")
            print(f"   Failed events: {health['backlog']['failed_events']}")
            print(f"   Pending speakers: {health['backlog']['pending_speakers']}")
            if health['warnings']:
                print(f"\n⚠️  Warnings:")
                for w in health['warnings']:
                    print(f"   - {w}")
            if health['critical']:
                print(f"\n❌ Critical Issues:")
                for c in health['critical']:
                    print(f"   - {c}")
        else:
            print(json.dumps(result, indent=2))
