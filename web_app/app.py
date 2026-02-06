"""
Flask web application for speaker search
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import sys
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit

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


# Pipeline scheduling
def run_scheduled_pipeline():
    """Run the consolidated pipeline on a schedule"""
    logger.info("Starting scheduled pipeline run...")

    try:
        # Import here to avoid circular imports
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from pipeline_cron import run_pipeline

        # Run pipeline: 5 events, 20 existing speakers
        success = run_pipeline(event_limit=5, existing_limit=20)

        if success:
            logger.info("✓ Scheduled pipeline completed successfully")
        else:
            logger.error("✗ Scheduled pipeline failed")

    except Exception as e:
        logger.error(f"ERROR in scheduled pipeline: {e}")
        import traceback
        traceback.print_exc()


# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Add pipeline job - runs every 2 hours
scheduler.add_job(
    func=run_scheduled_pipeline,
    trigger=IntervalTrigger(hours=2),
    id='pipeline_job',
    name='Run speaker pipeline every 2 hours',
    replace_existing=True
)

logger.info("✓ Scheduler initialized: pipeline runs every 2 hours (5 events + 20 existing speakers)")

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
                'score': round(result['score'], 3),
                'base_score': round(result.get('base_score', 0), 3),
                'bonus': round(result.get('bonus', 0), 3)
            }

            if explain and 'explanation' in result:
                formatted_result['explanation'] = result['explanation']

            formatted_results.append(formatted_result)

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

    return render_template(
        'speaker.html',
        speaker=speaker,
        tags=formatted_tags,
        events=formatted_events,
        demographics=demographics_data,
        locations=formatted_locations,
        languages=formatted_languages
    )


@app.route('/api/stats')
def api_stats():
    """Enhanced database statistics with enrichment progress and costs"""
    # Create new database connection for this request to avoid threading issues
    db_path = get_db_path()
    with SpeakerDatabase(db_path) as database:
        stats = database.get_enhanced_statistics()

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


if __name__ == '__main__':
    # Use PORT environment variable for Railway/Heroku compatibility
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port, host='0.0.0.0')
