from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
import secrets
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
# Generate a secure secret key
app.secret_key = secrets.token_hex(16)  # Or use a hard-coded string or environment variable
# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Route to redirect unauthorized users

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Database setup
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create table if it doesn't exist
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT  -- New column for image path
        )
    ''')
    conn.commit()
    conn.close()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

class User(UserMixin):
    def __init__(self, id, username, email, password):
        self.id = id
        self.username = username
        self.email = email
        self.password = password

# Load a user by ID (required by Flask-Login)
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(id=user['id'], username=user['username'], email=user['email'], password=user['password'])
    return None

# Home route - Read all posts
@app.route('/')
def index():
    conn = get_db_connection()
    # Fetch posts with the username of the author
    posts = conn.execute('''
        SELECT p.*, u.username 
        FROM posts p 
        JOIN users u ON p.user_id = u.id 
        ORDER BY p.id DESC
    ''').fetchall()

    # Check if the current user has liked each post and fetch comments
    posts_with_likes_and_comments = []
    for post in posts:
        liked = False
        if current_user.is_authenticated:
            liked = conn.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?',
                                 (current_user.id, post['id'])).fetchone() is not None

        # Fetch comments for the post
        comments = conn.execute('''
            SELECT c.*, u.username 
            FROM comments c 
            JOIN users u ON c.user_id = u.id 
            WHERE c.post_id = ?
        ''', (post['id'],)).fetchall()

        posts_with_likes_and_comments.append({**post, 'liked': liked, 'comments': comments})

    conn.close()
    return render_template('index.html', posts=posts_with_likes_and_comments)

# Create a new post
@app.route('/create', methods=['POST'])
@login_required
def create():
    title = request.form['title']
    content = request.form['content']
    image = request.files['image']

    image_path = None
    if image and allowed_file(image.filename):
        # Secure the filename and save it
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        image_path = f"/{image_path}"  # Store the relative path for the HTML

    conn = get_db_connection()
    conn.execute('INSERT INTO posts (title, content, image_path, user_id) VALUES (?, ?, ?, ?)',
                 (title, content, image_path, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Update a post
@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    title = request.form['title']
    content = request.form['content']

    conn = get_db_connection()
    conn.execute('UPDATE posts SET title = ?, content = ? WHERE id = ?', (title, content, id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# Delete a post
@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM posts WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username or email already exists!"
        finally:
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            user_obj = User(id=user['id'], username=user['username'], email=user['email'], password=user['password'])
            login_user(user_obj)
            return redirect(url_for('index'))
        return "Invalid email or password!"
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    conn = get_db_connection()
    conn.execute('INSERT INTO follows (follower_id, followed_id) VALUES (?, ?)', (current_user.id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('profile', user_id=user_id))

@app.route('/unfollow/<int:user_id>', methods=['POST'])
@login_required
def unfollow(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM follows WHERE follower_id = ? AND followed_id = ?', (current_user.id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('profile', user_id=user_id))

@app.route('/feed')
@login_required
def feed():
    conn = get_db_connection()
    # Fetch posts from users that the current user is following AND the current user's posts
    posts = conn.execute('''
        SELECT p.*, u.username 
        FROM posts p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.user_id = ? OR p.user_id IN (
            SELECT followed_id 
            FROM follows 
            WHERE follower_id = ?
        )
        ORDER BY p.id DESC
    ''', (current_user.id, current_user.id)).fetchall()

    # Check if the current user has liked each post and fetch comments
    posts_with_likes_and_comments = []
    for post in posts:
        # Check if the current user has liked the post
        liked = conn.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?',
                             (current_user.id, post['id'])).fetchone() is not None

        # Fetch comments for the post
        comments = conn.execute('''
            SELECT c.*, u.username 
            FROM comments c 
            JOIN users u ON c.user_id = u.id 
            WHERE c.post_id = ?
        ''', (post['id'],)).fetchall()

        # Combine post data with like status and comments
        posts_with_likes_and_comments.append({**post, 'liked': liked, 'comments': comments})

    conn.close()
    return render_template('feed.html', posts=posts_with_likes_and_comments)

@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    conn = get_db_connection()
    # Get user info
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    # Get user's posts
    posts = conn.execute('SELECT * FROM posts WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()

    # Check if the current user has liked each post and fetch comments
    posts_with_likes_and_comments = []
    for post in posts:
        # Check if the current user has liked the post
        liked = conn.execute('SELECT 1 FROM likes WHERE user_id = ? AND post_id = ?',
                             (current_user.id, post['id'])).fetchone() is not None

        # Fetch comments for the post
        comments = conn.execute('''
            SELECT c.*, u.username 
            FROM comments c 
            JOIN users u ON c.user_id = u.id 
            WHERE c.post_id = ?
        ''', (post['id'],)).fetchall()

        # Combine post data with like status and comments
        posts_with_likes_and_comments.append({**post, 'liked': liked, 'comments': comments})

    # Check if the current user is following this user
    is_following = conn.execute('SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = ?',
                                (current_user.id, user_id)).fetchone() is not None

    conn.close()
    return render_template('profile.html', user=user, posts=posts_with_likes_and_comments, is_following=is_following)

@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like(post_id):
    conn = get_db_connection()
    # Check if the user has already liked the post
    like = conn.execute('SELECT * FROM likes WHERE user_id = ? AND post_id = ?', (current_user.id, post_id)).fetchone()
    if like:
        # Unlike the post
        conn.execute('DELETE FROM likes WHERE id = ?', (like['id'],))
    else:
        # Like the post
        conn.execute('INSERT INTO likes (user_id, post_id) VALUES (?, ?)', (current_user.id, post_id))
    conn.commit()
    conn.close()

    # Redirect back to the page specified in the 'next' parameter
    next_page = request.form.get('next', url_for('index'))
    return redirect(next_page)

@app.route('/likes/<int:post_id>')
@login_required
def get_likes(post_id):
    conn = get_db_connection()
    likes = conn.execute('''
        SELECT u.username 
        FROM likes l 
        JOIN users u ON l.user_id = u.id 
        WHERE l.post_id = ?
    ''', (post_id,)).fetchall()
    conn.close()
    return render_template('likes.html', likes=likes)

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment(post_id):
    content = request.form['content']
    conn = get_db_connection()
    conn.execute('INSERT INTO comments (user_id, post_id, content) VALUES (?, ?, ?)', (current_user.id, post_id, content))
    conn.commit()
    conn.close()

    # Redirect back to the page specified in the 'next' parameter
    next_page = request.form.get('next', url_for('index'))
    return redirect(next_page)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)