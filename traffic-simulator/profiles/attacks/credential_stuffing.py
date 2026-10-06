"""
Credential Stuffing Test Profile

Generates rapid, repeated login attempts with varying credentials
to test the anomaly detection system's ability to identify
automated authentication abuse patterns.

This is a TESTING TOOL for the project's own API only.
"""

import random
import time
import requests
import logging
from faker import Faker

logger = logging.getLogger(__name__)
fake = Faker()


class CredentialStuffingTest:
    """
    Simulates credential stuffing pattern for anomaly detection testing.
    
    Characteristics that distinguish this from normal traffic:
    - Extremely rapid login attempts (0.05-0.3s between requests)
    - Many different username/password combinations
    - Only hits the /login endpoint
    - Very high 401 failure rate
    """

    def __init__(self, base_url, num_attempts=200):
        self.base_url = base_url
        self.num_attempts = num_attempts
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
            'X-Traffic-Type': 'credential_stuffing',
            'User-Agent': self.user_agent,
            'X-Forwarded-For': self.ip_address
        })
        self.actions_taken = 0
        self.successes = 0
        self.failures = 0

    def _generate_credential_pair(self):
        """Generate a test credential pair."""
        username = fake.user_name() + str(random.randint(1, 9999))
        password = fake.password(length=random.randint(6, 12))
        return username, password

    def run_session(self):
        """Run the credential stuffing test."""
        logger.info(f"[CredStuff] Starting test ({self.num_attempts} attempts)")

        for i in range(self.num_attempts):
            username, password = self._generate_credential_pair()

            try:
                resp = self.session.post(
                    f'{self.base_url}/api/auth/login',
                    json={'username': username, 'password': password},
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                self.actions_taken += 1

                if resp.status_code == 200:
                    self.successes += 1
                else:
                    self.failures += 1

            except requests.exceptions.RequestException as e:
                logger.debug(f"Request error: {e}")

            # Very fast timing — characteristic of automated tools
            time.sleep(random.uniform(0.05, 0.3))

            if (i + 1) % 50 == 0:
                logger.info(f"[CredStuff] Progress: {i+1}/{self.num_attempts} "
                           f"(success: {self.successes}, fail: {self.failures})")

        logger.info(f"[CredStuff] Completed: {self.actions_taken} attempts, "
                    f"{self.successes} successes, {self.failures} failures")
        return self.actions_taken
