import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.sqlite')

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        conn.execute('PRAGMA journal_mode=WAL;')
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def release_db_connection(conn):
    if conn:
        conn.close()
