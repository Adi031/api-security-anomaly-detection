# Behavioral Anomaly Detection for API Security

**A B.Tech CSE 7th Semester Major Project**

## What is this project?
This project is an intelligent behavioral security system designed to protect Web Application Programming Interfaces (APIs). Instead of relying on rigid, hardcoded rules (such as IP blocklists or static rate limits), it utilizes **Semi-Supervised Deep Learning (Autoencoders)** to learn the statistical and sequential dynamics of legitimate user behavior. When an attacker conducts automated, high-velocity, or stealthy human-paced attacks, their behavioral pattern deviates from normal and power-user baselines, enabling the system to detect and flag intrusions in real time.

## What does it do?
It monitors live HTTP traffic on a realistic E-Commerce API (covering user authentication, catalog browsing, cart operations, and order placement). The scoring engine evaluates client traffic over trailing 60-second sliding windows. If a client exhibits anomalous behavioral patterns across multiple consecutive evaluation windows, the system flags the session and raises high-priority alerts on the Security Operations Center (SOC) dashboard.

## Which attacks does it detect?
The system evaluates seven attack profiles across key OWASP API Security Top 10 categories, spanning 4 high-speed automated bots and 3 stealthy human-paced evasive variants (detecting **6 of 7 attack types overall**, including **2 of 3 slow attack types**):
1. **Credential Stuffing (Fast Bot):** High-velocity automated password guessing against `/api/auth/login`.
2. **Slow Credential Stuffing (Evasive):** Low-frequency brute-force attempts spaced at 2–4s human intervals.
3. **Data Scraping (Fast Bot):** High-frequency automated harvesting of the entire product catalog.
4. **BOLA / Enumeration (Fast Bot):** Systematic sequential probing of `/api/orders/:id` and `/api/users/:id`.
5. **Slow Enumeration (Evasive):** Shuffled order/user probes intermixed with legitimate product browsing at 2–4s intervals.
6. **Privilege Probing (Fast Bot):** Probing unauthorized administrative endpoints (e.g., `/api/users/:id/profile`).
7. **Slow Privilege Probing (Evasive):** Occasional administrative probes concealed inside browsing sessions (documented aggregation limitation: 0 of 4 caught).

## How does it do it? (The Machine Learning Architecture)
The pipeline employs an **Autoencoder** neural network trained exclusively on legitimate human and power-user sessions (semi-supervised anomaly detection):
1. **Feature Extraction:** Over trailing 60-second windows ending at every request, traffic is summarized into **11 behavioral features** capturing request velocity, inter-arrival timing dynamics, endpoint diversity, HTTP POST ratios, sequential ID probing, and error/authentication failure proportions.
2. **Reconstruction Loss:** The autoencoder compresses the 11-dimensional feature vector into a lower-dimensional latent representation (dim=6) and attempts to reconstruct it.
3. **Anomaly Scoring:** Legitimate sessions reconstruct with low Mean Squared Error (MSE), whereas attack behaviors produce high reconstruction errors.
4. **Calibrated Threshold ($\tau = 0.455855$) with Zero Attack Leakage:** The threshold is calibrated strictly on validation data as $3.5\times$ the 99th percentile ($P_{99} = 0.130244$) of legitimate reconstruction errors. No attack data is used anywhere in threshold selection.
5. **Window Gate & Persistence Rule:** To eliminate false positives from short sessions and transient spikes, scoring requires a minimum of 10 requests in the trailing 60s window (`MIN_WINDOW_REQUESTS = 10`), and an alert is raised only when **3 consecutive evaluation windows** exceed threshold $\tau$.

We evaluate two architectures:
- **Dense Autoencoder (Primary & Default Live Detector):** Evaluates 11 statistical behavioral features over 60-second trailing windows. Latency < 2ms. The threshold is calibrated at **$3.5\times P_{99}$** of validation (legitimate-only) errors ($\tau = 0.455855$) with session headroom. This model serves live traffic in the real-time scoring engine.
- **LSTM Autoencoder (Sequential Benchmark):** Evaluates sequences of 30 endpoint transitions and timing deltas (feature dimension 10, vocabulary size 10). The threshold uses a **plain $P_{99}$ with no headroom** ($\tau = 0.316657$). Note that the Dense model is the default, and the LSTM was evaluated on offline sequence splits and **not tested as the live detector** in the real-time scoring engine.

---

## ⚡ Localhost vs 127.0.0.1 DNS Timing Resolution
During testing on Windows environments, an artificial timing bottleneck was identified when clients targeted `http://localhost:5000`:
- **`http://localhost:5000`:** Median curl request duration = **0.2393s** (0.222s, 0.237s, 0.239s, 0.247s, 0.248s)
- **`http://127.0.0.1:5000`:** Median curl request duration = **0.0152s** (0.013s, 0.015s, 0.015s, 0.016s, 0.018s)

### Why BASE_URL was changed to `http://127.0.0.1:5000`
On Windows, HTTP clients resolving `localhost` first attempt IPv6 `::1` resolution before timing out and falling back to IPv4 `127.0.0.1`. The measured delay was **about 0.22 s with curl, about 2 s for the Python client on this machine** (due to socket/DNS resolution overhead accumulating across connection pooling). This inadvertently capped automated attack scripts in the simulator to $\approx 2.07\text{s}$ inter-request gaps, masking true bot burst velocities. Switching `BASE_URL` to explicit `http://127.0.0.1:5000` eliminated this DNS bottleneck completely (0.015s vs 0.239s in curl), allowing automated attacks to burst at realistic sub-second rates (median gap 0.157s) and ensuring training inter-arrival times match live client execution.

---

## 📊 Live Out-of-Sample Verification Results

Three independent out-of-sample live evaluation runs were conducted on brand-new, clean SQLite databases. Each run consisted of **12 concurrent legitimate users** running for **200 seconds**, alongside all **4 fast attacks** and all **3 slow evasive attacks** executing concurrently. Denominators strictly report sessions that reached the 10-request evaluation gate.

### Run 1 (`evaluation_runs/run_1.txt` — 1,332 requests, 45 sessions)
- Feature Drift: All 11 features $|z| \le 0.41$ (all `OK`)
- Pacing Diagnostic vs `data_manifest.json`: Median gap diff = **0.3%**, P1 diff = **11.8%**, P95 diff = **5.4%**

| Traffic Profile | Total Sessions | Reached Gate ($\ge 10$ reqs) | Sessions Flagged | Gate Rate | Total Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Credential Stuffing (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **BOLA / Enumeration (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Data Scraping (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Privilege Probe (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Credential Stuffing (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Enumeration (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Privilege Probe (Evasive)** | 1 | 1 | 0 | **0.0%** | 0.0% |
| **Normal Users** | 32 | 31 | 0 | **0.0%** | 0.0% |
| **Power Users** | 6 | 6 | 0 | **0.0%** | 0.0% |

---

### Run 2 (`evaluation_runs/run_2.txt` — 1,289 requests, 42 sessions)
- Feature Drift: All 11 features $|z| \le 0.68$ (all `OK`)
- Pacing Diagnostic vs `data_manifest.json`: Median gap diff = **9.4%**, P1 diff = **9.3%**, P95 diff = **6.1%**

| Traffic Profile | Total Sessions | Reached Gate ($\ge 10$ reqs) | Sessions Flagged | Gate Rate | Total Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Credential Stuffing (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **BOLA / Enumeration (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Data Scraping (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Privilege Probe (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Credential Stuffing (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Enumeration (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Privilege Probe (Evasive)** | 1 | 1 | 0 | **0.0%** | 0.0% |
| **Normal Users** | 27 | 25 | 0 | **0.0%** | 0.0% |
| **Power Users** | 8 | 8 | 0 | **0.0%** | 0.0% |

---

### Run 3 (`evaluation_runs/run_3.txt` — 1,246 requests, 39 sessions)
- Feature Drift: All 11 features $|z| \le 0.69$ (all `OK`)
- Pacing Diagnostic vs `data_manifest.json`: Median gap diff = **11.4%**, P1 diff = **18.0%**, P95 diff = **1.0%**

| Traffic Profile | Total Sessions | Reached Gate ($\ge 10$ reqs) | Sessions Flagged | Gate Rate | Total Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Credential Stuffing (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **BOLA / Enumeration (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Data Scraping (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Privilege Probe (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Credential Stuffing (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Enumeration (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Privilege Probe (Evasive)** | 1 | 1 | 0 | **0.0%** | 0.0% |
| **Normal Users** | 25 | 24 | 0 | **0.0%** | 0.0% |
| **Power Users** | 7 | 7 | 0 | **0.0%** | 0.0% |

---

### Summary of Live Out-of-Sample Performance
- **Legitimate Normal Users False Alarm Rate:** **0 / 80 (0.0%)** of gate-reaching sessions across all runs.
- **Power Users False Alarm Rate:** **0 / 21 (0.0%)** of gate-reaching sessions across all runs.
- **Combined Legitimate False Alarm Rate:** **0 / 101 (0.0%)**.
- **Fast Attack Detection Rate:** **12 / 12 (100.0%)** (4/4 on each run).
- **Slow Attack Detection Rate:** **2 of 3 slow attack types detected** (6 / 9 sessions flagged; caught slow credential stuffing and slow enumeration in all runs, but missed slow privilege probe: 0 / 4 caught across runs).
- **Overall Attack Detection Rate:** **6 of 7 attack types detected** (18 / 21 session-level alerts across all runs).

---

## ⚠️ Limitations & Boundary Conditions
1. **Simulated Traffic Environment:** All training and evaluation traffic was generated through scripted client simulation profiles rather than real production web user sessions. While profiles incorporate realistic human pacing jitter ($0.5\times - 1.8\times$) and random thinking delays, production real-world traffic will contain higher variance in user-agent headers, network jitter, and session lengths.
2. **10-Request Window Gate:** The trailing 60s sliding window enforces `MIN_WINDOW_REQUESTS = 10`. Sessions ending before reaching 10 requests (e.g., a visitor who browses 3 products and departs) are never evaluated by the anomaly detector.
3. **Small Attack Sample Size per Live Run:** In each live run, 1 session of each attack profile is unleashed against 12 concurrent users to model an opportunistic intrusion in ongoing traffic. While this tests real-time alerting sensitivity, statistical variance in attack detection is best evaluated alongside the offline test set (2,483 attack windows).
4. **Environment-Dependent Timing Features:** Inter-arrival time features (`mean_inter_request_time`, `min_inter_request_time`, `std_inter_request_time`) are influenced by the host machine's CPU speed, operating system scheduler, and network stack. If deploying this codebase to a different server or operating system, traffic generation and feature extraction must be re-run to recalibrate the baseline distribution.
5. **LSTM Detector Scope & Steady-State Scraping:** The LSTM autoencoder evaluates sequential endpoint transition paths. In steady-state scraping where an attacker continuously requests `/api/products/<ID>` in a loop, sequential transition novelty is low. Furthermore, the LSTM threshold rule is a plain $P_{99}$ with no headroom ($\tau = 0.316657$), unlike the Dense model's $3.5\times P_{99}$ headroom calibration ($\tau = 0.455855$). The Dense Autoencoder is designated as the primary default detector; the LSTM was evaluated offline on sequence splits and was not tested as the live detector in the live scoring engine.
6. **Slow Privilege Probe Detection Limit:** In `slow_privilege_probe`, an attacker makes only 4 unauthorized requests across a 26-request session with 3–6s delays (0 of 4 caught across runs). Because requests are widely spaced, a 60-second window contains only 1 error out of 12 requests ($<8\%$ error ratio), which does not persist across 3 consecutive sliding windows. Detecting such ultra-low-frequency attacks requires longer temporal aggregation windows (> 5 minutes).
7. **Threshold Calibration Strategy:** The decision threshold is mathematically fixed at $\tau = 3.5 \times P_{99}(\text{val\_errors})$ on legitimate-only validation data. While this guarantees zero attack label leakage and absorbs session-level sliding-window variance, it is tuned for high precision to protect legitimate users.

---

## 🚀 How to Run the Project Live

Open **4 separate PowerShell terminal windows** at the root of the project directory (`d:\Project-7th-Sem`).

### One-Time Setup:
```powershell
python init_sqlite.py
python target-api/seed_db.py
```

### Terminal 1: Start Mock E-Commerce API
```powershell
python target-api/app.py
```

### Terminal 2: Start Anomaly Scoring Engine
```powershell
python scoring-engine/main.py
```

### Terminal 3: Start SOC Dashboard
```powershell
cd dashboard
npm run dev
```
*(Open `http://localhost:5173` in your browser to view real-time traffic and alerts).*

### Terminal 4: Launch Traffic Simulator
To launch standard mixed traffic with 12 users and all 4 fast attacks:
```powershell
python traffic-simulator/simulator.py --mode mixed --attack all --users 12 --duration 200 --base-url http://127.0.0.1:5000
```
To run the slow human-paced attacks concurrently:
```powershell
python traffic-simulator/profiles/attacks/slow_attacks.py
```

---

## 🔬 How to Reproduce Training and Evaluation

### 1. Feature Extraction & Model Training
```powershell
$env:PYTHONUTF8=1
python ml-pipeline/features/feature_builder.py
python ml-pipeline/features/sequence_builder.py
python ml-pipeline/training/train_dense_ae.py
python ml-pipeline/training/train_lstm_ae.py
```

### 2. Model Evaluation on Test Split
```powershell
$env:PYTHONUTF8=1
python ml-pipeline/training/evaluate.py --model dense_ae
python ml-pipeline/training/evaluate.py --model lstm_ae --threshold-path ml-pipeline/saved_models/lstm_threshold.json
```

### 3. Out-of-Sample Live Replay Evaluation
```powershell
$env:PYTHONUTF8=1
python run_single_eval.py 1
python run_single_eval.py 2
python run_single_eval.py 3
```

---

## 📜 Academic Integrity & AI Assistance
In accordance with academic and institutional project guidelines, AI assistance (Google DeepMind Antigravity and Anthropic Claude) was utilized for exploratory pair programming, debugging the Windows IPv6 localhost DNS socket delay, refactoring trailing-window feature extraction, and developing test automation harnesses (`run_single_eval.py`). All core architectural choices, feature definitions, model training, evaluation executions, and reported experimental numbers were performed, verified, and validated on local hardware.
