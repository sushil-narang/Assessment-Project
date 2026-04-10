# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime
from flask_moment import Moment

from config import Config
from questions import questions as mcq_questions # Renamed to avoid conflict with local 'questions' variable

app = Flask(__name__)
app.config.from_object(Config)
moment = Moment(app)
# Database setup
DATABASE = app.config['DATABASE']

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                date_attempted DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        db.commit()

# Ensure database is initialized when the app starts
with app.app_context():
    init_db()

# User session management
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()
import functools
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('You need to be logged in to view that page.', 'warning')
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user: # If already logged in, redirect to home
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                db.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = f"User {username} is already registered."
            else:
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('login'))

        flash(error, 'danger')

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user: # If already logged in, redirect to home
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            flash('You have been logged in!', 'success')
            return redirect(url_for('index'))

        flash(error, 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/test', methods=('GET', 'POST'))
@login_required
def test():
    if request.method == 'POST':
        user_answers = {}
        for q in mcq_questions:
            answer = request.form.get(f'question_{q["id"]}')
            if answer:
                user_answers[q["id"]] = answer
        
        score = 0
        for q in mcq_questions:
            if user_answers.get(q["id"]) == q["answer"]:
                score += 1
        
        # Store score in the database
        db = get_db()
        db.execute(
            "INSERT INTO scores (user_id, score, date_attempted) VALUES (?, ?, ?)",
            (g.user['id'], score, datetime.now())
        )
        db.commit()

        flash(f'Test completed! Your score: {score}/{len(mcq_questions)}', 'success')
        return redirect(url_for('result'))
    
    return render_template('test.html', questions=mcq_questions)

@app.route('/result')
@login_required
def result():
    db = get_db()
    user_scores = db.execute(
        'SELECT score, date_attempted FROM scores WHERE user_id = ? ORDER BY date_attempted DESC',
        (g.user['id'],)
    ).fetchall()
    
    return render_template('result.html', scores=user_scores)


if __name__ == '__main__':
    app.run(debug=True)