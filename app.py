from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

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

# Home route - Read all posts
@app.route('/')
def index():
    conn = get_db_connection()
    posts = conn.execute('SELECT * FROM posts').fetchall()
    conn.close()
    return render_template('index.html', posts=posts)

# Create a new post
@app.route('/create', methods=['POST'])
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
    conn.execute('INSERT INTO posts (title, content, image_path) VALUES (?, ?, ?)', (title, content, image_path))
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)