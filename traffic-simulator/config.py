"""
Traffic Simulator Configuration
"""

# Target API base URL
BASE_URL = "http://localhost:5000"

# Default simulation parameters
DEFAULT_NORMAL_USERS = 10
DEFAULT_DURATION = 300  # seconds
DEFAULT_ATTACK_DELAY = 30  # seconds before starting attack in mixed mode

# User credentials pattern (matches seed_db.py)
USER_PREFIX = "user_"
USER_PASSWORD = "pass123"
NUM_SEEDED_USERS = 50

# Timing profiles (seconds)
NORMAL_USER_DELAY = (2.0, 8.0)     # Random delay range for normal users
POWER_USER_DELAY = (1.0, 4.0)      # Faster but still human-like
READING_PAUSE = (3.0, 15.0)         # Longer pause (simulating reading a page)

# Session parameters
NORMAL_SESSION_ACTIONS = (5, 15)    # Min-max actions per normal session
POWER_SESSION_ACTIONS = (15, 30)    # Power users do more

# Product browsing
MAX_PRODUCT_PAGES = 5
MAX_PRODUCT_ID = 100
