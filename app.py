import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for, Response
from flask_login import LoginManager, current_user, login_required

load_dotenv()

BASE_DIR   = Path(__file__).parent
CONFIG_FILE = BASE_DIR / 'config.json'
RUNS_DIR   = BASE_DIR / 'runs'


def save_run(result):
    """Persist a run's full result dict to runs/{run_id}.json."""
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{result['run_id']}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, default=str)


def load_run(run_id):
    """Load a saved run by ID. Returns None if not found."""
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_runs():
    """Return run metadata for all saved runs, newest first."""
    RUNS_DIR.mkdir(exist_ok=True)
    runs = []
    for p in sorted(RUNS_DIR.glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
            runs.append({
                'run_id':            data.get('run_id', p.stem),
                'timestamp':         data.get('timestamp', ''),
                'uploaded_by':       data.get('uploaded_by', ''),
                'run_name':          data.get('run_name', ''),
                'filename':          data.get('filename', ''),
                'source':            data.get('source', ''),
                'row_count':         data.get('row_count', 0),
                'qualifiable_count': data.get('qualifiable_count', 0),
                'no_fit_count':      data.get('no_fit_count', 0),
                'warning_count':     len(data.get('warnings', [])),
            })
        except Exception:
            pass
    return runs


def parse_log_lines(log_file, limit=200):
    """Read and parse the activity log, newest first."""
    if not log_file.exists():
        return []
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    entries = []
    for line in reversed(lines[-limit:]):
        parts = line.strip().split(' | ')
        if len(parts) >= 3:
            entries.append({
                'timestamp': parts[0],
                'action':    parts[1],
                'email':     parts[2],
                'extra':     parts[3] if len(parts) > 3 else '',
            })
    return entries


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

    # Load config once at startup
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        app.config['LEAD_CONFIG'] = json.load(f)

    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.init_app(app)

    from auth.routes import User, LOG_FILE

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    # Register auth blueprint
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # ---------------------------------------------------------------------------
    # Routes
    # ---------------------------------------------------------------------------

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('upload'))
        return redirect(url_for('auth.login'))

    @app.route('/upload', methods=['GET', 'POST'])
    @login_required
    def upload():
        result = None

        if request.method == 'POST':
            file     = request.files.get('file')
            source   = request.form.get('source', '').strip()
            run_name = request.form.get('run_name', '').strip()

            # Validation
            if not file or file.filename == '':
                flash('Please select a CSV file.')
                return render_template('upload.html', result=result)
            if not file.filename.lower().endswith('.csv'):
                flash('File must be a .csv')
                return render_template('upload.html', result=result)
            if source not in ('Sifted', 'PitchBook'):
                flash('Please select a valid source.')
                return render_template('upload.html', result=result)

            from pipeline.normalizer import normalize_csv
            from pipeline.filter import apply_filter
            from pipeline.scraper import enrich_description
            from pipeline.classifier import classify_leads
            from pipeline.scorer import assign_status_and_owner
            from pipeline.why_us import generate_why_us
            from auth.routes import log_event

            result = normalize_csv(
                file.stream,
                source,
                app.config['LEAD_CONFIG'],
                current_user.full_name
            )

            # Step 3: geo + stage filter
            filtered = apply_filter(result['leads'], app.config['LEAD_CONFIG'])

            # Step 3b: scrape missing descriptions (qualifiable leads only)
            for lead in filtered['qualifiable']:
                enrich_description(lead)

            # Step 4: LLM classification (skipped if no API key)
            if os.environ.get('OPENAI_API_KEY') and filtered['qualifiable']:
                filtered['qualifiable'] = classify_leads(
                    filtered['qualifiable'], app.config['LEAD_CONFIG']
                )

            # Step 5: status + owner + why us
            for lead in filtered['qualifiable']:
                assign_status_and_owner(lead, app.config['LEAD_CONFIG'])
                lead['whyUs'] = generate_why_us(lead, app.config['LEAD_CONFIG'])

            # Merge and attach counts
            result['leads']             = filtered['qualifiable'] + filtered['no_fit']
            result['qualifiable_count'] = len(filtered['qualifiable'])
            result['no_fit_count']      = len(filtered['no_fit'])

            # Attach metadata for storage
            result['filename']  = file.filename
            result['run_name']  = run_name or file.filename.replace('.csv', '')
            result['timestamp'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            # Step 6: persist run
            save_run(result)

            log_event(
                current_user.email,
                'upload',
                f"filename={file.filename} source={source} rows={result['row_count']} run_id={result['run_id']}"
            )

        return render_template('upload.html', result=result)

    @app.route('/process', methods=['POST'])
    @login_required
    def process():
        flash('Pipeline complete — Affinity push coming in Step 7.')
        return redirect(url_for('upload'))

    @app.route('/logs')
    @login_required
    def logs():
        return render_template(
            'logs.html',
            runs=list_runs(),
            log_lines=parse_log_lines(LOG_FILE),
        )

    @app.route('/runs/<run_id>')
    @login_required
    def view_run(run_id):
        result = load_run(run_id)
        if result is None:
            flash('Run not found.')
            return redirect(url_for('logs'))
        return render_template('run.html', result=result)

    @app.route('/export/<run_id>')
    @login_required
    def export_run(run_id):
        result = load_run(run_id)
        if result is None:
            flash('Run not found.')
            return redirect(url_for('logs'))
        from pipeline.exporter import build_export_zip
        zip_bytes = build_export_zip(result)
        run_name  = result.get('run_name') or run_id[:8]
        filename  = f"{run_name}_leads.zip"
        return Response(
            zip_bytes,
            mimetype='application/zip',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
