import sqlite3

# Connect to the SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('database.db')

conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
conn.execute('''
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        image_path TEXT,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
''')
conn.execute('''
    CREATE TABLE IF NOT EXISTS follows (
        follower_id INTEGER NOT NULL,
        followed_id INTEGER NOT NULL,
        PRIMARY KEY (follower_id, followed_id),
        FOREIGN KEY (follower_id) REFERENCES users (id),
        FOREIGN KEY (followed_id) REFERENCES users (id)
    )
''')

# Commit changes and close the connection
conn.commit()
conn.close()