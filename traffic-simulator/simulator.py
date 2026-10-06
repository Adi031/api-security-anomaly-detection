"""
Traffic Simulator — Main Orchestrator

Orchestrates concurrent normal users and test traffic patterns against
the target Flask API. Generates realistic mixed traffic for training
and evaluating the anomaly detection models.

Usage:
    # Normal traffic only (for training data)
    python simulator.py --mode normal --users 20 --duration 300

    # Mixed traffic (normal + test patterns, for evaluation)
    python simulator.py --mode mixed --users 10 --attack credential_stuffing --attack-delay 30

    # Run a specific test pattern
    python simulator.py --mode attack --attack scraping

    # All test patterns
    python simulator.py --mode mixed --users 15 --attack all --attack-delay 60
"""

import argparse
import logging
import random
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from config import (
    BASE_URL, DEFAULT_NORMAL_USERS, DEFAULT_DURATION,
    DEFAULT_ATTACK_DELAY, USER_PREFIX, USER_PASSWORD, NUM_SEEDED_USERS
)
from profiles.normal_user import NormalUser
from profiles.power_user import PowerUser
from profiles.attacks.credential_stuffing import CredentialStuffingTest
from profiles.attacks.scraping import ScrapingTest
from profiles.attacks.enumeration import EnumerationTest
from profiles.attacks.privilege_probe import PrivilegeProbeTest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def create_normal_user(base_url, user_number):
    """Create a normal user instance with seeded credentials."""
    user_id = user_number
    username = f"{USER_PREFIX}{user_number}"
    password = USER_PASSWORD
    
    # 80% normal, 20% power users
    if random.random() < 0.2:
        return PowerUser(base_url, user_id, username, password)
    return NormalUser(base_url, user_id, username, password)


def run_user_loop(base_url, user_number, duration):
    """
    Run user sessions in a loop for the specified duration.
    Each user runs multiple sessions with breaks in between.
    """
    start_time = time.time()
    total_actions = 0
    sessions = 0

    while time.time() - start_time < duration:
        user = create_normal_user(base_url, user_number)
        actions = user.run_session()
        total_actions += actions
        sessions += 1

        # Break between sessions (user comes back later)
        remaining = duration - (time.time() - start_time)
        if remaining > 10:
            break_time = random.uniform(5.0, min(30.0, remaining))
            time.sleep(break_time)

    return total_actions, sessions


def run_attack(base_url, attack_type, evasive=False):
    """Run a specific test pattern and return action count."""
    if attack_type == 'credential_stuffing':
        attacker = CredentialStuffingTest(base_url, num_attempts=200)
    elif attack_type == 'scraping':
        attacker = ScrapingTest(base_url, max_product_id=100, evasive=evasive)
    elif attack_type == 'enumeration':
        attacker = EnumerationTest(base_url, max_id=150)
    elif attack_type == 'privilege_probe':
        attacker = PrivilegeProbeTest(base_url)
    else:
        logger.error(f"Unknown attack type: {attack_type}")
        return 0

    return attacker.run_session()


def main():
    parser = argparse.ArgumentParser(
        description='API Traffic Simulator for Anomaly Detection Testing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simulator.py --mode normal --users 20 --duration 300
  python simulator.py --mode mixed --users 10 --attack credential_stuffing
  python simulator.py --mode attack --attack all
        """
    )
    parser.add_argument('--mode', choices=['normal', 'attack', 'mixed'], default='normal',
                        help='Traffic mode (default: normal)')
    parser.add_argument('--users', type=int, default=30,
                        help=f'Number of concurrent normal users (default: {DEFAULT_NORMAL_USERS})')
    parser.add_argument('--duration', type=int, default=600,
                        help=f'Duration in seconds (default: {DEFAULT_DURATION})')
    parser.add_argument('--attack', type=str, default=None,
                        choices=['credential_stuffing', 'scraping', 'enumeration',
                                 'privilege_probe', 'all'],
                        help='Test pattern type to run')
    parser.add_argument('--attack-delay', type=int, default=DEFAULT_ATTACK_DELAY,
                        help=f'Delay before starting test pattern in mixed mode (default: {DEFAULT_ATTACK_DELAY}s)')
    parser.add_argument('--base-url', type=str, default=BASE_URL,
                        help=f'Target API base URL (default: {BASE_URL})')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--evasive', action='store_true',
                        help='Enable evasive mode for attacks')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    all_attack_types = ['credential_stuffing', 'scraping', 'enumeration', 'privilege_probe']

    print("\n" + "=" * 60)
    print("API Traffic Simulator")
    print("=" * 60)
    print(f"  Mode:       {args.mode}")
    print(f"  Base URL:   {args.base_url}")
    print(f"  Users:      {args.users}")
    print(f"  Duration:   {args.duration}s")
    if args.attack:
        print(f"  Test type:  {args.attack}")
    if args.mode == 'mixed':
        print(f"  Test delay: {args.attack_delay}s")
    print(f"  Started:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    start_time = time.time()
    total_actions = 0
    results = []

    if args.mode == 'normal':
        # Run only normal user traffic
        user_numbers = random.sample(range(1, NUM_SEEDED_USERS + 1), min(args.users, NUM_SEEDED_USERS))

        with ThreadPoolExecutor(max_workers=min(args.users, 20)) as executor:
            futures = {
                executor.submit(run_user_loop, args.base_url, uid, args.duration): uid
                for uid in user_numbers
            }
            for future in as_completed(futures):
                uid = futures[future]
                try:
                    actions, sessions = future.result()
                    results.append((uid, actions, sessions))
                    total_actions += actions
                except Exception as e:
                    logger.error(f"User {uid} error: {e}")

    elif args.mode == 'attack':
        # Run only test patterns
        attack_types = all_attack_types if args.attack == 'all' else [args.attack]
        
        for atype in attack_types:
            logger.info(f"Running test pattern: {atype}")
            actions = run_attack(args.base_url, atype, evasive=args.evasive)
            total_actions += actions
            results.append((atype, actions))

    elif args.mode == 'mixed':
        # Run normal users + test patterns concurrently
        if not args.attack:
            logger.error("--attack required for mixed mode")
            sys.exit(1)

        attack_types = all_attack_types if args.attack == 'all' else [args.attack]
        user_numbers = random.sample(range(1, NUM_SEEDED_USERS + 1), min(args.users, NUM_SEEDED_USERS))

        with ThreadPoolExecutor(max_workers=min(args.users + len(attack_types), 25)) as executor:
            # Start normal users immediately
            user_futures = {
                executor.submit(run_user_loop, args.base_url, uid, args.duration): f"user_{uid}"
                for uid in user_numbers
            }
            logger.info(f"Started {len(user_numbers)} normal users")

            # Wait, then start test patterns
            time.sleep(args.attack_delay)
            logger.info(f"Starting test patterns after {args.attack_delay}s delay...")

            attack_futures = {}
            for atype in attack_types:
                future = executor.submit(run_attack, args.base_url, atype, evasive=args.evasive)
                attack_futures[future] = atype

            # Collect results
            all_futures = {**user_futures, **attack_futures}
            for future in as_completed(all_futures):
                name = all_futures[future]
                try:
                    result = future.result()
                    if isinstance(result, tuple):
                        actions, sessions = result
                        results.append((name, actions, sessions))
                        total_actions += actions
                    else:
                        results.append((name, result))
                        total_actions += result
                except Exception as e:
                    logger.error(f"{name} error: {e}")

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 60)
    print("Simulation Summary")
    print("=" * 60)
    print(f"  Total requests: {total_actions}")
    print(f"  Duration:       {elapsed:.1f}s")
    print(f"  Throughput:     {total_actions / max(elapsed, 1):.1f} req/s")
    print(f"  Finished:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if results:
        print(f"\n  Details:")
        for r in results:
            if len(r) == 3:
                name, actions, sessions = r
                print(f"    {name}: {actions} actions in {sessions} sessions")
            else:
                name, actions = r
                print(f"    {name}: {actions} actions")
    
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
