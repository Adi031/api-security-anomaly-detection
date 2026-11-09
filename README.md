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
4. **Calibrated Threshold ($\tau = 0.419546$) with Zero Attack Leakage:** The threshold is calibrated strictly on legitimate validation data as $3.5\times$ the 99th percentile ($P_{99} = 0.119870$) of normal reconstruction errors ($\tau = 3.5 \times P_{99} = 0.419546$). No attack data is used in threshold selection.
5. **Window Gate & Persistence Rule:** To maintain a target False Positive Rate (FPR $\le 5\%$) and filter transient spikes, scoring requires a minimum of 10 requests in the trailing 60s window (`MIN_WINDOW_REQUESTS = 10`), and an alert is raised only when **3 consecutive evaluation windows** exceed threshold $\tau$.

We evaluate two architectures:
- **Dense Autoencoder (Primary & Default Live Detector):** Evaluates 11 statistical behavioral features over 60-second trailing windows. Designed for low-latency deployment (target model inference latency $< 15\text{ ms}$, measured $< 0.01\text{ ms}$ on CPU; pipeline detection $< 50\text{ ms}$). The threshold is calibrated at **$3.5\times P_{99}$** of validation (legitimate-only) errors ($\tau = 0.419546$) with session headroom. This model serves live traffic in the real-time scoring engine.
- **LSTM Autoencoder (Sequential Benchmark):** Evaluates sequences of 30 endpoint transitions and timing deltas (feature dimension 10, vocabulary size 10). The threshold uses a **plain $P_{99}$ with no headroom** ($\tau = 0.194286$). Note that the Dense model is the default, and the LSTM was evaluated on offline sequence splits and **not tested as the live detector** in the real-time scoring engine.

---

## ⚡ Localhost vs 127.0.0.1 DNS Timing Resolution
During testing on Windows environments, an artificial timing bottleneck was identified when clients targeted `http://localhost:5000`:
- **`http://localhost:5000`:** Median curl request duration = **0.2393s** (0.222s, 0.237s, 0.239s, 0.247s, 0.248s)
- **`http://127.0.0.1:5000`:** Median curl request duration = **0.0152s** (0.013s, 0.015s, 0.015s, 0.016s, 0.018s)

### Why BASE_URL was changed to `http://127.0.0.1:5000`
On Windows, HTTP clients resolving `localhost` first attempt IPv6 `::1` resolution before timing out and falling back to IPv4 `127.0.0.1`. The measured delay was **about 0.22 s with curl, about 2 s for the Python client on this machine** (due to socket/DNS resolution overhead accumulating across connection pooling). This inadvertently capped automated attack scripts in the simulator to $\approx 2.07\text{s}$ inter-request gaps, masking true bot burst velocities. Switching `BASE_URL` to explicit `http://127.0.0.1:5000` eliminated this DNS bottleneck completely (0.015s vs 0.239s in curl), allowing automated attacks to burst at realistic sub-second rates (median gap 0.177s) and ensuring training inter-arrival times match live client execution.

---

## 📊 Live Out-of-Sample Verification Results

Three independent out-of-sample live evaluation runs were conducted on brand-new, clean SQLite databases. Each run consisted of **12 concurrent legitimate users** running for **200 seconds**, alongside all **4 fast attacks** and all **3 slow evasive attacks** executing concurrently. Denominators strictly report sessions that reached the 10-request evaluation gate.

### Run 1 (`evaluation_runs/run_1.txt` — 1,349 requests, 47 sessions)
- Feature Drift: All 11 features $|z| \le 0.38$ (all `OK`)
- Pacing Diagnostic vs `data_manifest.json`: Median gap diff = **6.9%**, P1 diff = **0.0%**, P95 diff = **1.7%**

| Traffic Profile | Total Sessions | Reached Gate ($\ge 10$ reqs) | Sessions Flagged | Gate Rate | Total Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Credential Stuffing (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **BOLA / Enumeration (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Data Scraping (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Privilege Probe (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Credential Stuffing (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Enumeration (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Privilege Probe (Evasive)** | 1 | 1 | 0 | **0.0%** | 0.0% |
| **Normal Users** | 34 | 33 | 0 | **0.0%** | 0.0% |
| **Power Users** | 6 | 6 | 0 | **0.0%** | 0.0% |

---

### Run 2 (`evaluation_runs/run_2.txt` — 1,286 requests, 43 sessions)
- Feature Drift: All 11 features $|z| \le 0.45$ (all `OK`)
- Pacing Diagnostic vs `data_manifest.json`: Median gap diff = **6.9%**, P1 diff = **20.5%**, P95 diff = **3.3%**

| Traffic Profile | Total Sessions | Reached Gate ($\ge 10$ reqs) | Sessions Flagged | Gate Rate | Total Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Credential Stuffing (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **BOLA / Enumeration (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Data Scraping (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Privilege Probe (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Credential Stuffing (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Enumeration (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Privilege Probe (Evasive)** | 1 | 1 | 0 | **0.0%** | 0.0% |
| **Normal Users** | 31 | 30 | 0 | **0.0%** | 0.0% |
| **Power Users** | 5 | 5 | 0 | **0.0%** | 0.0% |

---

### Run 3 (`evaluation_runs/run_3.txt` — 1,189 requests, 35 sessions)
- Feature Drift: All 11 features $|z| \le 0.34$ (all `OK`)
- Pacing Diagnostic vs `data_manifest.json`: Median gap diff = **3.1%**, P1 diff = **21.6%**, P95 diff = **6.4%**

| Traffic Profile | Total Sessions | Reached Gate ($\ge 10$ reqs) | Sessions Flagged | Gate Rate | Total Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Credential Stuffing (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **BOLA / Enumeration (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Data Scraping (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Privilege Probe (Fast)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Credential Stuffing (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Enumeration (Evasive)** | 1 | 1 | 1 | **100.0%** | 100.0% |
| **Slow Privilege Probe (Evasive)** | 1 | 1 | 0 | **0.0%** | 0.0% |
| **Normal Users** | 22 | 21 | 0 | **0.0%** | 0.0% |
| **Power Users** | 6 | 6 | 0 | **0.0%** | 0.0% |

---

### Summary of Live Out-of-Sample Performance
- **Legitimate Normal Users False Alarm Rate:** **0 / 84 (0.0%)** of gate-reaching sessions across all runs.
- **Power Users False Alarm Rate:** **0 / 17 (0.0%)** of gate-reaching sessions across all runs.
- **Combined Legitimate False Alarm Rate:** **0 / 101 (0.0%)** (target FPR: $\le 5.0\%$).
- **Fast Attack Detection Rate:** **12 / 12 (100.0%)** (4/4 on each run).
- **Slow Attack Detection Rate:** **2 of 3 slow attack types detected** (6 / 9 sessions flagged; caught slow credential stuffing and slow enumeration in all runs, but missed slow privilege probe: 0 / 3 caught across runs).
- **Overall Attack Detection Rate:** **6 of 7 attack types detected** (18 / 21 session-level alerts across all runs).

---

## 📈 Baseline Models Benchmark & Comparison

To validate the deep learning architecture against industry and classical alternatives, we benchmarked the **Dense Autoencoder (Sentinel-v2)** against three baseline methods on the exact same held-out test dataset (**9,414 evaluation sessions**: 758 legitimate, 8,656 attacks). All unsupervised models were trained strictly on legitimate normal sessions.

| Model | Model Type | Precision | Recall | F1-Score | False Positive Rate (FPR) | ROC-AUC | Latency (CPU) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Static Rate Limiter** | Heuristic Rules | 97.71% | 97.12% | 97.42% | 25.99% | 0.9849 | < 0.01 ms |
| **Isolation Forest** | Tree-based ML | 99.61% | 99.33% | 99.47% | 4.49% | 0.9984 | < 0.01 ms |
| **One-Class SVM** | Kernel ML | 99.57% | 99.53% | 99.55% | 4.88% | 0.9985 | 0.01 ms |
| **Dense Autoencoder (Ours)** | **Deep Learning** | **100.00%** | **96.53%** | **98.24%** | **0.00%** | **0.9994** | **< 0.01 ms** |

*Benchmark Data Reference:* [`ml-pipeline/saved_models/evaluation/baseline_comparison.json`](ml-pipeline/saved_models/evaluation/baseline_comparison.json)

*Key Findings:*
1. **Rate Limiting Deficiencies:** The heuristic baseline suffers from an unacceptable **25.99% False Positive Rate**, as natural browsing bursts exceed static thresholds.
2. **False Positive Control:** While Isolation Forest (4.49% FPR) and One-Class SVM (4.88% FPR) meet the target requirement ($\le 5\%$ FPR), the Dense Autoencoder achieved the highest separability (**ROC-AUC: 0.9994**) with **0.00% False Positive Rate** on the held-out normal split at operating threshold $\tau = 0.419546$.
3. **Latency Compliance:** All algorithms execute in **$< 0.01\text{ ms}$** per session on CPU, comfortably satisfying the $< 15\text{ ms}$ real-time inference requirement.

---

## ⚠️ Limitations & Boundary Conditions
1. **Simulated Traffic Environment:** All training and evaluation traffic was generated through scripted client simulation profiles rather than real production web user sessions. While profiles incorporate realistic human pacing jitter ($0.5\times - 1.8\times$) and random thinking delays, production real-world traffic will contain higher variance in user-agent headers, network jitter, and session lengths.
2. **10-Request Window Gate:** The trailing 60s sliding window enforces `MIN_WINDOW_REQUESTS = 10`. Sessions ending before reaching 10 requests (e.g., a visitor who browses 3 products and departs) are never evaluated by the anomaly detector.
3. **Small Attack Sample Size per Live Run:** In each live run, 1 session of each attack profile is unleashed against 12 concurrent users to model an opportunistic intrusion in ongoing traffic. While this tests real-time alerting sensitivity, statistical variance in attack detection is best evaluated alongside the offline test set (2,568 attack windows).
4. **Environment-Dependent Timing Features:** Inter-arrival time features (`mean_inter_request_time`, `min_inter_request_time`, `std_inter_request_time`) are influenced by the host machine's CPU speed, operating system scheduler, and network stack. If deploying this codebase to a different server or operating system, traffic generation and feature extraction must be re-run to recalibrate the baseline distribution.
5. **LSTM Detector Scope & Steady-State Scraping:** The LSTM autoencoder evaluates sequential endpoint transition paths. In steady-state scraping where an attacker continuously requests `/api/products/<ID>` in a loop, sequential transition novelty is low. Furthermore, the LSTM threshold rule is a plain $P_{99}$ with no headroom ($\tau = 0.194286$), unlike the Dense model's $3.5\times P_{99}$ headroom calibration ($\tau = 0.419546$). The Dense Autoencoder is designated as the primary default detector; the LSTM was evaluated offline on sequence splits and was not tested as the live detector in the live scoring engine.
6. **Slow Privilege Probe Detection Limit:** In `slow_privilege_probe`, an attacker makes only 4 unauthorized requests across a 26-request session with 3–6s delays (0 of 3 caught across runs). Because requests are widely spaced, a 60-second window contains only 1 error out of 12 requests ($<8\%$ error ratio), which does not persist across 3 consecutive sliding windows. Detecting such ultra-low-frequency attacks requires longer temporal aggregation windows (> 5 minutes).
7. **Threshold Calibration Strategy:** The decision threshold is mathematically fixed at $\tau = 3.5 \times P_{99}(\text{val\_errors}) = 0.419546$ on legitimate-only validation data. While this guarantees zero attack label leakage and absorbs session-level sliding-window variance, it is tuned for high precision to protect legitimate users.
8. **Session-Rotating & Distributed Evasion:** The current system is explicitly architected as a session-behavioral detector. Attacks that rotate IP addresses and discard session identifiers on every single HTTP request deliberately avoid session accumulation. Mitigating such attacks requires multi-session cross-account and IP-subnet rolling aggregation, which is documented as planned future work.

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

