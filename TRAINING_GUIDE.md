# End-to-End Model Training & Reproduction Manual

This guide provides the complete, step-by-step instructions to train the **API Behavioral Anomaly Detection** models from a completely blank project state and reproduce the exact benchmark results.

---

## Prerequisites & Environment
Ensure you are in the root project directory (`d:\Project-7th-Sem` or your workspace root) and have Python installed with required packages (`torch`, `numpy`, `pandas`, `scikit-learn`, `flask`, `fastapi`, `aiosqlite`, `requests`).

Set UTF-8 console encoding before running Python commands:
```powershell
$env:PYTHONUTF8=1
```

---

## Phase 1: Initialize Fresh Database & Start API Server

Open **Terminal 1** at the project root:

```powershell
# 1. Initialize clean SQLite tables
python init_sqlite.py

# 2. Seed default users, products, and initial orders
python target-api/seed_db.py

# 3. Start the Target API server
python target-api/app.py
```
> **Leave Terminal 1 running.** The API server will be available at `http://127.0.0.1:5000`.

---

## Phase 2: Generate Training & Evaluation Traffic

Open **Terminal 2** at the project root.

### Step A: Generate Legitimate Human & Power-User Traffic
To ensure the autoencoder captures natural human inter-arrival variance and burst traffic without exploding $z$-scores, generate at least 150 sessions reaching $\ge 10$ requests across three concurrency batches:

```powershell
# Batch 1: 12 users, 120 seconds
python traffic-simulator/simulator.py --mode normal --users 12 --duration 120 --base-url http://127.0.0.1:5000

# Batch 2: 35 users, 180 seconds (higher concurrency)
python traffic-simulator/simulator.py --mode normal --users 35 --duration 180 --base-url http://127.0.0.1:5000

# Batch 3: 25 users, 120 seconds
python traffic-simulator/simulator.py --mode normal --users 25 --duration 120 --base-url http://127.0.0.1:5000
```

Verify that you have met the session quota ($\ge 150$ sessions):
```powershell
python -c "import sqlite3; conn = sqlite3.connect('database.sqlite'); c = conn.cursor(); c.execute(\"SELECT COUNT(*) FROM (SELECT session_id, COUNT(*) as cnt FROM request_logs WHERE traffic_type IN ('normal', 'power') GROUP BY session_id HAVING cnt >= 10)\"); print('Legitimate sessions >= 10 reqs:', c.fetchone()[0]); conn.close()"
```
*(Expected output: ~160–165 sessions).*

---

### Step B: Generate Attack Traffic (Fast & Slow Evasive)
Run 4 complete rounds of all 4 fast attacks and all 3 slow attack variants:

```powershell
# 4 rounds of all 4 fast attacks (Credential Stuffing, Scraping, Enumeration, Privilege Probe)
for ($i=1; $i -le 4; $i++) {
    python traffic-simulator/simulator.py --mode attack --attack all --base-url http://127.0.0.1:5000
}

# 4 rounds of slow human-paced attacks (2-4s intervals)
for ($i=1; $i -le 4; $i++) {
    python traffic-simulator/profiles/attacks/slow_attacks.py
}
```

---

### Step C: Compute Timing Baseline Manifest & Fast Attack Sanity Check
Run the manifest computation script to calculate legitimate human inter-arrival percentiles and verify that automated bot attacks burst at sub-second rates:

```powershell
python compute_manifest.py
```

### Expected Output:
```json
{
  "total_gaps_analyzed": 3605,
  "median_gap": 3.4762,
  "mean_gap": 16.6245,
  "p1_gap": 0.7314,
  "p5_gap": 1.1331,
  "p25_gap": 2.0738,
  "p75_gap": 5.9975,
  "p95_gap": 10.12,
  "fast_attack_median_gap": 0.1657,
  "fast_attack_sanity_check": "PASSED (< 0.5s)"
}
```
> **Sanity Check Rule:** `fast_attack_sanity_check` must output `"PASSED (< 0.5s)"` with median gap around `0.15s` (confirming the Windows IPv6 localhost bug is eliminated).

Now **stop the Target API** in Terminal 1 by pressing `CTRL + C`.

---

## Phase 3: Feature Extraction & Sequence Building

With raw traffic logged in `database.sqlite`, extract statistical sliding window features and sequence tensors using fixed seed `42`:

```powershell
$env:PYTHONUTF8=1

# 1. Extract 11 behavioral features over trailing 60s windows
python ml-pipeline/features/feature_builder.py

# 2. Build 30-timestep sequence tensors for LSTM model
python ml-pipeline/features/sequence_builder.py
```

### What This Does:
1. Filters trailing 60s windows ending at requests with `MIN_WINDOW_REQUESTS = 10`.
2. Computes the 11 client-behavioral features: `request_count`, `unique_endpoints`, `endpoint_diversity_ratio`, `mean_inter_request_time`, `std_inter_request_time`, `min_inter_request_time`, `failed_auth_ratio`, `error_ratio`, `method_post_ratio`, `sequential_id_score`, `session_duration`.
3. Fits `StandardScaler` strictly on legitimate training sessions, enforcing variance floors:
   $$\sigma_{\text{time}} \ge 1.5\text{s}, \quad \sigma_{\text{count}} \ge 4.0, \quad \sigma_{\text{ratio}} \ge 0.35$$
4. Clips $z$-scores to $[-5.0, 5.0]$ to prevent out-of-sample score explosions.
5. Produces `train_features.npy` (~745 windows), `val_features.npy` (~203 windows), and `test_features.npy` (~2680 windows).

---

## Phase 4: Model Training

Train both neural network architectures:

```powershell
$env:PYTHONUTF8=1

# 1. Train Dense Autoencoder (Primary Live Model)
python ml-pipeline/training/train_dense_ae.py

# 2. Train LSTM Autoencoder (Sequential Benchmark)
python ml-pipeline/training/train_lstm_ae.py
```

### Threshold Calibration Rules:
* **Dense Autoencoder:** The threshold is calibrated strictly from legitimate validation errors:
  $$\tau_{\text{dense}} = 3.5 \times P_{99}(\text{val\_errors}) \approx 0.455855$$
  *(Includes session headroom multiplier to absorb multi-window variance; zero attack label leakage).*
* **LSTM Autoencoder:** Calibrated at plain 99th percentile:
  $$\tau_{\text{lstm}} = P_{99}(\text{val\_errors}) \approx 0.316657$$

---

## Phase 5: Offline Model Evaluation (Test Split)

Evaluate both trained models against held-out normal and attack test windows:

```powershell
$env:PYTHONUTF8=1

# Evaluate Dense Autoencoder
python ml-pipeline/training/evaluate.py --model dense_ae

# Evaluate LSTM Autoencoder
python ml-pipeline/training/evaluate.py --model lstm_ae --threshold-path ml-pipeline/saved_models/lstm_threshold.json
```

### Expected Output:
* **Dense Autoencoder:** Precision $\approx 1.0000$, Recall $\approx 0.9968$, F1-Score $\approx 0.9984$, AUC-ROC $= 1.0000$.
* Plots and result JSONs saved to `ml-pipeline/saved_models/evaluation/`.

---

## Phase 6: Live Out-of-Sample Verification Runs

Run the 3 automated out-of-sample live replay runs on fresh, independent SQLite databases:

```powershell
$env:PYTHONUTF8=1
python run_single_eval.py 1
python run_single_eval.py 2
python run_single_eval.py 3
```

Each run:
1. Creates a brand-new temporary SQLite database (`test_eval_N.sqlite`).
2. Starts the Target API and Scoring Engine in background processes.
3. Simulates 12 concurrent users for 200 seconds while unleashing all 4 fast attacks and 3 slow attacks.
4. Evaluates real-time sliding windows with the 3-consecutive-window persistence rule.
5. Saves raw terminal output to `evaluation_runs/run_N.txt`.
6. Confirms:
   * **Normal User False Alarms:** 0.0% (0 / 31, 0 / 25, 0 / 24).
   * **Power User False Alarms:** 0.0% (0 / 6, 0 / 8, 0 / 7).
   * **Fast Attack Detection:** 100.0% (4 / 4 in all runs).
   * **Slow Attack Detection:** 2 of 3 attack types caught in all runs (slow credential stuffing and slow enumeration detected; slow privilege probe missed due to 60s aggregation boundary).
   * **Timing Drift:** Median gap difference vs baseline $< 12\%$.
7. Deletes the temporary test database automatically.

---

## Phase 7: Running the Real-Time SOC Demo

Once trained, to run the complete live interactive demo:

1. **Terminal 1 (Target API):**
   ```powershell
   python target-api/app.py
   ```
2. **Terminal 2 (AI Scoring Engine):**
   ```powershell
   python scoring-engine/main.py
   ```
3. **Terminal 3 (React SOC Dashboard):**
   ```powershell
   cd dashboard
   npm run dev
   ```
   *Open `http://localhost:5173` in your browser.*

4. **Terminal 4 (Traffic Simulator):**
   ```powershell
   # Launch mixed background traffic + fast attacks
   python traffic-simulator/simulator.py --mode mixed --attack all --users 12 --duration 200 --base-url http://127.0.0.1:5000

   # Launch slow evasive attacks concurrently
   python traffic-simulator/profiles/attacks/slow_attacks.py
   ```
