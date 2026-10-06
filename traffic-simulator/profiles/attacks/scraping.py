"""
Scraping Test Profile

Generates systematic, sequential endpoint traversal patterns to test
the anomaly detection system's ability to identify automated data
collection behavior.

This is a TESTING TOOL for the project's own API only.
"""

import random
import time
import requests
import logging

logger = logging.getLogger(__name__)


class ScrapingTest:
    """
    Simulates web scraping pattern for anomaly detection testing.
    
    Characteristics that distinguish this from normal traffic:
    - Sequential product ID access (1, 2, 3, 4, ...)
    - Machine-speed timing (0.01-0.1s between requests)
    - Only hits product listing/detail endpoints
    - No login, no ordering — pure data extraction pattern
    - Very high request volume in short time
    """

    def __init__(self, base_url, max_product_id=100, evasive=False):
        self.base_url = base_url
        self.max_product_id = max_product_id
        self.evasive = evasive
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
            'X-Traffic-Type': 'scraping',
            'User-Agent': self.user_agent,
            'X-Forwarded-For': self.ip_address
        })
        self.actions_taken = 0

    def run_session(self):
        """Run the scraping test."""
        logger.info(f"[Scraping] Starting test (products 1-{self.max_product_id})")

        # Phase 1: Scrape all listing pages
        page = 1
        while True:
            try:
                resp = self.session.get(
                    f'{self.base_url}/api/products',
                    params={'page': page, 'per_page': 20},
                    timeout=10
                )
                self.actions_taken += 1

                if resp.status_code != 200:
                    break

                data = resp.json()
                products = data.get('products', data) if isinstance(data, dict) else data
                if not products or (isinstance(products, list) and len(products) == 0):
                    break

                page += 1
                delay = random.uniform(1.0, 3.0) if self.evasive else random.uniform(0.05, 0.1)
                time.sleep(delay)

            except requests.exceptions.RequestException:
                break

        # Phase 2: Scrape each product detail sequentially
        for pid in range(1, self.max_product_id + 1):
            try:
                self.session.get(
                    f'{self.base_url}/api/products/{pid}',
                    timeout=10
                )
                self.actions_taken += 1
            except requests.exceptions.RequestException:
                pass

            time.sleep(random.uniform(0.01, 0.1))

            if pid % 25 == 0:
                logger.info(f"[Scraping] Progress: {pid}/{self.max_product_id}")

        logger.info(f"[Scraping] Completed: {self.actions_taken} requests")
        return self.actions_taken
