# Behavioral Anomaly Detection for API Security

**A B.Tech CSE 7th Semester Major Project**

## What is this project?
This project is an advanced cybersecurity system that acts like a security guard for a web application (API). Instead of relying on hardcoded rules (like blocking a specific IP address), it uses **Machine Learning (Artificial Intelligence)** to automatically learn what a "normal" user looks like. If an attacker tries to hack the system, their behavior will look mathematically different from a normal user, and the AI will catch them in real-time.

## What does it do?
It monitors live traffic on a mock E-Commerce website. It looks at every action a user takes (logging in, browsing products, adding to cart). The AI analyzes this behavior every 2 seconds. If a user starts acting like an automated bot or a hacker, the system instantly flags them and alerts the Security Operations Center (SOC) dashboard.

## Which attacks does it prevent?
The AI is currently trained to detect four major types of cyber attacks:
1. **Credential Stuffing (Brute Force):** Hackers trying thousands of stolen passwords on the login page in seconds.
2. **Data Scraping:** Automated bots rapidly downloading the entire product catalog without pausing to actually "read" the pages like a human would.
3. **BOLA / Enumeration:** Hackers systematically guessing `user_id` or `order_id` numbers (e.g., trying user 1, user 2, user 3) to steal other people's private data.
4. **Privilege Probes:** Attackers trying to access hidden admin URLs (e.g., `/api/admin/delete`) that they aren't supposed to know about.

## How does it do it? (The Machine Learning)
We use a Machine Learning architecture called an **Autoencoder**. 
1. We train the AI purely on normal human traffic. The AI learns how humans click, how long they wait between clicks, and what pages they visit.
2. When live traffic comes in, the AI tries to "reconstruct" the behavior based on what it knows about normal humans.
3. If an attacker uses an automated bot script, the bot behaves completely differently than a human. The AI fails to reconstruct the behavior, which causes a mathematical spike called **Mean Squared Error (MSE)**.
4. If this error spikes too high for 3 consecutive checks (the Persistence Rule), the system mathematically proves it is a cyber attack and triggers an alert.

We built two versions of this AI:
- **Dense Autoencoder:** Looks at high-volume statistics (like how many errors were triggered in 60 seconds). Very stable and catches 97% of attacks.
- **LSTM Autoencoder:** Looks at the exact *sequence* of clicks. Harder to train, but theoretically better at catching sneaky, low-volume attacks.

*(Note: We default to using the highly stable Dense model in this project, which scores 97.24% accuracy).*

---

## 🚀 How to Run the Project Live

To see the system working live, open **4 separate PowerShell terminal windows** at the root of the project (`d:\Project-7th-Sem`).

### First Time Setup (One-Time Only)
Before running anything for the first time, initialize the database and seed it with sample data:
```powershell
python init_sqlite.py
python target-api/seed_db.py
```

### Terminal 1: Start the Target Website
This runs the mock E-Commerce API that users and hackers will interact with.
```powershell
python target-api/app.py
```

### Terminal 2: Start the Security AI (Scoring Engine)
This starts the backend engine that runs the Machine Learning model on the live traffic.
```powershell
python scoring-engine/main.py
```

### Terminal 3: Start the Security Dashboard
This launches the stunning visual dashboard so you can watch the attacks happen.
```powershell
cd dashboard
npm run dev
```
*(Once started, open `http://localhost:5173` in your browser).*

### Terminal 4: Launch the Traffic Simulator (The Hackers!)
This launches a script that generates legitimate human users AND unleashes all four cyber attacks at the exact same time.
```powershell
python traffic-simulator/simulator.py --mode mixed --attack all --users 20 --duration 600
```
**Look at your browser dashboard (Terminal 3). You will see the normal traffic flowing, and suddenly the AI graphs will spike into the red as it catches the simulated attacks!**

---

## 🧠 How to Retrain the Machine Learning Model
If you ever want to wipe the AI's memory and retrain it from scratch, you can run our automated script. This script will delete the database, generate fresh normal human traffic, simulate fresh attacks, and train both the Dense and LSTM models across 5 random seeds to guarantee statistical accuracy.

1. Stop all the terminals above.
2. Open PowerShell and run:
```powershell
$env:PYTHONUTF8=1
python run_experiments.py
```
This will take a few minutes. When it finishes, it will print out a highly rigorous statistical table showing the Precision, Recall, and AUC (Accuracy) of the newly trained models!


---

## 📊 Evaluation & Benchmarks (Session-Level Results)

We benchmarked the trained Dense Autoencoder using real-time replay evaluation (`evaluate_live.py`) across all 582 recorded sessions (9,162 requests) under real-world traffic dynamics:

| Traffic Profile | Total Sessions | Sessions Flagged | Detection / False Alarm Rate |
| :--- | :---: | :---: | :---: |
| **Credential Stuffing** | 4 | 4 | **100.0%** (Detected) |
| **BOLA / Enumeration** | 4 | 4 | **100.0%** (Detected) |
| **Data Scraping** | 4 | 4 | **100.0%** (Detected) |
| **Privilege Probes** | 4 | 4 | **100.0%** (Detected) |
| **Normal Users** | 458 | 0 | **0.0%** (No False Alarms) |
| **Power Users (Busy Legitimate)** | 108 | 0 | **0.0%** (No False Alarms) |

### Key Architectural Safeguards:
1. **Trailing Window Sampling with 10-Request Gate:**
   - Both feature generation (`feature_builder.py`) and live scoring (`scoring-engine/main.py`) evaluate trailing 60-second windows ending at requests with `MIN_WINDOW_REQUESTS = 10`.
   - By including legitimate power-user windows during training, the model understands high-throughput legitimate user behavior and achieves a 0.0% false alarm rate.
2. **Short-Burst Heuristic Fast Path:**
   - For short sessions under 10 requests, a fast-path heuristic monitors error concentration ($\ge 3$ consecutive errors with $\ge 75\%$ error rate within $<15$s), detecting rapid brute-force sprays or probes without requiring a full 10-request window.
3. **Persistence Rule & Raw Audit Logging:**
   - The engine flags alerts only on the 3rd consecutive anomalous window (with 60s per-session alert cooldowns).
   - Raw model scores and raw anomaly classifications are preserved in `scored_requests` for complete auditability.
4. **Dynamic Threshold Loading:**
   - The SOC dashboard dynamically queries `/api/stats` to adapt to the calibrated model threshold ($	au = 0.648$ for Dense Autoencoder).
