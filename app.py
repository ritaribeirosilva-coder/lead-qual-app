import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required

load_dotenv()

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / 'config.json'


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

    from auth.routes import User

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
            file = request.files.get('file')
            source = request.form.get('source', '').strip()

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
            from auth.routes import log_event

            result = normalize_csv(
                file.stream,
                source,
                app.config['LEAD_CONFIG'],
                current_user.full_name
            )

            log_event(
                current_user.email,
                'upload',
                f"filename={file.filename} source={source} rows={result['row_count']}"
            )

        return render_template('upload.html', result=result)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
