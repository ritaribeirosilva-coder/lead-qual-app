import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

USERS_FILE = Path(__file__).parent.parent / 'users.json'
LOG_FILE = Path(__file__).parent.parent / 'logs' / 'activity.log'
ALLOWED_DOMAIN = 'semapanext.com'


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class User(UserMixin):
    def __init__(self, email, full_name, password_hash):
        self.id = email
        self.email = email
        self.full_name = full_name
        self.password_hash = password_hash

    @classmethod
    def get(cls, email):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            for u in users:
                if u['email'].lower() == email.lower():
                    return cls(u['email'], u['full_name'], u['password_hash'])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return None

    @classmethod
    def all(cls):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            return [cls(u['email'], u['full_name'], u['password_hash']) for u in users]
        except (FileNotFoundError, json.JSONDecodeError):
            return []


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_event(email, action, extra=''):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    line = f"{timestamp} | {action} | {email} | {extra}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('upload'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Domain check
        domain = email.split('@')[-1] if '@' in email else ''
        if domain != ALLOWED_DOMAIN:
            flash('Access restricted to Semapa Next team members.')
            return render_template('login.html')

        # Credential check
        user = User.get(email)
        if user and check_password_hash(user.password_hash, password):
            log_event(user.email, 'login')
            login_user(user)
            return redirect(url_for('upload'))

        flash('Invalid email or password.')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_event(current_user.email, 'logout')
    logout_user()
    return redirect(url_for('auth.login'))
