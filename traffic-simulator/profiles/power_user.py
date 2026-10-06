"""
Power User Profile — High-volume but legitimate browsing.

Power users are active, fast browsers who view many products and place
multiple orders, but still follow natural patterns and human-like timing.
"""

import random
import time
import requests
import logging

logger = logging.getLogger(__name__)


class PowerUser:
    """Simulates a high-volume but legitimate power user."""

    def __init__(self, base_url, user_id, username, password):
        self.base_url = base_url
        self.user_id = user_id
        self.username = username
        self.password = password
        self.token = None
        self.session = requests.Session()
        self.actions_taken = 0
        self.products_viewed = []
        import uuid
        self.session_id = str(uuid.uuid4())
        self.user_agent = random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
        ])
        self.ip_address = f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"

    def _headers(self):
        h = {
            'Content-Type': 'application/json',
            'X-Session-ID': self.session_id,
            'X-Traffic-Type': 'power',
            'User-Agent': self.user_agent,
            'X-Forwarded-For': self.ip_address
        }
        if self.token:
            h['Authorization'] = f'Bearer {self.token}'
        return h

    def _delay(self, min_s=1.0, max_s=4.0):
        """Faster but still human-like delays."""
        delay = random.uniform(min_s, max_s)
        if random.random() < 0.1:
            delay += random.uniform(2.0, 6.0)
        time.sleep(delay)

    def _safe_request(self, method, url, **kwargs):
        try:
            resp = getattr(self.session, method)(url, headers=self._headers(), timeout=10, **kwargs)
            self.actions_taken += 1
            return resp
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request error for {self.username}: {e}")
            return None

    def login(self):
        resp = self._safe_request('post', f'{self.base_url}/api/auth/login',
                                  json={'username': self.username, 'password': self.password})
        if resp and resp.status_code == 200:
            data = resp.json()
            self.token = data.get('token')
            return True
        return False

    def browse_extensively(self):
        """Browse many product pages."""
        num_pages = random.randint(3, 7)
        for page in range(1, num_pages + 1):
            self._delay(1.0, 3.0)
            resp = self._safe_request('get', f'{self.base_url}/api/products',
                                      params={'page': page, 'per_page': 20})
            if resp and resp.status_code == 200:
                data = resp.json()
                products = data.get('products', data) if isinstance(data, dict) else data
                if isinstance(products, list):
                    for p in products:
                        pid = p.get('id') if isinstance(p, dict) else None
                        if pid and random.random() < 0.5:
                            self.products_viewed.append(pid)

    def view_many_products(self):
        """View 8-15 product details."""
        if not self.products_viewed:
            self.products_viewed = random.sample(range(1, 80), random.randint(8, 15))

        num_to_view = min(random.randint(8, 15), len(self.products_viewed))
        products = random.sample(self.products_viewed, num_to_view)

        for pid in products:
            self._delay(1.0, 3.5)
            self._safe_request('get', f'{self.base_url}/api/products/{pid}')

    def create_multiple_orders(self):
        """Create 3-5 orders."""
        if not self.token:
            return

        num_orders = random.randint(3, 5)
        for _ in range(num_orders):
            self._delay(2.0, 5.0)
            pid = random.choice(self.products_viewed) if self.products_viewed else random.randint(1, 50)
            qty = random.randint(1, 5)
            price = round(random.uniform(10.0, 500.0), 2)
            self._safe_request('post', f'{self.base_url}/api/orders',
                               json={'product_id': pid, 'quantity': qty, 'total_price': price})

    def check_all_orders(self):
        """Review all orders."""
        if not self.token:
            return
        self._delay(1.5, 3.0)
        resp = self._safe_request('get', f'{self.base_url}/api/orders')
        if resp and resp.status_code == 200:
            data = resp.json()
            orders = data.get('orders', data) if isinstance(data, dict) else data
            if isinstance(orders, list):
                for order in orders[:5]:
                    oid = order.get('id') if isinstance(order, dict) else None
                    if oid:
                        self._delay(1.0, 2.5)
                        self._safe_request('get', f'{self.base_url}/api/orders/{oid}')

    def logout(self):
        if self.token:
            self._delay(0.5, 2.0)
            self._safe_request('post', f'{self.base_url}/api/auth/logout')
            self.token = None

    def run_session(self):
        """Run a complete power user session."""
        logger.info(f"[Power] {self.username} starting session")

        if not self.login():
            return self.actions_taken

        self._delay(0.5, 2.0)
        self.browse_extensively()
        self.view_many_products()
        self.create_multiple_orders()
        self.check_all_orders()

        self._delay(1.0, 3.0)
        self._safe_request('get', f'{self.base_url}/api/users/{self.user_id}/profile')

        self.logout()

        logger.info(f"[Power] {self.username} finished ({self.actions_taken} actions)")
        return self.actions_taken
