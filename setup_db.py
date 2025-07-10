# setup_db.py
import sqlite3
import os

DB_PATH = "chat_history.db"
print(f"Creating tables in: {os.path.abspath(DB_PATH)}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS session (
        session_id TEXT PRIMARY KEY,
        phone TEXT,
        is_logged_in INTEGER DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.commit()
conn.close()

print("✅ Tables created successfully.")
