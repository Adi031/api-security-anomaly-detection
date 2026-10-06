import time
from flask import request, g
import uuid
from db import get_db_connection, release_db_connection
from datetime import datetime, timezone

def init_middleware(app):
    @app.before_request
    def before_request():
        g.start_time = time.time()
        g.user_id = None
        g.is_authenticated = False
        g.session_id = request.cookies.get('session_id') or request.headers.get('X-Session-ID') or str(uuid.uuid4())

    @app.after_request
    def after_request(response):
        if not hasattr(g, 'start_time'):
            return response

        response_time_ms = (time.time() - g.start_time) * 1000

        timestamp = datetime.now(timezone.utc)
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        method = request.method
        endpoint = request.path
        status_code = response.status_code
        user_agent = request.headers.get('User-Agent', '')
        traffic_type = request.headers.get('X-Traffic-Type', 'normal')

        request_body_size = request.content_length or 0
        response_body_size = response.content_length or 0

        user_id = getattr(g, 'user_id', None)
        is_authenticated = getattr(g, 'is_authenticated', False)
        session_id = getattr(g, 'session_id', None)

        if session_id:
            response.set_cookie('session_id', session_id)

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO request_logs 
                    (timestamp, user_id, session_id, ip_address, method, endpoint, 
                    status_code, response_time_ms, user_agent, request_body_size, 
                    response_body_size, is_authenticated, traffic_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (timestamp, user_id, session_id, ip_address, method, endpoint,
                     status_code, response_time_ms, user_agent, request_body_size,
                     response_body_size, is_authenticated, traffic_type)
                )
                conn.commit()
            except Exception as e:
                print(f"Failed to log request: {e}")
                conn.rollback()
            finally:
                release_db_connection(conn)

        return response
