import sqlite3

conn = sqlite3.connect('database.sqlite')
cursor = conn.cursor()

for sid_prefix in ['25cfc6e6', '975892e1', '9f17be76', '4bacfb6f', '876aa47a', '6788cf94', 'faab72dd']:
    cursor.execute("""
        SELECT session_id, count(*), min(timestamp), max(timestamp)
        FROM request_logs 
        WHERE session_id LIKE ? 
        GROUP BY session_id
    """, (f"{sid_prefix}%",))
    res = cursor.fetchall()
    print(f"Session {sid_prefix}: {res}")

print("\n--- Now checking active sessions in last 5 min ---")
now = cursor.execute("SELECT datetime('now')").fetchone()[0]
print(f"Current DB time: {now}")

cursor.execute("""
    SELECT session_id, count(*) as request_count, max(timestamp) as last_seen
    FROM request_logs 
    WHERE timestamp >= datetime('now', '-5 minute')
    GROUP BY session_id 
    ORDER BY max(timestamp) DESC
""")
active = cursor.fetchall()
print(f"Total active sessions in last 5m: {len(active)}")
for a in active[:10]:
    print("  Active:", a)

conn.close()
