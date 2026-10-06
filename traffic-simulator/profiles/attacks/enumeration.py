"""
Enumeration Test Profile

Generates sequential resource ID probing patterns to test the anomaly
detection system's ability to identify automated enumeration behavior.

This is a TESTING TOOL for the project's own API only.
"""

import random
import time
import requests
import logging

logger = logging.getLogger(__name__)


class EnumerationTest:
    """
    Simulates resource enumeration pattern for anomaly detection testing.
    
    Characteristics that distinguish this from normal traffic:
    - Sequential probing of resource IDs (orders, users)
    - Mix of 200 (found) and 404 (not found) responses
    - Accessing resources that don't belong to the user
    - Fast timing (0.05-0.2s between requests)
    - Methodical, linear traversal pattern
    """

    def __init__(self, base_url, username="user_1", password="pass123", max_id=200):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.max_id = max_id
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
            'X-Traffic-Type': 'enumeration',
            'User-Agent': self.user_agent,
            'X-Forwarded-For': self.ip_address
        })
        self.token = None
        self.actions_taken = 0
        self.found = 0
        self.not_found = 0

    def _headers(self):
        h = {'Content-Type': 'application/json'}
        if self.token:
            h['Authorization'] = f'Bearer {self.token}'
        return h

    def login(self):
        """Login to get auth token for probing protected endpoints."""
        try:
            resp = self.session.post(
                f'{self.base_url}/api/auth/login',
                json={'username': self.username, 'password': self.password},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            if resp.status_code == 200:
                self.token = resp.json().get('token')
                self.actions_taken += 1
                return True
        except requests.exceptions.RequestException:
            pass
        return False

    def run_session(self):
        """Run the enumeration test."""
        logger.info(f"[Enum] Starting test (IDs 1-{self.max_id})")

        self.login()

        # Enumerate order IDs
        logger.info("[Enum] Phase 1: Probing order IDs")
        for oid in range(1, self.max_id + 1):
            try:
                resp = self.session.get(
                    f'{self.base_url}/api/orders/{oid}',
                    headers=self._headers(),
                    timeout=10
                )
                self.actions_taken += 1

                if resp.status_code == 200:
                    self.found += 1
                elif resp.status_code == 404:
                    self.not_found += 1

            except requests.exceptions.RequestException:
                pass

            time.sleep(random.uniform(0.05, 0.2))

            if oid % 50 == 0:
                logger.info(f"[Enum] Orders progress: {oid}/{self.max_id} "
                           f"(found: {self.found}, 404: {self.not_found})")

        # Enumerate user profiles
        logger.info("[Enum] Phase 2: Probing user profiles")
        for uid in range(1, min(self.max_id, 60) + 1):
            try:
                resp = self.session.get(
                    f'{self.base_url}/api/users/{uid}/profile',
                    headers=self._headers(),
                    timeout=10
                )
                self.actions_taken += 1

                if resp.status_code == 200:
                    self.found += 1
                elif resp.status_code == 404:
                    self.not_found += 1

            except requests.exceptions.RequestException:
                pass

            time.sleep(random.uniform(0.05, 0.2))

        logger.info(f"[Enum] Completed: {self.actions_taken} requests, "
                    f"found: {self.found}, not found: {self.not_found}")
        return self.actions_taken
