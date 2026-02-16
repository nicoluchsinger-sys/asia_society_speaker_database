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
SITE_PASSWORD = os.environ.get('SITE_PASSWORD', 'asiasociety123')

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

            # Run pipeline: 10 events, 20 existing speakers
            success = run_pipeline(event_limit=10, existing_limit=20)

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

logger.info("✓ Scheduler initialized: pipeline runs at 6:00 and 18:00 UTC (10 events + 20 existing speakers per run)")

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
            ip_address=request.remote_addr,
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
        allowed_fields = ['affiliation', 'title', 'bio', 'primary_affiliation']
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


@app.route('/admin/search-analytics')
@login_required
def search_analytics_page():
    """Search analytics dashboard page"""
    return render_template('search_analytics.html')


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
