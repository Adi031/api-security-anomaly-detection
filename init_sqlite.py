import sqlite3
import os

def init_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.sqlite')
    print(f"Initializing SQLite database at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(80) UNIQUE NOT NULL,
        password_hash VARCHAR(256) NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        role VARCHAR(20) DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        price DECIMAL(10, 2) NOT NULL,
        category VARCHAR(50),
        stock INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL DEFAULT 1,
        total_price DECIMAL(10, 2) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    """)
    
    # Request logs table — with traffic_type for labeling (fix #4)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS request_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER,
        session_id VARCHAR(64),
        ip_address VARCHAR(45),
        method VARCHAR(10) NOT NULL,
        endpoint VARCHAR(500) NOT NULL,
        status_code INTEGER NOT NULL,
        response_time_ms REAL,
        user_agent VARCHAR(500),
        request_body_size INTEGER DEFAULT 0,
        response_body_size INTEGER DEFAULT 0,
        is_authenticated BOOLEAN DEFAULT 0,
        traffic_type VARCHAR(30) DEFAULT 'normal'
    )
    """)
    
    # Alerts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        session_id VARCHAR(64),
        user_id INTEGER,
        ip_address VARCHAR(45),
        anomaly_score REAL NOT NULL,
        severity VARCHAR(20) NOT NULL,
        model_type VARCHAR(50),
        description TEXT,
        feature_contributions TEXT,
        window_start TIMESTAMP,
        window_end TIMESTAMP,
        resolved BOOLEAN DEFAULT 0
    )
    """)
    
    # Scored requests table — stores per-request anomaly scores (fix #21)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scored_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_log_id INTEGER NOT NULL,
        anomaly_score REAL NOT NULL,
        severity VARCHAR(20) NOT NULL,
        scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (request_log_id) REFERENCES request_logs(id)
    )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_session ON request_logs(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_traffic_type ON request_logs(traffic_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scored_requests_log_id ON scored_requests(request_log_id)")
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
