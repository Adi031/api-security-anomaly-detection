"""Slow / human-paced attackers (2-6 s gaps) used to test whether the model is sensitive to evasive attacks."""
import random
import sys
import threading
import time
import uuid
import requests

BASE = "http://127.0.0.1:5000"

def sess(label):
    s = requests.Session()
    s.headers.update({
        "X-Session-ID": str(uuid.uuid4()),
        "X-Traffic-Type": label,
        "X-Forwarded-For": f"10.9.{random.randint(0,255)}.{random.randint(1,254)}",
        "User-Agent": "Mozilla/5.0 (slow-test)"
    })
    return s

def login(s, u, p="pass123"):
    try:
        r = s.post(BASE + "/api/auth/login", json={"username": u, "password": p}, timeout=10)
        if r.status_code == 200:
            s.headers["Authorization"] = "Bearer " + r.json().get("token", "")
    except Exception:
        pass

def get(s, path):
    try:
        s.get(BASE + path, timeout=10)
    except Exception:
        pass

def slow_credential_stuffing(num_attempts=40):
    s = sess("slow_credential_stuffing")
    for _ in range(num_attempts):
        try:
            s.post(BASE + "/api/auth/login", json={"username": f"user{random.randint(1,9999)}", "password": f"pw{random.randint(1,99999)}"}, timeout=10)
        except Exception:
            pass
        time.sleep(random.uniform(2, 4))

def slow_enumeration(num_requests=40):
    s = sess("slow_enumeration")
    login(s, "user_1")
    for i, oid in enumerate(random.sample(range(1, 200), min(num_requests, 190))):
        get(s, f"/api/orders/{oid}")
        time.sleep(random.uniform(2, 4))
        if i % 4 == 3:
            get(s, f"/api/products/{random.randint(1,100)}")
            time.sleep(random.uniform(2, 4))

def slow_privilege_probe(num_requests=26):
    s = sess("slow_privilege_probe")
    login(s, "user_5")
    for i in range(num_requests):
        if i in (5, 10, 15, 21):
            get(s, f"/api/users/{random.randint(1,50)}/profile")
        else:
            get(s, f"/api/products/{random.randint(1,100)}")
        time.sleep(random.uniform(3, 6))

def run_all_slow_attacks():
    ts = [
        threading.Thread(target=slow_credential_stuffing),
        threading.Thread(target=slow_enumeration),
        threading.Thread(target=slow_privilege_probe)
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

if __name__ == "__main__":
    run_all_slow_attacks()
