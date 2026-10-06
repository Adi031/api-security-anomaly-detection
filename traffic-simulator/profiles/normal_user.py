"""
Normal User Profile — Simulates realistic human browsing behavior.

A normal user session follows a natural flow:
  login → browse products → view details → maybe order → check orders → logout

Timing is human-like with variable delays, occasional pauses (reading),
and non-systematic endpoint access patterns.
"""

import random
import time
import requests
import logging

logger = logging.getLogger(__name__)


class NormalUser:
    """Simulates a normal, legitimate user session."""

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
        """Build headers with auth token if available."""
        h = {
            'Content-Type': 'application/json',
            'X-Session-ID': self.session_id,
            'X-Traffic-Type': 'normal',
            'User-Agent': self.user_agent,
            'X-Forwarded-For': self.ip_address
        }
        if self.token:
            h['Authorization'] = f'Bearer {self.token}'
        return h

    def _delay(self, min_s=2.0, max_s=8.0):
        """Human-like delay with slight randomness."""
        delay = random.uniform(min_s, max_s)
        # Occasionally pause longer (user is reading/thinking)
        if random.random() < 0.15:
            delay += random.uniform(3.0, 10.0)
        time.sleep(delay)

    def _safe_request(self, method, url, **kwargs):
        """Make a request with error handling."""
        try:
            resp = getattr(self.session, method)(url, headers=self._headers(), timeout=10, **kwargs)
            self.actions_taken += 1
            return resp
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request error for {self.username}: {e}")
            return None

    def login(self):
        """Log in and get auth token."""
        resp = self._safe_request('post', f'{self.base_url}/api/auth/login',
                                  json={'username': self.username, 'password': self.password})
        if resp and resp.status_code == 200:
            data = resp.json()
            self.token = data.get('token')
            logger.debug(f"{self.username} logged in successfully")
            return True
        logger.debug(f"{self.username} login failed")
        return False

    def browse_products(self):
        """Browse product listing pages (1-3 pages)."""
        num_pages = random.randint(1, 3)
        for page in range(1, num_pages + 1):
            self._delay(1.5, 5.0)
            resp = self._safe_request('get', f'{self.base_url}/api/products',
                                      params={'page': page, 'per_page': 20})
            if resp and resp.status_code == 200:
                data = resp.json()
                products = data.get('products', data) if isinstance(data, dict) else data
                if isinstance(products, list) and products:
                    # Remember some product IDs to view later
                    for p in products:
                        pid = p.get('id') if isinstance(p, dict) else None
                        if pid and random.random() < 0.4:
                            self.products_viewed.append(pid)

    def view_product_details(self):
        """View details of 2-6 products (not all — realistic browsing)."""
        if not self.products_viewed:
            # Fallback: pick random product IDs
            self.products_viewed = random.sample(range(1, 80), random.randint(2, 5))

        num_to_view = min(random.randint(2, 6), len(self.products_viewed))
        products_to_view = random.sample(self.products_viewed, num_to_view)

        for pid in products_to_view:
            self._delay(2.0, 7.0)
            self._safe_request('get', f'{self.base_url}/api/products/{pid}')
            
            # Occasionally re-visit a product (realistic behavior)
            if random.random() < 0.1 and self.products_viewed:
                revisit = random.choice(self.products_viewed)
                self._delay(1.0, 3.0)
                self._safe_request('get', f'{self.base_url}/api/products/{revisit}')

    def create_order(self):
        """Create 0-2 orders."""
        if not self.token:
            return

        num_orders = random.choices([0, 1, 2], weights=[0.3, 0.5, 0.2])[0]
        for _ in range(num_orders):
            self._delay(3.0, 8.0)
            pid = random.choice(self.products_viewed) if self.products_viewed else random.randint(1, 50)
            qty = random.randint(1, 3)
            price = round(random.uniform(10.0, 500.0), 2)
            self._safe_request('post', f'{self.base_url}/api/orders',
                               json={'product_id': pid, 'quantity': qty, 'total_price': price})

    def check_orders(self):
        """Check order list and maybe view an order detail."""
        if not self.token:
            return

        self._delay(2.0, 5.0)
        resp = self._safe_request('get', f'{self.base_url}/api/orders')
        if resp and resp.status_code == 200:
            data = resp.json()
            orders = data.get('orders', data) if isinstance(data, dict) else data
            if isinstance(orders, list) and orders and random.random() < 0.5:
                order = random.choice(orders)
                oid = order.get('id') if isinstance(order, dict) else None
                if oid:
                    self._delay(1.5, 4.0)
                    self._safe_request('get', f'{self.base_url}/api/orders/{oid}')

    def view_profile(self):
        """Occasionally view own profile."""
        if not self.token or random.random() > 0.3:
            return
        self._delay(2.0, 5.0)
        self._safe_request('get', f'{self.base_url}/api/users/{self.user_id}/profile')

    def logout(self):
        """Log out."""
        if self.token:
            self._delay(1.0, 3.0)
            self._safe_request('post', f'{self.base_url}/api/auth/logout')
            self.token = None

    def run_session(self):
        """
        Run a complete normal user session.
        Returns number of actions taken.
        """
        logger.info(f"[Normal] {self.username} starting session")
        
        if not self.login():
            return self.actions_taken

        self._delay(1.0, 3.0)

        # Natural flow with some randomization
        self.browse_products()
        self.view_product_details()
        
        # Not everyone orders
        if random.random() < 0.6:
            self.create_order()
        
        # Some users check their orders
        if random.random() < 0.4:
            self.check_orders()
        
        # Occasionally view profile
        self.view_profile()
        
        self.logout()
        
        logger.info(f"[Normal] {self.username} finished ({self.actions_taken} actions)")
        return self.actions_taken
