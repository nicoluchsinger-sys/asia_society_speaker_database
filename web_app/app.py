"""
Flask web application for speaker search
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import sys
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import markdown

# Add parent directory to path to access modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from speaker_search import SpeakerSearch
from database import SpeakerDatabase

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple password protection - single password for all users
# Set SITE_PASSWORD environment variable in Railway
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'CHANGE_ME_IN_ENV_VARS')

# Initialize search engine (reuse connection)
search = None
db = None

def get_db_path():
    """Get database path - /data/speakers.db on Railway, ./speakers.db locally"""
    if os.path.exists('/data'):
        # Railway production with mounted volume
        return '/data/speakers.db'
    else:
        # Local development
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'speakers.db')

def get_search():
    """Lazy initialization of search engine"""
    global search
    if search is None:
        db_path = get_db_path()
        search = SpeakerSearch(db_path=db_path, provider='openai')
    return search

def get_db():
    """Lazy initialization of database"""
    global db
    if db is None:
        db_path = get_db_path()
        db = SpeakerDatabase(db_path)
    return db


# Pipeline lock configuration - configurable timeout via environment variable
PIPELINE_LOCK_TIMEOUT = int(os.environ.get('PIPELINE_LOCK_TIMEOUT_SECONDS', '1800'))  # Default: 30 minutes

# Pipeline scheduling
def run_scheduled_pipeline():
    """Run the consolidated pipeline on a schedule"""
    import sqlite3
    from datetime import datetime, timezone

    logger.info("Starting scheduled pipeline run...")
    db_path = get_db_path()

    try:
        # Check if pipeline is already running (distributed lock across Railway instances)
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Create lock table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_lock (
                lock_id INTEGER PRIMARY KEY CHECK (lock_id = 1),
                is_locked BOOLEAN NOT NULL DEFAULT 0,
                locked_at TEXT,
                locked_by TEXT
            )
        ''')

        # Initialize lock row if it doesn't exist
        cursor.execute('INSERT OR IGNORE INTO pipeline_lock (lock_id, is_locked) VALUES (1, 0)')
        conn.commit()

        # Try to acquire lock
        cursor.execute('SELECT is_locked, locked_at, locked_by FROM pipeline_lock WHERE lock_id = 1')
        row = cursor.fetchone()
        is_locked, locked_at, locked_by = row[0], row[1], row[2] if len(row) > 2 else 'unknown'

        logger.info(f"Lock status: is_locked={is_locked}, locked_at={locked_at}, locked_by={locked_by}")

        # Check if lock is stale (older than configured timeout - pipeline should never take that long)
        if is_locked and locked_at:
            import time
            locked_time = datetime.fromisoformat(locked_at.replace('+00:00', ''))
            elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - locked_time).total_seconds()
            logger.info(f"Lock age: {elapsed:.0f}s (timeout threshold: {PIPELINE_LOCK_TIMEOUT}s)")

            if elapsed > PIPELINE_LOCK_TIMEOUT:
                logger.warning(f"⚠ Stale lock detected ({elapsed:.0f}s old, owner: {locked_by}), clearing it")
                is_locked = False

        if is_locked:
            logger.info(f"⏭ Pipeline already running (locked by {locked_by} at {locked_at}), skipping this execution")
            conn.close()
            return

        # Acquire lock
        instance_id = os.environ.get('RAILWAY_REPLICA_ID', 'local')
        cursor.execute(
            'UPDATE pipeline_lock SET is_locked = 1, locked_at = ?, locked_by = ? WHERE lock_id = 1',
            (datetime.now(timezone.utc).isoformat(), instance_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"✓ Acquired pipeline execution lock (instance: {instance_id})")

        try:
            # Import here to avoid circular imports
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from pipeline_cron import run_pipeline

            # Run pipeline: 20 new events, 5 pending retries, 20 existing speakers
            success = run_pipeline(event_limit=20, existing_limit=20, pending_limit=5)

            if success:
                logger.info("✓ Scheduled pipeline completed successfully")
            else:
                logger.error("✗ Scheduled pipeline failed")

        finally:
            # Release lock
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute('UPDATE pipeline_lock SET is_locked = 0 WHERE lock_id = 1')
            conn.commit()
            conn.close()
            logger.info("✓ Released pipeline execution lock")

    except Exception as e:
        logger.error(f"ERROR in scheduled pipeline: {e}")
        import traceback
        traceback.print_exc()
        # Try to release lock on error
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute('UPDATE pipeline_lock SET is_locked = 0 WHERE lock_id = 1')
            conn.commit()
            conn.close()
        except:
            pass


def run_monthly_refresh():
    """Run the monthly speaker refresh on a schedule"""
    import sqlite3
    from datetime import datetime, timezone

    logger.info("Starting monthly speaker refresh...")
    db_path = get_db_path()

    try:
        # Check if refresh is already running (distributed lock)
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Create lock table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS refresh_lock (
                lock_id INTEGER PRIMARY KEY CHECK (lock_id = 1),
                is_locked BOOLEAN NOT NULL DEFAULT 0,
                locked_at TEXT,
                locked_by TEXT
            )
        ''')

        # Initialize lock row if it doesn't exist
        cursor.execute('INSERT OR IGNORE INTO refresh_lock (lock_id, is_locked) VALUES (1, 0)')
        conn.commit()

        # Try to acquire lock
        cursor.execute('SELECT is_locked, locked_at, locked_by FROM refresh_lock WHERE lock_id = 1')
        row = cursor.fetchone()
        is_locked, locked_at, locked_by = row[0], row[1], row[2] if len(row) > 2 else 'unknown'

        logger.info(f"Refresh lock status: is_locked={is_locked}, locked_at={locked_at}, locked_by={locked_by}")

        # Check if lock is stale (older than 2 hours - refresh should never take that long)
        if is_locked and locked_at:
            import time
            locked_time = datetime.fromisoformat(locked_at.replace('+00:00', ''))
            elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - locked_time).total_seconds()
            logger.info(f"Refresh lock age: {elapsed:.0f}s (timeout: 7200s)")

            if elapsed > 7200:  # 2 hours
                logger.warning(f"⚠ Stale refresh lock detected ({elapsed:.0f}s old, owner: {locked_by}), clearing it")
                is_locked = False

        if is_locked:
            logger.info(f"⏭ Monthly refresh already running (locked by {locked_by} at {locked_at}), skipping")
            conn.close()
            return

        # Acquire lock
        instance_id = os.environ.get('RAILWAY_REPLICA_ID', 'local')
        cursor.execute(
            'UPDATE refresh_lock SET is_locked = 1, locked_at = ?, locked_by = ? WHERE lock_id = 1',
            (datetime.now(timezone.utc).isoformat(), instance_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"✓ Acquired refresh execution lock (instance: {instance_id})")

        try:
            # Import refresh function
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from refresh_stale_speakers import refresh_stale_speakers

            # Run refresh: 20 speakers, >6 months old, non-interactive
            result = refresh_stale_speakers(limit=20, months=6, non_interactive=True)

            logger.info(f"✓ Monthly refresh completed: {result['refreshed']} speakers refreshed, "
                       f"{result.get('affiliation_changes', 0)} affiliation updates, "
                       f"{result.get('title_changes', 0)} title updates, "
                       f"cost: ${result['cost']:.4f}")

        finally:
            # Release lock
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute('UPDATE refresh_lock SET is_locked = 0 WHERE lock_id = 1')
            conn.commit()
            conn.close()
            logger.info("✓ Released refresh execution lock")

    except Exception as e:
        logger.error(f"ERROR in monthly refresh: {e}")
        import traceback
        traceback.print_exc()
        # Try to release lock on error
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute('UPDATE refresh_lock SET is_locked = 0 WHERE lock_id = 1')
            conn.commit()
            conn.close()
        except:
            pass


# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Add pipeline job - runs twice daily at 6 AM and 6 PM UTC
scheduler.add_job(
    func=run_scheduled_pipeline,
    trigger=CronTrigger(hour='6,18'),  # Runs at 6:00 and 18:00 UTC
    id='pipeline_job',
    name='Run speaker pipeline twice daily',
    replace_existing=True,
    coalesce=True,  # If multiple runs are pending, only run once
    max_instances=1  # Only allow one instance of this job to run at a time
)

logger.info("✓ Scheduler initialized: pipeline runs at 6:00 and 18:00 UTC (20 events + 20 existing speakers per run)")

# Add monthly refresh job - runs on the 1st of each month at 3 AM UTC
scheduler.add_job(
    func=run_monthly_refresh,
    trigger=CronTrigger(day=1, hour=3),  # 1st of month at 3:00 AM UTC
    id='monthly_refresh_job',
    name='Run monthly speaker refresh',
    replace_existing=True,
    coalesce=True,
    max_instances=1
)

logger.info("✓ Monthly refresh scheduled: runs 1st of each month at 3:00 AM UTC (refreshes stale speakers >6 months old)")

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


def login_required(f):
    """Decorator to require password authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == SITE_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Incorrect password')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    """Homepage with search interface"""
    return render_template('search.html')


@app.route('/stats')
@login_required
def stats_page():
    """Statistics dashboard"""
    return render_template('stats.html')


@app.route('/api/search', methods=['POST'])
@login_required
def api_search():
    """Search API endpoint"""
    import time
    start_time = time.time()

    data = request.get_json()
    query = data.get('query', '').strip()
    limit = data.get('limit', 10)
    explain = data.get('explain', False)

    if not query:
        return jsonify({
            'success': False,
            'error': 'Query cannot be empty'
        }), 400

    try:
        search_engine = get_search()
        results = search_engine.search(query, top_k=limit, explain=explain)

        # Format results for JSON
        formatted_results = []
        for result in results:
            formatted_result = {
                'speaker_id': result['speaker_id'],
                'name': result['name'],
                'title': result.get('title'),
                'affiliation': result.get('affiliation'),
                'bio': result.get('bio'),
                'tags': result.get('tags', []),
                'event_count': result.get('event_count', 0),
                'location': result.get('location'),
                'score': round(result['score'], 3),
                'base_score': round(result.get('base_score', 0), 3),
                'bonus': round(result.get('bonus', 0), 3)
            }

            if explain and 'explanation' in result:
                formatted_result['explanation'] = result['explanation']

            formatted_results.append(formatted_result)

        # Log search query for analytics
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        database = get_db()
        database.log_search(
            query=query,
            ip_address=get_real_ip(),  # Get real client IP, not proxy IP
            results_count=len(formatted_results),
            execution_time_ms=execution_time
        )

        return jsonify({
            'success': True,
            'query': query,
            'results': formatted_results,
            'count': len(formatted_results)
        })

    except Exception as e:
        import traceback
        print(f"Search error: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}'
        }), 500


@app.route('/speaker/<int:speaker_id>')
@login_required
def speaker_detail(speaker_id):
    """Speaker detail page"""
    database = get_db()

    speaker_data = database.get_speaker_by_id(speaker_id)
    if not speaker_data:
        return "Speaker not found", 404

    # Parse speaker data
    speaker = {
        'speaker_id': speaker_data[0],
        'name': speaker_data[1],
        'title': speaker_data[2],
        'affiliation': speaker_data[3],
        'primary_affiliation': speaker_data[4],
        'bio': speaker_data[5]
    }

    # Get additional data
    tags = database.get_speaker_tags(speaker_id)
    events = database.get_speaker_events(speaker_id)
    demographics = database.get_speaker_demographics(speaker_id)
    locations = database.get_speaker_locations(speaker_id)
    languages = database.get_speaker_languages(speaker_id)

    # Format demographics
    demographics_data = None
    if demographics:
        demographics_data = {
            'gender': demographics[0],
            'gender_confidence': demographics[1],
            'nationality': demographics[2],
            'nationality_confidence': demographics[3],
            'birth_year': demographics[4],
            'enriched_at': demographics[5]
        }

    # Format tags with confidence colors
    formatted_tags = []
    for tag in tags:
        tag_text, confidence, source, created_at = tag
        color = 'green' if confidence and confidence > 0.8 else 'blue' if confidence and confidence > 0.6 else 'gray'
        formatted_tags.append({
            'text': tag_text,
            'confidence': confidence,
            'color': color,
            'source': source
        })

    # Format locations
    formatted_locations = []
    for loc in locations:
        formatted_locations.append({
            'location_id': loc[0],
            'location_type': loc[1],
            'city': loc[2],
            'country': loc[3],
            'region': loc[4],
            'is_primary': loc[5],
            'confidence': loc[6],
            'source': loc[7]
        })

    # Format languages
    formatted_languages = []
    for lang in languages:
        formatted_languages.append({
            'language': lang[0],
            'proficiency': lang[1],
            'confidence': lang[2],
            'source': lang[3]
        })

    # Format events
    formatted_events = []
    for event in events:
        formatted_events.append({
            'event_id': event[0],
            'title': event[1],
            'event_date': event[2],
            'url': event[3],
            'role': event[4]
        })

    # Get speaker corrections (verified and unverified)
    corrections = database.get_speaker_corrections(speaker_id)

    # Format corrections
    verified_corrections = []
    unverified_suggestions = []

    for correction in corrections:
        import json
        corr_id, field, current, suggested, context, submitted_at, submitted_by, \
        verified, confidence, reasoning, sources_json, applied_at = correction

        # Parse sources JSON
        sources = []
        if sources_json:
            try:
                sources = json.loads(sources_json)
            except:
                sources = []

        formatted_corr = {
            'correction_id': corr_id,
            'field_name': field,
            'current_value': current,
            'suggested_value': suggested,
            'context': context,
            'submitted_at': submitted_at,
            'confidence': confidence,
            'reasoning': reasoning,
            'sources': sources,
            'applied_at': applied_at
        }

        if verified:
            verified_corrections.append(formatted_corr)
        else:
            unverified_suggestions.append(formatted_corr)

    return render_template(
        'speaker.html',
        speaker=speaker,
        tags=formatted_tags,
        events=formatted_events,
        demographics=demographics_data,
        locations=formatted_locations,
        languages=formatted_languages,
        verified_corrections=verified_corrections,
        unverified_suggestions=unverified_suggestions
    )


@app.route('/event/<int:event_id>')
@login_required
def event_detail(event_id):
    """Event detail page showing all speakers"""
    database = get_db()

    # Get event details
    event_data = database.get_event_by_id(event_id)
    if not event_data:
        return "Event not found", 404

    # Parse event data
    event = {
        'event_id': event_data[0],
        'url': event_data[1],
        'title': event_data[2],
        'event_date': event_data[3],
        'location': event_data[4]
    }

    # Get all speakers for this event
    speakers_data = database.get_event_speakers(event_id)

    # Format speakers
    formatted_speakers = []
    for speaker in speakers_data:
        formatted_speakers.append({
            'speaker_id': speaker[0],
            'name': speaker[1],
            'title': speaker[2],
            'affiliation': speaker[3],
            'role': speaker[4]
        })

    return render_template(
        'event.html',
        event=event,
        speakers=formatted_speakers
    )


@app.route('/faq')
@login_required
def faq():
    """FAQ page with dynamic statistics"""
    import sqlite3

    database = get_db()

    # Get current statistics for dynamic content
    cursor = database.conn.cursor()

    # Get speaker and event counts
    cursor.execute('SELECT COUNT(*) FROM speakers')
    total_speakers = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM events')
    total_events = cursor.fetchone()[0]

    # Get event date range (using same query as stats API)
    cursor.execute('''
        SELECT event_date
        FROM events
        WHERE event_date IS NOT NULL
          AND event_date NOT LIKE '%-%T%:%'
        ORDER BY
            substr(event_date, 8, 4) ||
            CASE substr(event_date, 4, 3)
                WHEN 'Jan' THEN '01'
                WHEN 'Feb' THEN '02'
                WHEN 'Mar' THEN '03'
                WHEN 'Apr' THEN '04'
                WHEN 'May' THEN '05'
                WHEN 'Jun' THEN '06'
                WHEN 'Jul' THEN '07'
                WHEN 'Aug' THEN '08'
                WHEN 'Sep' THEN '09'
                WHEN 'Oct' THEN '10'
                WHEN 'Nov' THEN '11'
                WHEN 'Dec' THEN '12'
            END ||
            substr(event_date, 1, 2)
        ASC
        LIMIT 1
    ''')
    oldest = cursor.fetchone()
    oldest_event_date = oldest[0] if oldest else 'Unknown'

    cursor.execute('''
        SELECT event_date
        FROM events
        WHERE event_date IS NOT NULL
          AND event_date NOT LIKE '%-%T%:%'
        ORDER BY
            substr(event_date, 8, 4) ||
            CASE substr(event_date, 4, 3)
                WHEN 'Jan' THEN '01'
                WHEN 'Feb' THEN '02'
                WHEN 'Mar' THEN '03'
                WHEN 'Apr' THEN '04'
                WHEN 'May' THEN '05'
                WHEN 'Jun' THEN '06'
                WHEN 'Jul' THEN '07'
                WHEN 'Aug' THEN '08'
                WHEN 'Sep' THEN '09'
                WHEN 'Oct' THEN '10'
                WHEN 'Nov' THEN '11'
                WHEN 'Dec' THEN '12'
            END ||
            substr(event_date, 1, 2)
        DESC
        LIMIT 1
    ''')
    newest = cursor.fetchone()
    newest_event_date = newest[0] if newest else 'Unknown'

    # Read FAQ markdown file
    faq_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'FAQ.md')
    with open(faq_path, 'r', encoding='utf-8') as f:
        faq_content = f.read()

    # Replace template variables with actual values
    faq_content = faq_content.replace('{{total_speakers}}', str(total_speakers))
    faq_content = faq_content.replace('{{total_events}}', str(total_events))
    faq_content = faq_content.replace('{{oldest_event_date}}', oldest_event_date)
    faq_content = faq_content.replace('{{newest_event_date}}', newest_event_date)

    # Replace contact email from environment variable (not stored in repo)
    contact_email = os.environ.get('CONTACT_EMAIL', 'contact@example.com')
    faq_content = faq_content.replace('{{contact_email}}', contact_email)

    # Convert markdown to HTML
    faq_html = markdown.markdown(faq_content, extensions=['extra', 'nl2br'])

    return render_template('faq.html', faq_content=faq_html)


@app.route('/api/stats')
def api_stats():
    """Enhanced database statistics with enrichment progress and costs"""
    import sqlite3

    # Create new database connection for this request to avoid threading issues
    db_path = get_db_path()
    with SpeakerDatabase(db_path) as database:
        stats = database.get_enhanced_statistics()

        # Get event date range (event_date is mostly text format "DD MMM YYYY", some ISO)
        # Convert to sortable format by parsing and ordering correctly
        cursor = database.conn.cursor()

        # Get oldest event by converting date format (handle both text and ISO formats)
        cursor.execute('''
            SELECT event_date
            FROM events
            WHERE event_date IS NOT NULL
              AND event_date NOT LIKE '%-%T%:%'
            ORDER BY
                substr(event_date, 8, 4) ||
                CASE substr(event_date, 4, 3)
                    WHEN 'Jan' THEN '01'
                    WHEN 'Feb' THEN '02'
                    WHEN 'Mar' THEN '03'
                    WHEN 'Apr' THEN '04'
                    WHEN 'May' THEN '05'
                    WHEN 'Jun' THEN '06'
                    WHEN 'Jul' THEN '07'
                    WHEN 'Aug' THEN '08'
                    WHEN 'Sep' THEN '09'
                    WHEN 'Oct' THEN '10'
                    WHEN 'Nov' THEN '11'
                    WHEN 'Dec' THEN '12'
                END ||
                substr(event_date, 1, 2)
            ASC
            LIMIT 1
        ''')
        oldest = cursor.fetchone()

        # Get newest event
        cursor.execute('''
            SELECT event_date
            FROM events
            WHERE event_date IS NOT NULL
              AND event_date NOT LIKE '%-%T%:%'
            ORDER BY
                substr(event_date, 8, 4) ||
                CASE substr(event_date, 4, 3)
                    WHEN 'Jan' THEN '01'
                    WHEN 'Feb' THEN '02'
                    WHEN 'Mar' THEN '03'
                    WHEN 'Apr' THEN '04'
                    WHEN 'May' THEN '05'
                    WHEN 'Jun' THEN '06'
                    WHEN 'Jul' THEN '07'
                    WHEN 'Aug' THEN '08'
                    WHEN 'Sep' THEN '09'
                    WHEN 'Oct' THEN '10'
                    WHEN 'Nov' THEN '11'
                    WHEN 'Dec' THEN '12'
                END ||
                substr(event_date, 1, 2)
            DESC
            LIMIT 1
        ''')
        newest = cursor.fetchone()

        stats['oldest_event_date'] = oldest[0] if oldest else None
        stats['newest_event_date'] = newest[0] if newest else None

    # Add next scheduled pipeline run time
    try:
        job = scheduler.get_job('pipeline_job')
        if job and job.next_run_time:
            stats['next_pipeline_run'] = job.next_run_time.isoformat()
        else:
            stats['next_pipeline_run'] = None
    except Exception as e:
        logger.error(f"Error getting next pipeline run time: {e}")
        stats['next_pipeline_run'] = None

    return jsonify(stats)


@app.route('/events')
@login_required
def events_page():
    """Events browse page"""
    return render_template('events.html')


@app.route('/leaderboard')
@login_required
def leaderboard_page():
    """Speaker leaderboard page"""
    return render_template('leaderboard.html')


@app.route('/api/leaderboard', methods=['GET'])
@login_required
def api_leaderboard():
    """API endpoint for speaker leaderboard"""
    try:
        # Get query parameters
        limit = int(request.args.get('limit', 10))
        months = request.args.get('months', '12')
        months = int(months) if months and months != 'all' else None

        # Create new database connection for this request
        db_path = get_db_path()
        with SpeakerDatabase(db_path) as database:
            # Get top speakers
            speakers = database.get_top_speakers(limit=limit, months=months)

        # Format speakers
        formatted_speakers = []
        for idx, speaker in enumerate(speakers, 1):
            speaker_id, name, affiliation, event_count, last_event, locations, tags = speaker

            # Parse locations (comma-separated from GROUP_CONCAT DISTINCT)
            unique_locations = []
            if locations:
                unique_locations = [loc.strip() for loc in locations.split(',') if loc.strip()]

            # Parse tags
            tag_list = []
            if tags:
                tag_list = [tag.strip() for tag in tags.split(',')[:3]]  # Top 3 tags

            formatted_speakers.append({
                'rank': idx,
                'speaker_id': speaker_id,
                'name': name,
                'affiliation': affiliation,
                'event_count': event_count,
                'last_event': last_event,
                'locations': unique_locations,
                'location_count': len(unique_locations),
                'tags': tag_list
            })

        return jsonify({
            'success': True,
            'speakers': formatted_speakers,
            'count': len(formatted_speakers),
            'timeframe': f'{months} months' if months else 'all time'
        })

    except Exception as e:
        import traceback
        logger.error(f"Leaderboard API error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to fetch leaderboard: {str(e)}'
        }), 500


@app.route('/api/events', methods=['GET'])
@login_required
def api_events():
    """API endpoint for events listing with filtering"""
    try:
        # Get query parameters
        location_filter = request.args.get('location', None)
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        # Create new database connection for this request
        db_path = get_db_path()
        with SpeakerDatabase(db_path) as database:
            # Get events
            events = database.get_all_events(
                location_filter=location_filter,
                limit=limit,
                offset=offset
            )

            # Get unique locations for filter dropdown
            locations = database.get_unique_event_locations()

        # Format events
        formatted_events = []
        for event in events:
            event_id, title, event_date, location, speaker_count = event
            formatted_events.append({
                'event_id': event_id,
                'title': title,
                'event_date': event_date,
                'location': location,
                'speaker_count': speaker_count
            })

        return jsonify({
            'success': True,
            'events': formatted_events,
            'locations': locations,
            'count': len(formatted_events),
            'offset': offset,
            'limit': limit
        })

    except Exception as e:
        import traceback
        logger.error(f"Events API error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to fetch events: {str(e)}'
        }), 500


@app.route('/api/speaker/<int:speaker_id>/suggest-correction', methods=['POST'])
@login_required
def suggest_correction(speaker_id):
    """Submit a suggested correction for a speaker with AI verification"""
    try:
        data = request.get_json()

        # Validate required fields
        if not data or 'field_name' not in data or 'suggested_value' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: field_name, suggested_value'
            }), 400

        field_name = data['field_name']
        suggested_value = data['suggested_value']
        suggestion_context = data.get('context', '')

        # Validate field_name
        allowed_fields = ['affiliation', 'title', 'bio', 'primary_affiliation', 'city', 'country', 'location']
        if field_name not in allowed_fields:
            return jsonify({
                'success': False,
                'error': f'Invalid field_name. Must be one of: {", ".join(allowed_fields)}'
            }), 400

        # Get current speaker data
        db_path = get_db_path()
        with SpeakerDatabase(db_path) as database:
            speaker_data = database.get_speaker_by_id(speaker_id)

            if not speaker_data:
                return jsonify({
                    'success': False,
                    'error': 'Speaker not found'
                }), 404

            speaker_id_db, name, title, affiliation, primary_affiliation, bio = speaker_data
            current_value = None

            # Get current value for the field
            if field_name == 'affiliation':
                current_value = affiliation
            elif field_name == 'title':
                current_value = title
            elif field_name == 'bio':
                current_value = bio
            elif field_name == 'primary_affiliation':
                current_value = primary_affiliation
            elif field_name in ['city', 'country', 'location']:
                # Get primary location from speaker_locations table
                locations = database.get_speaker_locations(speaker_id)
                if locations:
                    # locations are ordered by is_primary DESC, so first one is primary
                    loc = locations[0]
                    location_id, location_type, city, country, region, is_primary, confidence, source, created_at = loc
                    if field_name == 'city':
                        current_value = city or ''
                    elif field_name == 'country':
                        current_value = country or ''
                    elif field_name == 'location':
                        # Combine city and country for location field
                        parts = [p for p in [city, country] if p]
                        current_value = ', '.join(parts) if parts else ''
                else:
                    current_value = ''

            # Don't process if suggestion is same as current value
            if current_value == suggested_value:
                return jsonify({
                    'success': False,
                    'error': 'Suggested value is the same as current value'
                }), 400

        # Verify correction with AI
        from correction_verifier import verify_with_web_search

        verification = verify_with_web_search(
            speaker_name=name,
            field_name=field_name,
            current_value=current_value,
            suggested_value=suggested_value,
            user_context=suggestion_context
        )

        # Get submitter IP address
        submitted_by = request.remote_addr

        # Determine if we should auto-apply
        verified = verification['confidence'] >= 0.85 and verification['is_correct']

        # Save correction to database
        with SpeakerDatabase(db_path) as database:
            correction_id = database.save_correction(
                speaker_id=speaker_id,
                field_name=field_name,
                current_value=current_value,
                suggested_value=suggested_value,
                suggestion_context=suggestion_context,
                submitted_by=submitted_by,
                verified=verified,
                confidence=verification['confidence'],
                reasoning=verification['reasoning'],
                sources=verification['sources']
            )

            # If high confidence, apply the correction immediately
            if verified:
                if field_name in ['city', 'country', 'location']:
                    # Handle location fields separately
                    database.apply_location_correction(speaker_id, field_name, suggested_value)
                else:
                    # Handle regular fields
                    database.apply_correction(speaker_id, field_name, suggested_value)

        # Return result
        return jsonify({
            'success': True,
            'correction_id': correction_id,
            'applied': verified,
            'confidence': verification['confidence'],
            'reasoning': verification['reasoning'],
            'sources': verification['sources'],
            'message': (
                f'Correction verified and applied automatically (confidence: {verification["confidence"]:.0%})'
                if verified else
                f'Suggestion saved but not verified (confidence: {verification["confidence"]:.0%}). '
                'It will be shown as an unverified suggestion on the speaker page.'
            )
        })

    except Exception as e:
        import traceback
        logger.error(f"Correction submission error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Failed to process correction: {str(e)}'
        }), 500


@app.route('/admin/upload-db', methods=['POST'])
def upload_database():
    """TEMPORARY: Upload database file - REMOVE AFTER USE"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        db_path = get_db_path()

        file.save(db_path)

        return jsonify({'success': True, 'message': f'Database uploaded to {db_path}', 'size': os.path.getsize(db_path)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/download-db', methods=['GET'])
def download_database():
    """TEMPORARY: Download database file - REMOVE AFTER USE"""
    from flask import send_file
    try:
        db_path = get_db_path()
        return send_file(db_path, as_attachment=True, download_name='speakers.db')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/run-pipeline', methods=['POST'])
@login_required
def manual_pipeline_trigger():
    """Manually trigger the pipeline (for testing)"""
    try:
        # Run pipeline in background thread to avoid blocking
        import threading
        thread = threading.Thread(target=run_scheduled_pipeline)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Pipeline started in background',
            'note': 'Check logs or /api/stats for progress'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/lock-status', methods=['GET'])
@login_required
def lock_status():
    """Check pipeline lock status - useful for debugging stuck locks"""
    import sqlite3
    from datetime import datetime, timezone

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Create lock table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pipeline_lock (
                lock_id INTEGER PRIMARY KEY CHECK (lock_id = 1),
                is_locked BOOLEAN NOT NULL DEFAULT 0,
                locked_at TEXT,
                locked_by TEXT
            )
        ''')

        # Initialize lock row if it doesn't exist
        cursor.execute('INSERT OR IGNORE INTO pipeline_lock (lock_id, is_locked) VALUES (1, 0)')
        conn.commit()

        # Get current lock status
        cursor.execute('SELECT is_locked, locked_at, locked_by FROM pipeline_lock WHERE lock_id = 1')
        row = cursor.fetchone()
        conn.close()

        is_locked = bool(row[0])
        locked_at = row[1]
        locked_by = row[2] if len(row) > 2 else 'unknown'

        status = {
            'is_locked': is_locked,
            'locked_at': locked_at,
            'locked_by': locked_by,
            'timeout_threshold_seconds': PIPELINE_LOCK_TIMEOUT
        }

        # Calculate lock age if locked
        if is_locked and locked_at:
            try:
                locked_time = datetime.fromisoformat(locked_at.replace('+00:00', ''))
                elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - locked_time).total_seconds()
                status['lock_age_seconds'] = int(elapsed)
                status['is_stale'] = elapsed > PIPELINE_LOCK_TIMEOUT
            except Exception as e:
                logger.error(f"Error calculating lock age: {e}")
                status['lock_age_seconds'] = None
                status['is_stale'] = False

        return jsonify(status)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/unlock', methods=['POST'])
@login_required
def force_unlock():
    """Manually reset a stuck pipeline lock - use with caution"""
    import sqlite3
    from datetime import datetime, timezone

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Get current lock status before clearing
        cursor.execute('SELECT is_locked, locked_at, locked_by FROM pipeline_lock WHERE lock_id = 1')
        row = cursor.fetchone()

        if not row or not row[0]:
            conn.close()
            return jsonify({
                'success': True,
                'message': 'Lock was already unlocked',
                'was_locked': False
            })

        locked_at = row[1]
        locked_by = row[2] if len(row) > 2 else 'unknown'

        # Calculate how long it was locked
        lock_age = None
        if locked_at:
            try:
                locked_time = datetime.fromisoformat(locked_at.replace('+00:00', ''))
                lock_age = int((datetime.now(timezone.utc).replace(tzinfo=None) - locked_time).total_seconds())
            except:
                pass

        # Clear the lock
        cursor.execute('UPDATE pipeline_lock SET is_locked = 0 WHERE lock_id = 1')
        conn.commit()
        conn.close()

        logger.warning(f"⚠ Pipeline lock manually cleared (was locked by {locked_by} at {locked_at}, age: {lock_age}s)")

        return jsonify({
            'success': True,
            'message': 'Pipeline lock cleared',
            'was_locked': True,
            'previous_owner': locked_by,
            'previous_locked_at': locked_at,
            'lock_age_seconds': lock_age
        })

    except Exception as e:
        logger.error(f"Error clearing lock: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/reset-failed-events', methods=['POST'])
@login_required
def reset_failed_events_endpoint():
    """Reset failed events back to pending for reprocessing"""
    import sqlite3

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Get count and examples of failed events
        cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'failed'")
        failed_count = cursor.fetchone()[0]

        if failed_count == 0:
            conn.close()
            return jsonify({
                'success': True,
                'message': 'No failed events to reset',
                'count': 0
            })

        # Get some examples
        cursor.execute("""
            SELECT event_id, title, url
            FROM events
            WHERE processing_status = 'failed'
            ORDER BY event_id DESC
            LIMIT 3
        """)
        examples = cursor.fetchall()

        # Reset the events
        cursor.execute("""
            UPDATE events
            SET processing_status = 'pending'
            WHERE processing_status = 'failed'
        """)
        conn.commit()
        conn.close()

        logger.info(f"Reset {failed_count} failed events to pending status")

        # Format examples for display
        example_titles = [f"{row[1][:50]}..." for row in examples[:3]]

        return jsonify({
            'success': True,
            'message': f'Reset {failed_count} failed events to pending',
            'count': failed_count,
            'examples': example_titles
        })

    except Exception as e:
        logger.error(f"Error resetting failed events: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/download-logs')
@login_required
def download_pipeline_logs():
    """Download the pipeline debug log file"""
    import os
    from flask import send_file

    log_file = 'pipeline_debug.log'

    if not os.path.exists(log_file):
        return jsonify({'error': 'No log file found. Run the pipeline first.'}), 404

    return send_file(
        log_file,
        as_attachment=True,
        download_name='pipeline_debug.log',
        mimetype='text/plain'
    )


@app.route('/api/search-analytics')
@login_required
def api_search_analytics():
    """API endpoint for search analytics data"""
    try:
        days = int(request.args.get('days', 30))

        db_path = get_db_path()
        with SpeakerDatabase(db_path) as database:
            analytics = database.get_search_analytics(days=days)

        # Format data for JSON response
        return jsonify({
            'success': True,
            'days': days,
            'total_searches': analytics['total_searches'],
            'avg_results_per_search': round(analytics['avg_results_per_search'], 2),
            'avg_execution_time_ms': round(analytics['avg_execution_time_ms'], 2),
            'top_queries': [
                {
                    'query': row[0],
                    'count': row[1],
                    'avg_results': round(row[2], 1)
                }
                for row in analytics['top_queries']
            ],
            'no_result_queries': [
                {
                    'query': row[0],
                    'count': row[1]
                }
                for row in analytics['no_result_queries']
            ],
            'daily_volume': [
                {
                    'date': row[0],
                    'count': row[1]
                }
                for row in analytics['daily_volume']
            ]
        })

    except Exception as e:
        import traceback
        logger.error(f"Search analytics error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/admin')
@login_required
def admin_panel():
    """Consolidated admin panel - not linked from menu, direct URL only"""
    return render_template('admin.html')


@app.route('/admin/pipeline-status')
@login_required
def admin_pipeline_status():
    """Get current pipeline status"""
    import sqlite3
    from datetime import datetime, timezone

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Check if pipeline is running
        cursor.execute('SELECT is_locked, locked_at FROM pipeline_lock WHERE lock_id = 1')
        lock_row = cursor.fetchone()
        is_running = bool(lock_row[0]) if lock_row else False

        # Get last pipeline run
        cursor.execute('''
            SELECT timestamp, success FROM pipeline_runs
            ORDER BY run_id DESC LIMIT 1
        ''')
        last_run_row = cursor.fetchone()

        # Check for errors in recent runs
        cursor.execute('''
            SELECT COUNT(*) FROM pipeline_runs
            WHERE success = 0 AND timestamp > datetime('now', '-24 hours')
        ''')
        error_count = cursor.fetchone()[0]

        conn.close()

        # Format last run time
        last_run = None
        if last_run_row:
            try:
                dt = datetime.fromisoformat(last_run_row[0])
                last_run = dt.strftime('%Y-%m-%d %H:%M UTC')
            except:
                last_run = last_run_row[0]

        return jsonify({
            'is_running': is_running,
            'has_errors': error_count > 0,
            'error_count_24h': error_count,
            'last_run': last_run
        })

    except Exception as e:
        logger.error(f"Pipeline status error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/recent-runs')
@login_required
def admin_recent_runs():
    """Get last 10 pipeline runs"""
    import sqlite3
    from datetime import datetime

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT timestamp, events_scraped, speakers_extracted,
                   duration_seconds, total_cost, success
            FROM pipeline_runs
            ORDER BY run_id DESC
            LIMIT 10
        ''')

        rows = cursor.fetchall()
        conn.close()

        runs = []
        for row in rows:
            try:
                dt = datetime.fromisoformat(row[0])
                timestamp_str = dt.strftime('%Y-%m-%d %H:%M UTC')
            except:
                timestamp_str = row[0]

            runs.append({
                'timestamp': timestamp_str,
                'events_scraped': row[1] or 0,
                'speakers_extracted': row[2] or 0,
                'duration': round(row[3] or 0, 1),
                'total_cost': row[4] or 0,
                'success': bool(row[5])
            })

        return jsonify(runs)

    except Exception as e:
        logger.error(f"Recent runs error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/recent-searches')
@login_required
def admin_recent_searches():
    """Get last 10 searches with IP addresses"""
    import sqlite3
    from datetime import datetime

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Get recent searches from search_logs table
        cursor.execute('''
            SELECT query, results_count, execution_time_ms,
                   ip_address, timestamp
            FROM search_logs
            ORDER BY log_id DESC
            LIMIT 10
        ''')

        rows = cursor.fetchall()
        conn.close()

        searches = []
        for row in rows:
            try:
                dt = datetime.fromisoformat(row[4])
                timestamp_str = dt.strftime('%Y-%m-%d %H:%M UTC')
            except:
                timestamp_str = row[4] if row[4] else 'Unknown'

            # Simple location from IP (just show IP for now, can add geoIP later)
            ip = row[3] if row[3] else 'Unknown'
            location = get_ip_location(ip) if ip != 'Unknown' else 'Unknown'

            searches.append({
                'timestamp': timestamp_str,
                'query': row[0] or '',
                'result_count': row[1] or 0,
                'ip_address': ip,
                'location': location
            })

        return jsonify(searches)

    except Exception as e:
        logger.error(f"Recent searches error: {e}")
        return jsonify({'error': str(e)}), 500


def get_real_ip() -> str:
    """Get real client IP address, handling proxies like Railway"""
    # Check X-Forwarded-For header (set by Railway and other proxies)
    if request.headers.get('X-Forwarded-For'):
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The first one is the real client IP
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()

    # Check X-Real-IP header (alternative header some proxies use)
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP').strip()

    # Fallback to remote_addr (will be proxy IP if behind a proxy)
    return request.remote_addr


def get_ip_location(ip: str) -> str:
    """Get approximate location from IP address using ipapi.co"""
    try:
        # Simple check for local/private IPs
        if ip.startswith('127.') or ip.startswith('192.168.') or ip.startswith('10.'):
            return 'Local'
        if ip.startswith('100.64.'):  # Railway internal
            return 'Railway (Internal)'

        # Use ipapi.co for geolocation (free tier: 1,000 requests/day, no API key needed)
        import requests
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=2)

        if response.status_code == 200:
            data = response.json()
            # Build location string from available data
            city = data.get('city', '')
            region = data.get('region', '')
            country = data.get('country_name', '')

            # Format location nicely
            parts = []
            if city:
                parts.append(city)
            if region and region != city:
                parts.append(region)
            if country:
                parts.append(country)

            if parts:
                return ', '.join(parts)

        return 'Unknown'
    except Exception as e:
        logger.debug(f"IP geolocation failed for {ip}: {e}")
        return 'Unknown'


@app.route('/admin/user-activity')
@login_required
def admin_user_activity():
    """Get user activity metrics - popular searches and most viewed speakers"""
    import sqlite3

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Get top 10 searches by frequency
        cursor.execute('''
            SELECT query, COUNT(*) as search_count
            FROM search_logs
            WHERE query IS NOT NULL AND query != ''
            GROUP BY query
            ORDER BY search_count DESC
            LIMIT 10
        ''')

        top_searches = []
        for row in cursor.fetchall():
            top_searches.append({
                'query': row[0],
                'count': row[1]
            })

        # Get most viewed speakers (speakers with most events)
        cursor.execute('''
            SELECT s.name, s.affiliation, COUNT(es.event_id) as event_count
            FROM speakers s
            JOIN event_speakers es ON s.speaker_id = es.speaker_id
            GROUP BY s.speaker_id
            ORDER BY event_count DESC
            LIMIT 10
        ''')

        top_speakers = []
        for row in cursor.fetchall():
            top_speakers.append({
                'name': row[0],
                'affiliation': row[1] or 'N/A',
                'view_count': row[2]  # Frontend expects 'view_count'
            })

        conn.close()

        return jsonify({
            'top_searches': top_searches,
            'top_speakers': top_speakers
        })

    except Exception as e:
        logger.error(f"User activity error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api-costs')
@login_required
def admin_api_costs():
    """Get API usage and cost breakdown"""
    import sqlite3
    from datetime import datetime, timedelta

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Get total cost from all pipeline runs
        cursor.execute('SELECT COALESCE(SUM(total_cost), 0) FROM pipeline_runs')
        total_cost = cursor.fetchone()[0]

        # Get monthly costs (last 30 days)
        cursor.execute('''
            SELECT COALESCE(SUM(total_cost), 0)
            FROM pipeline_runs
            WHERE timestamp > datetime('now', '-30 days')
        ''')
        monthly_cost = cursor.fetchone()[0]

        # Get average cost per event/speaker
        cursor.execute('''
            SELECT
                COUNT(*) as run_count,
                COALESCE(SUM(events_scraped), 0) as total_events,
                COALESCE(SUM(speakers_extracted), 0) as total_speakers
            FROM pipeline_runs
            WHERE success = 1
        ''')
        row = cursor.fetchone()
        run_count = row[0]
        total_events = row[1]
        total_speakers = row[2]

        # Calculate averages
        avg_cost_per_event = (total_cost / total_events) if total_events > 0 else 0
        avg_cost_per_speaker = (total_cost / total_speakers) if total_speakers > 0 else 0

        # Get monthly breakdown (last 12 months)
        cursor.execute('''
            SELECT
                strftime('%Y-%m', timestamp) as month,
                COALESCE(SUM(total_cost), 0) as cost
            FROM pipeline_runs
            GROUP BY strftime('%Y-%m', timestamp)
            ORDER BY month DESC
            LIMIT 12
        ''')

        monthly_breakdown = []
        for row in cursor.fetchall():
            monthly_breakdown.append({
                'month': row[0],
                'cost': round(row[1], 2)
            })

        conn.close()

        # For breakdown by operation type, we estimate based on typical ratios
        # since we don't track extraction/enrichment/embeddings separately
        # Typical cost distribution: 70% extraction, 20% enrichment, 10% embeddings
        return jsonify({
            'this_month': round(monthly_cost, 2),
            'all_time': round(total_cost, 2),
            'per_event': round(avg_cost_per_event, 4),
            'per_speaker': round(avg_cost_per_speaker, 4),
            'breakdown': {
                'extraction': round(total_cost * 0.70, 2),  # Estimated
                'enrichment': round(total_cost * 0.20, 2),  # Estimated
                'embeddings': round(total_cost * 0.10, 2)   # Estimated
            },
            'monthly': monthly_breakdown
        })

    except Exception as e:
        logger.error(f"API costs error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/database-health')
@login_required
def admin_database_health():
    """Get database health metrics"""
    import sqlite3
    import os

    try:
        db_path = get_db_path()

        # Get database file size
        db_size_bytes = os.path.getsize(db_path)
        db_size_mb = db_size_bytes / (1024 * 1024)

        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Get table counts
        cursor.execute('SELECT COUNT(*) FROM events')
        event_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speakers')
        speaker_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM event_speakers')
        event_speaker_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speaker_embeddings')
        embedding_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM search_logs')
        search_count = cursor.fetchone()[0]

        # Check for events pending extraction
        cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'pending'")
        pending_events = cursor.fetchone()[0]

        # Check for failed events
        cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'failed'")
        failed_events = cursor.fetchone()[0]

        # Get database fragmentation
        cursor.execute('PRAGMA page_count')
        page_count = cursor.fetchone()[0]

        cursor.execute('PRAGMA freelist_count')
        freelist_count = cursor.fetchone()[0]

        fragmentation_pct = (freelist_count / page_count * 100) if page_count > 0 else 0

        conn.close()

        # Total records
        total_records = event_count + speaker_count + event_speaker_count + embedding_count + search_count

        # Last vacuum - we don't track this, so use estimated value
        last_vacuum = 'Never' if fragmentation_pct > 10 else 'Recently'

        # Build tables array for frontend
        tables = [
            {'name': 'Events', 'count': event_count},
            {'name': 'Speakers', 'count': speaker_count},
            {'name': 'Event Speakers', 'count': event_speaker_count},
            {'name': 'Embeddings', 'count': embedding_count},
            {'name': 'Search Logs', 'count': search_count}
        ]

        return jsonify({
            'size_mb': round(db_size_mb, 1),
            'total_records': total_records,
            'last_vacuum': last_vacuum,
            'tables': tables,
            'pending_events': pending_events,
            'failed_events': failed_events,
            'fragmentation_pct': round(fragmentation_pct, 1)
        })

    except Exception as e:
        logger.error(f"Database health error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/data-quality')
@login_required
def admin_data_quality():
    """Get data quality and completeness metrics"""
    import sqlite3

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Speaker completeness metrics
        cursor.execute('SELECT COUNT(*) FROM speakers')
        total_speakers = cursor.fetchone()[0]

        # Speakers with bio
        cursor.execute('SELECT COUNT(*) FROM speakers WHERE bio IS NOT NULL AND bio != ""')
        speakers_with_bio = cursor.fetchone()[0]

        # Speakers with tags
        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_tags')
        speakers_with_tags = cursor.fetchone()[0]

        # Speakers with demographics (from speaker_demographics table)
        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_demographics')
        speakers_with_demographics = cursor.fetchone()[0]

        # Speakers with locations (from speaker_locations table)
        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_locations')
        speakers_with_locations = cursor.fetchone()[0]

        # Event completeness metrics
        cursor.execute('SELECT COUNT(*) FROM events')
        total_events = cursor.fetchone()[0]

        # Events with dates (event_date field)
        cursor.execute('SELECT COUNT(*) FROM events WHERE event_date IS NOT NULL AND event_date != ""')
        events_with_dates = cursor.fetchone()[0]

        # Events with speakers
        cursor.execute('''
            SELECT COUNT(DISTINCT event_id)
            FROM event_speakers
        ''')
        events_with_speakers = cursor.fetchone()[0]

        # Events with body text (content)
        cursor.execute('SELECT COUNT(*) FROM events WHERE body_text IS NOT NULL AND body_text != ""')
        events_with_descriptions = cursor.fetchone()[0]

        # Events with locations
        cursor.execute('SELECT COUNT(*) FROM events WHERE location IS NOT NULL AND location != ""')
        events_with_locations = cursor.fetchone()[0]

        # Events processed and failed
        cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'completed'")
        events_processed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM events WHERE processing_status = 'failed'")
        events_failed = cursor.fetchone()[0]

        conn.close()

        # Build response matching frontend expectations
        return jsonify({
            'speakers': {
                'total': total_speakers,
                'with_bios': speakers_with_bio,
                'with_tags': speakers_with_tags,
                'with_demographics': speakers_with_demographics,
                'with_locations': speakers_with_locations
            },
            'events': {
                'total': total_events,
                'with_dates': events_with_dates,
                'with_speakers': events_with_speakers,
                'with_descriptions': events_with_descriptions,
                'with_locations': events_with_locations,
                'processed': events_processed,
                'failed': events_failed
            }
        })

    except Exception as e:
        logger.error(f"Data quality error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/reset-costs', methods=['POST'])
@login_required
def reset_api_costs():
    """Reset API cost tracking to zero for fresh start with new pricing"""
    import sqlite3

    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=5.0)
        cursor = conn.cursor()

        # Check if pipeline_runs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        if not cursor.fetchone():
            conn.close()
            return jsonify({
                'success': True,
                'message': 'No pipeline_runs table found - nothing to reset',
                'runs_deleted': 0
            })

        # Get current stats before reset
        cursor.execute('SELECT COUNT(*), COALESCE(SUM(total_cost), 0) FROM pipeline_runs')
        count, total_cost = cursor.fetchone()

        if count == 0:
            conn.close()
            return jsonify({
                'success': True,
                'message': 'No pipeline runs to reset',
                'runs_deleted': 0,
                'previous_total_cost': 0
            })

        # Clear the table
        cursor.execute('DELETE FROM pipeline_runs')
        conn.commit()
        conn.close()

        logger.info(f"Reset API costs: deleted {count} pipeline runs totaling ${total_cost:.2f}")

        return jsonify({
            'success': True,
            'message': f'API cost tracking reset - deleted {count} pipeline run records',
            'runs_deleted': count,
            'previous_total_cost': round(total_cost, 2)
        })

    except Exception as e:
        logger.error(f"Error resetting API costs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/debug-stats')
def debug_stats():
    """Detailed diagnostic statistics"""
    db_path = get_db_path()
    with SpeakerDatabase(db_path) as db:
        cursor = db.conn.cursor()

        debug = {}

        # Basic counts
        cursor.execute('SELECT COUNT(*) FROM speakers')
        debug['total_speakers'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speakers WHERE tagging_status = "completed"')
        debug['enriched_speakers'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speaker_embeddings')
        debug['total_embeddings'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_embeddings')
        debug['unique_speakers_with_embeddings'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT speaker_id) FROM speaker_tags')
        debug['tagged_speakers'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM speaker_tags')
        debug['total_tags'] = cursor.fetchone()[0]

        # Check for orphaned records
        cursor.execute('''
            SELECT COUNT(*) FROM speaker_embeddings
            WHERE speaker_id NOT IN (SELECT speaker_id FROM speakers)
        ''')
        debug['orphaned_embeddings'] = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM speaker_tags
            WHERE speaker_id NOT IN (SELECT speaker_id FROM speakers)
        ''')
        debug['orphaned_tags'] = cursor.fetchone()[0]

        # Pipeline runs
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_runs'")
        if cursor.fetchone():
            cursor.execute('SELECT COUNT(*) FROM pipeline_runs')
            debug['pipeline_runs'] = cursor.fetchone()[0]

            # Check if cost columns exist
            cursor.execute("PRAGMA table_info(pipeline_runs)")
            columns = [row[1] for row in cursor.fetchall()]
            debug['cost_columns_exist'] = 'extraction_cost' in columns
        else:
            debug['pipeline_runs'] = 0
            debug['cost_columns_exist'] = False

        return jsonify(debug)


@app.route('/admin/cleanup-orphaned', methods=['POST'])
def cleanup_orphaned():
    """Delete orphaned embeddings and tags"""
    try:
        db_path = get_db_path()
        with SpeakerDatabase(db_path) as db:
            cursor = db.conn.cursor()

            # Delete orphaned embeddings
            cursor.execute('''
                DELETE FROM speaker_embeddings
                WHERE speaker_id NOT IN (SELECT speaker_id FROM speakers)
            ''')
            orphaned_embeddings = cursor.rowcount

            # Delete orphaned tags
            cursor.execute('''
                DELETE FROM speaker_tags
                WHERE speaker_id NOT IN (SELECT speaker_id FROM speakers)
            ''')
            orphaned_tags = cursor.rowcount

            db.conn.commit()

            return jsonify({
                'success': True,
                'orphaned_embeddings_deleted': orphaned_embeddings,
                'orphaned_tags_deleted': orphaned_tags
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/backfill-embeddings', methods=['POST'])
def backfill_embeddings():
    """One-time fix: Generate embeddings for speakers that are missing them"""
    try:
        from generate_embeddings import generate_embeddings
        import threading

        def run_backfill():
            logger.info("Starting embedding backfill...")
            try:
                db_path = get_db_path()
                logger.info(f"Using database: {db_path}")
                generate_embeddings(batch_size=50, provider='openai', verbose=True, db_path=db_path)
                logger.info("Embedding backfill completed successfully")
            except Exception as e:
                logger.error(f"Embedding backfill failed: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # Run in background thread
        thread = threading.Thread(target=run_backfill)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Embedding backfill started in background',
            'note': 'Check logs for progress. Should generate ~376 embeddings.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/regenerate-embeddings', methods=['POST'])
def regenerate_embeddings():
    """Regenerate ALL embeddings including tags (overwrites existing)"""
    try:
        from generate_embeddings import regenerate_all_embeddings
        import threading

        def run_regeneration():
            logger.info("Starting embedding regeneration for ALL speakers...")
            try:
                db_path = get_db_path()
                logger.info(f"Using database: {db_path}")
                regenerate_all_embeddings(batch_size=50, provider='openai', verbose=True, db_path=db_path)
                logger.info("Embedding regeneration completed successfully")
            except Exception as e:
                logger.error(f"Embedding regeneration failed: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # Run in background thread
        thread = threading.Thread(target=run_regeneration)
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Embedding regeneration started in background',
            'note': 'Regenerating embeddings for all 848 speakers. Check logs for progress. Will take ~2-3 minutes.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Use PORT environment variable for Railway/Heroku compatibility
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port, host='0.0.0.0')
