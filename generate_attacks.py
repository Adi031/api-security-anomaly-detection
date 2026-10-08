import sys
import os
import argparse
import random
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'traffic-simulator'))
from simulator import run_attack

base_url = "http://127.0.0.1:5000"
attack_types = ['credential_stuffing', 'scraping', 'enumeration', 'privilege_probe']

def worker(atype):
    try:
        run_attack(base_url, atype, evasive=random.choice([True, False]))
    except Exception as e:
        print(f"Error {atype}: {e}")

print("Generating 100 sessions for each attack type...")
with ThreadPoolExecutor(max_workers=20) as executor:
    for atype in attack_types:
        for _ in range(100):
            executor.submit(worker, atype)

print("Done generating attacks.")
