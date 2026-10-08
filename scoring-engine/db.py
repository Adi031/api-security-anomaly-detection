import aiosqlite
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database.sqlite')

class Database:
    def __init__(self):
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(DB_PATH, timeout=15.0)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute('PRAGMA journal_mode=WAL;')

    async def disconnect(self):
        if self.conn:
            await self.conn.close()

    async def fetch_new_logs(self, last_id: int):
        query = """
            SELECT id, timestamp, user_id, session_id, ip_address, method, endpoint, 
                   status_code, response_time_ms, user_agent, request_body_size, 
                   response_body_size, is_authenticated, traffic_type
            FROM request_logs
            WHERE id > ?
            ORDER BY id ASC
        """
        async with self.conn.execute(query, (last_id,)) as cursor:
            records = await cursor.fetchall()
        return [dict(r) for r in records]

    async def insert_alert(self, alert: dict):
        query = """
            INSERT INTO alerts (timestamp, session_id, user_id, ip_address, anomaly_score, 
                                severity, model_type, description, feature_contributions, 
                                window_start, window_end, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        async with self.conn.execute(
            query,
            (alert['timestamp'], alert['session_id'], alert.get('user_id'), 
             alert['ip_address'], alert['anomaly_score'], alert['severity'], 
             alert['model_type'], alert['description'], 
             json.dumps(alert['feature_contributions']),
             alert['window_start'], alert['window_end'], alert.get('resolved', False))
        ) as cursor:
            alert_id = cursor.lastrowid
        await self.conn.commit()
        return alert_id

    async def fetch_alerts(self, limit: int = 20, offset: int = 0, severity: str = None):
        query = "SELECT * FROM alerts"
        args = []
        if severity:
            query += " WHERE severity = ?"
            args.append(severity)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        args.extend([limit, offset])
        
        async with self.conn.execute(query, args) as cursor:
            records = await cursor.fetchall()
        return [dict(r) for r in records]
        
    async def fetch_session(self, session_id: str):
        query = "SELECT * FROM request_logs WHERE session_id = ? ORDER BY timestamp ASC"
        async with self.conn.execute(query, (session_id,)) as cursor:
            records = await cursor.fetchall()
        return [dict(r) for r in records]
        
    async def fetch_recent_session(self, session_id: str, latest_ts: str, seconds: int = 60):
        query = "SELECT * FROM request_logs WHERE session_id = ? AND timestamp >= datetime(?, ?) AND timestamp <= ? ORDER BY timestamp ASC"
        async with self.conn.execute(query, (session_id, latest_ts, f"-{seconds} second", latest_ts)) as cursor:
            records = await cursor.fetchall()
        return [dict(r) for r in records]

    async def fetch_active_sessions(self):
        query = """
            SELECT session_id, count(*) as request_count 
            FROM request_logs 
            GROUP BY session_id 
            ORDER BY max(timestamp) DESC 
            LIMIT 50
        """
        async with self.conn.execute(query) as cursor:
            records = await cursor.fetchall()
        return [dict(r) for r in records]

    async def insert_scored_requests(self, batch: list):
        query = """
            INSERT INTO scored_requests (request_log_id, anomaly_score, severity)
            VALUES (?, ?, ?)
        """
        async with self.conn.executemany(query, batch) as cursor:
            pass
        await self.conn.commit()

db = Database()
