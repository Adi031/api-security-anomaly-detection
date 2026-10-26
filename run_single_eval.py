import os
import sys
import time
import subprocess
import requests

def run_eval(run_idx):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, f"test_eval_{run_idx}.sqlite")
    
    # 1. Clean up any existing db
    for ext in ["", "-wal", "-shm"]:
        p = db_path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                print(f"Warning removing {p}: {e}")

    env = os.environ.copy()
    env["DB_PATH"] = db_path
    env["PYTHONUTF8"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    print(f"\n=======================================================")
    print(f"STARTING OUT-OF-SAMPLE EVALUATION RUN {run_idx}")
    print(f"Target DB: {db_path}")
    print(f"=======================================================")

    # 2. Initialize and seed DB
    print("[1/6] Initializing and seeding fresh database...")
    subprocess.run([sys.executable, "init_sqlite.py"], env=env, check=True)
    subprocess.run([sys.executable, "target-api/seed_db.py"], env=env, check=True)

    # 3. Start target-api
    print("[2/6] Starting target-api on 127.0.0.1:5000...")
    api_proc = subprocess.Popen([sys.executable, "target-api/app.py"], env=env)
    
    # Wait for API to respond
    ready = False
    for _ in range(30):
        try:
            r = requests.get("http://127.0.0.1:5000/api/products", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)
        
    if not ready:
        api_proc.terminate()
        raise RuntimeError("Target API failed to start on 127.0.0.1:5000")
    print("      Target API is healthy.")

    # 4. Start scoring engine
    print("[3/6] Starting scoring engine...")
    engine_proc = subprocess.Popen([sys.executable, "scoring-engine/main.py"], env=env)
    time.sleep(2)

    # 5. Launch mixed simulator + slow attacks in parallel
    print("[4/6] Launching mixed simulator (12 users, 200s, all attacks) and slow attacks in parallel...")
    sim_cmd = [
        sys.executable, "traffic-simulator/simulator.py",
        "--mode", "mixed",
        "--attack", "all",
        "--users", "12",
        "--duration", "200",
        "--base-url", "http://127.0.0.1:5000"
    ]
    slow_cmd = [sys.executable, "traffic-simulator/profiles/attacks/slow_attacks.py"]

    sim_proc = subprocess.Popen(sim_cmd, env=env)
    slow_proc = subprocess.Popen(slow_cmd, env=env)

    # Wait for both to finish
    print("      Traffic simulation in progress...")
    sim_proc.wait()
    print("      Mixed simulator finished.")
    slow_proc.wait()
    print("      Slow attacks finished.")

    # Grace period for scoring engine to flush trailing windows
    print("      Allowing scoring engine 5 seconds to process remaining logs...")
    time.sleep(5)

    # Terminate background services
    print("[5/6] Stopping target-api and scoring engine...")
    engine_proc.terminate()
    api_proc.terminate()
    try:
        engine_proc.wait(timeout=5)
    except Exception:
        engine_proc.kill()
    try:
        api_proc.wait(timeout=5)
    except Exception:
        api_proc.kill()

    # 6. Evaluate live run
    print("[6/6] Running evaluate_live.py on generated database...")
    eval_cmd = [sys.executable, "evaluate_live.py", "--db", db_path]
    res = subprocess.run(eval_cmd, env=env, capture_output=True, text=True, encoding="utf-8")
    
    output_text = res.stdout + "\n" + res.stderr
    print(output_text)

    # Save to evaluation_runs/run_N.txt
    os.makedirs(os.path.join(base_dir, "evaluation_runs"), exist_ok=True)
    out_file = os.path.join(base_dir, "evaluation_runs", f"run_{run_idx}.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(output_text)
    print(f"Saved raw output to {out_file}")

    # Clean up test DB
    print(f"Cleaning up {db_path}...")
    for ext in ["", "-wal", "-shm"]:
        p = db_path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                print(f"Warning removing {p}: {e}")

    print(f"=== RUN {run_idx} COMPLETE ===\n")

if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_eval(idx)
