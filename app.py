import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, flash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'db')
DB_PATH = os.path.join(DB_DIR, 'tweets.db')

# Ensure db directory exists
os.makedirs(DB_DIR, exist_ok=True)

# Initialize database and create table if not exists
conn = sqlite3.connect(DB_PATH)
conn.execute('''
    CREATE TABLE IF NOT EXISTS tweets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
''')
conn.commit()
conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
''')
conn.commit()
conn.close()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tweets', methods=['GET'])
def get_tweets():
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT content, timestamp FROM tweets ORDER BY timestamp DESC'
    ).fetchall()
    conn.close()
    tweets = [
        {'content': row['content'], 'timestamp': row['timestamp']}
        for row in rows
    ]
    return jsonify(tweets)

@app.route('/api/tweets', methods=['POST'])
def post_tweet():
    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Empty content'}), 400
    timestamp = datetime.utcnow().isoformat() + 'Z'
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tweets (content, timestamp) VALUES (?, ?)',
        (content, timestamp)
    )
    conn.commit()
    conn.close()
    return jsonify({'content': content, 'timestamp': timestamp}), 201

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('ユーザー名とパスワードを入力してください。')
            return redirect(url_for('register'))
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, generate_password_hash(password)))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash('ユーザー名は既に使用されています。')
            return redirect(url_for('register'))
        conn.close()
        flash('登録完了しました。ログインしてください。')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('ログインしました。')
            return redirect(url_for('index'))
        flash('ユーザー名またはパスワードが正しくありません。')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('ログアウトしました。')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
