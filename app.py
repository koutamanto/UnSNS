import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, flash
from functools import wraps
from werkzeug.utils import secure_filename
import json
from pywebpush import webpush, WebPushException

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
VAPID_CLAIMS = {"sub": "mailto:your-email@example.com"}

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
        timestamp TEXT NOT NULL,
        user_id INTEGER,
        parent_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
''')
conn.commit()
# Add avatar column if not present
conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        bio TEXT DEFAULT '',
        avatar TEXT
    )
''')
conn.commit()
# Migrate tweets table to include user_id column if not present
cursor = conn.execute("PRAGMA table_info(tweets)")
existing_cols = [row[1] for row in cursor.fetchall()]
if 'user_id' not in existing_cols:
    conn.execute("ALTER TABLE tweets ADD COLUMN user_id INTEGER")
    conn.commit()
# Migrate tweets table to include parent_id column if not present
cursor = conn.execute("PRAGMA table_info(tweets)")
cols = [row[1] for row in cursor.fetchall()]
if 'parent_id' not in cols:
    conn.execute("ALTER TABLE tweets ADD COLUMN parent_id INTEGER")
    conn.commit()
# Migrate users table to include bio column if not present
cursor = conn.execute("PRAGMA table_info(users)")
existing_user_cols = [row[1] for row in cursor.fetchall()]
if 'bio' not in existing_user_cols:
    conn.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT ''")
    conn.commit()
# Migrate users table to include avatar column if not present
if 'avatar' not in existing_user_cols:
    conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
    conn.commit()
conn.close()

# Create subscriptions table
conn = sqlite3.connect(DB_PATH)
conn.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT NOT NULL,
        p256dh TEXT NOT NULL,
        auth TEXT NOT NULL
    )
''')
conn.commit()
conn.close()

# Create tweet likes table
conn = sqlite3.connect(DB_PATH)
conn.execute('''
    CREATE TABLE IF NOT EXISTS tweet_likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tweet_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY(tweet_id) REFERENCES tweets(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
''')
conn.commit()
conn.close()

# Ensure uploads folder exists
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_push_notification(data):
    conn = get_db_connection()
    subs = conn.execute('SELECT endpoint, p256dh, auth FROM subscriptions').fetchall()
    conn.close()
    for s in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": s["endpoint"],
                    "keys": {"p256dh": s["p256dh"], "auth": s["auth"]}
                },
                data=json.dumps(data),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_public_key=VAPID_PUBLIC_KEY,
                vapid_claims=VAPID_CLAIMS
            )
        except WebPushException as ex:
            print("Web push failed: {}", repr(ex))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tweets', methods=['GET'])
def get_tweets():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT t.id, t.content, t.timestamp, t.parent_id,
               u.username, u.avatar, 
               COUNT(l.id) AS like_count
        FROM tweets t
        LEFT JOIN users u ON t.user_id = u.id
        LEFT JOIN tweet_likes l ON t.id = l.tweet_id
        GROUP BY t.id
        ORDER BY t.timestamp DESC
    ''').fetchall()
    conn.close()
    tweets = [
        {
            'id': row['id'],
            'content': row['content'],
            'timestamp': row['timestamp'],
            'parent_id': row['parent_id'],
            'username': row['username'] or '匿名',
            'avatar': row['avatar'],
            'like_count': row['like_count']
        }
        for row in rows
    ]
    return jsonify(tweets)

@app.route('/api/tweets', methods=['POST'])
def post_tweet():
    if 'user_id' not in session:
        return jsonify({'error': 'ログインが必要です'}), 401
    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Empty content'}), 400
    parent_id = data.get('parent_id')
    timestamp = datetime.utcnow().isoformat() + 'Z'
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tweets (content, timestamp, user_id, parent_id) VALUES (?, ?, ?, ?)',
        (content, timestamp, session['user_id'], parent_id)
    )
    conn.commit()
    # send browser push notification
    send_push_notification({"title": "UnSNS", "body": content})
    conn.close()
    return jsonify({'content': content, 'timestamp': timestamp}), 201

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        bio = request.form.get('bio', '').strip()
        if not username or not password:
            flash('ユーザー名とパスワードを入力してください。')
            return redirect(url_for('register'))
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, password, bio) VALUES (?, ?, ?)',
                (username, generate_password_hash(password), bio)
            )
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

@app.route('/profile/<username>', methods=['GET', 'POST'])
def profile(username):
    conn = get_db_connection()
    if request.method == 'POST':
        if session.get('username') == username:
            bio = request.form.get('bio', '').strip()
            conn.execute('UPDATE users SET bio = ? WHERE username = ?', (bio, username))
            conn.commit()
            flash('プロフィールを更新しました。')
            return redirect(url_for('profile', username=username))
        flash('権限がありません。')
        return redirect(url_for('index'))
    user_row = conn.execute('SELECT id, username, bio, avatar FROM users WHERE username = ?', (username,)).fetchone()
    if not user_row:
        conn.close()
        return "ユーザーが見つかりません", 404
    tweets_rows = conn.execute(
        'SELECT content, timestamp FROM tweets WHERE user_id = ? ORDER BY timestamp DESC',
        (user_row['id'],)
    ).fetchall()
    conn.close()
    tweets = [{'content': r['content'], 'timestamp': r['timestamp']} for r in tweets_rows]
    return render_template('profile.html', user={'username': user_row['username'], 'bio': user_row['bio'], 'avatar': user_row['avatar']}, tweets=tweets)


# /home route: profile edit for logged-in user
@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    conn = get_db_connection()
    if request.method == 'POST':
        avatar = request.files.get('avatar')
        if avatar and allowed_file(avatar.filename):
            filename = secure_filename(f"{session['user_id']}_{avatar.filename}")
            avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn.execute('UPDATE users SET avatar = ? WHERE id = ?', (filename, session['user_id']))
        bio = request.form.get('bio', '').strip()
        conn.execute(
            'UPDATE users SET bio = ? WHERE id = ?',
            (bio, session['user_id'])
        )
        conn.commit()
        conn.close()
        flash('プロフィールを更新しました。')
        return redirect(url_for('home'))
    user_row = conn.execute(
        'SELECT username, bio, avatar FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()
    return render_template('home.html', user={'username': user_row['username'], 'bio': user_row['bio'], 'avatar': user_row['avatar']})

@app.route('/subscribe', methods=['POST'])
def subscribe():
    sub = request.get_json()
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO subscriptions (endpoint, p256dh, auth) VALUES (?, ?, ?)',
        (sub["endpoint"], sub["keys"]["p256dh"], sub["keys"]["auth"])
    )
    conn.commit()
    conn.close()
    return '', 201

@app.route('/api/tweets/<int:tweet_id>/likes', methods=['GET'])
def get_likes(tweet_id):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.username FROM tweet_likes tl
        JOIN users u ON tl.user_id = u.id
        WHERE tl.tweet_id = ?
    ''', (tweet_id,)).fetchall()
    conn.close()
    return jsonify([{'username': r['username']} for r in rows])

@app.route('/api/tweets/<int:tweet_id>/likes', methods=['POST'])
def toggle_like(tweet_id):
    if 'user_id' not in session:
        return jsonify({'error': 'ログインが必要です'}), 401
    user_id = session['user_id']
    conn = get_db_connection()
    existing = conn.execute(
        'SELECT id FROM tweet_likes WHERE tweet_id = ? AND user_id = ?',
        (tweet_id, user_id)
    ).fetchone()
    if existing:
        conn.execute('DELETE FROM tweet_likes WHERE id = ?', (existing['id'],))
    else:
        conn.execute('INSERT INTO tweet_likes (tweet_id, user_id) VALUES (?, ?)', (tweet_id, user_id))
    conn.commit()
    # get new count
    count = conn.execute(
        'SELECT COUNT(*) AS cnt FROM tweet_likes WHERE tweet_id = ?',
        (tweet_id,)
    ).fetchone()['cnt']
    conn.close()
    return jsonify({'like_count': count})

@app.route('/api/tweets/<int:tweet_id>', methods=['DELETE'])
def delete_tweet(tweet_id):
    if 'user_id' not in session:
        return jsonify({'error': 'ログインが必要です'}), 401
    conn = get_db_connection()
    row = conn.execute(
        'SELECT user_id FROM tweets WHERE id = ?', (tweet_id,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '投稿が見つかりません'}), 404
    if row['user_id'] != session['user_id']:
        conn.close()
        return jsonify({'error': '権限がありません'}), 403
    conn.execute('DELETE FROM tweets WHERE id = ?', (tweet_id,))
    conn.commit()
    conn.close()
    return '', 204

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True, port=443, ssl_context=('ssl/cert.pem', 'ssl/privkey.key'))