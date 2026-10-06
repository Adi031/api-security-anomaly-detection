"""
Privilege Probe Test Profile

Simulates a user who starts with normal behavior then suddenly shifts
to accessing endpoints and resources outside their normal pattern.

This is a TESTING TOOL for the project's own API only.
"""

import random
import time
import requests
import logging

logger = logging.getLogger(__name__)


class PrivilegeProbeTest:
    """
    Simulates privilege escalation / anomalous access pattern.
    
    Characteristics that distinguish this from normal traffic:
    - Starts with normal browsing behavior (camouflage)
    - Then abruptly switches to accessing other users' data
    - Tries to access resources belonging to different user IDs
    - Accesses endpoints outside the user's normal pattern
    - The behavioral SHIFT is the anomaly signal
    """

    def __init__(self, base_url, username="user_5", password="pass123", user_id=5):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.user_id = user_id
        self.session = requests.Session()
        import uuid
        import random
        self.session_id = str(uuid.uuid4())
        self.user_agent = random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
        ])
        self.ip_address = f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"
        self.session.headers.update({
            'X-Session-ID': self.session_id,
            'X-Traffic-Type': 'privilege_probe',
            'User-Agent': self.user_agent,
            'X-Forwarded-For': self.ip_address
        })
        self.token = None
        self.actions_taken = 0

    def _headers(self):
        h = {'Content-Type': 'application/json'}
        if self.token:
            h['Authorization'] = f'Bearer {self.token}'
        return h

    def _safe_request(self, method, url, **kwargs):
        try:
            resp = getattr(self.session, method)(url, headers=self._headers(), timeout=10, **kwargs)
            self.actions_taken += 1
            return resp
        except requests.exceptions.RequestException:
            return None

    def login(self):
        resp = self._safe_request('post', f'{self.base_url}/api/auth/login',
                                  json={'username': self.username, 'password': self.password})
        if resp and resp.status_code == 200:
            self.token = resp.json().get('token')
            return True
        return False

    def normal_phase(self):
        """Start with normal-looking behavior for camouflage."""
        # Browse some products normally
        for _ in range(random.randint(3, 5)):
            time.sleep(random.uniform(2.0, 5.0))
            self._safe_request('get', f'{self.base_url}/api/products',
                               params={'page': random.randint(1, 3)})

        # View a couple of products
        for pid in random.sample(range(1, 50), random.randint(2, 4)):
            time.sleep(random.uniform(2.0, 6.0))
            self._safe_request('get', f'{self.base_url}/api/products/{pid}')

        # View own profile (normal)
        time.sleep(random.uniform(1.0, 3.0))
        self._safe_request('get', f'{self.base_url}/api/users/{self.user_id}/profile')

    def probe_phase(self):
        """
        Shift to anomalous behavior — probe other users' data.
        The abrupt behavioral change is what the model should detect.
        """
        # Access OTHER users' profiles (not own)
        for target_uid in range(1, 30):
            if target_uid == self.user_id:
                continue
            time.sleep(random.uniform(0.3, 1.0))
            self._safe_request('get', f'{self.base_url}/api/users/{target_uid}/profile')

        # Try to access other users' orders
        for oid in random.sample(range(1, 100), 20):
            time.sleep(random.uniform(0.2, 0.8))
            self._safe_request('get', f'{self.base_url}/api/orders/{oid}')

        # Try to modify another user's profile
        for target_uid in random.sample(range(1, 20), 5):
            if target_uid == self.user_id:
                continue
            time.sleep(random.uniform(0.3, 1.0))
            self._safe_request('put', f'{self.base_url}/api/users/{target_uid}/profile',
                               json={'email': f'hacked_{target_uid}@test.com'})

    def run_session(self):
        """Run the privilege probe test."""
        logger.info(f"[PrivProbe] Starting test as {self.username}")

        if not self.login():
            logger.warning(f"[PrivProbe] Login failed for {self.username}")
            return self.actions_taken

        # Phase 1: Normal behavior (camouflage)
        logger.info("[PrivProbe] Phase 1: Normal behavior")
        self.normal_phase()

        # Phase 2: Privilege probing (anomalous shift)
        logger.info("[PrivProbe] Phase 2: Probing other users' data")
        self.probe_phase()

        logger.info(f"[PrivProbe] Completed: {self.actions_taken} requests")
        return self.actions_taken
