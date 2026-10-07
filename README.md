# Behavioral Anomaly Detection for API Security

An advanced unsupervised anomaly detection system that learns normal API usage patterns and flags deviations in real time using Recurrent Neural Networks (LSTMs). It detects complex, sequence-based cyber attacks without hardcoded rules or labeled training data.

This project was built for a B.Tech CSE 7th Semester Major Project.

## Architecture

```
[Target Web API] → generates real-world user traffic logs
       ↓
[Log Collector (SQLite)] → timestamp, session_id, endpoint, method, status_code, IP
       ↓
[Feature Sequence Builder] → converts chronological logs into padded token sequences
       ↓
[LSTM Autoencoder] → predicts the next sequence, outputs Mean Squared Error (MSE)
       ↓
[FastAPI Scoring Engine] → threshold-based severity (CLEAN, FLAGGED, BLOCKED)
       ↓
[React Dashboard] → real-time timeline, anomaly score charts, live active sessions
```

## Tech Stack

| Component | Technology |
|---|---|
| **Target API** | Flask (Python) |
| **ML Models** | PyTorch (LSTM Autoencoder) |
| **Database** | SQLite, Pandas |
| **Scoring Engine** | FastAPI, WebSockets |
| **Dashboard** | React, Vite, Recharts |
| **Traffic Simulator** | Python (Requests) |

## Quick Start Guide

You will need to open **4 separate terminal windows** to run the complete microservices architecture.

### Prerequisites
- Python 3.10+
- Node.js 18+
- Windows PowerShell / Linux Bash

### 1. Initialize DB & Start Target API
Open **Terminal 1**:
```powershell
cd target-api
pip install -r requirements.txt
python ../init_sqlite.py
python seed_db.py
python app.py
```
*(Leave this running. It hosts the mock e-commerce API on port 5000).*

### 2. Start the React Dashboard
Open **Terminal 2**:
```powershell
cd dashboard
npm install
npm run dev
```
*(Leave this running. It hosts the UI on port 5173).*

### 3. Start the Scoring Engine (LSTM Mode)
Open **Terminal 3**:
```powershell
cd scoring-engine
pip install -r requirements.txt
$env:MODEL_TYPE="lstm"
python -m uvicorn main:app --port 8001
```
*(Leave this running. It analyzes the database in real-time and broadcasts alerts).*

### 4. Run the Traffic Simulator
Open **Terminal 4**:
```powershell
cd traffic-simulator
pip install -r requirements.txt
python simulator.py --users 30 --duration 600
```
This generates normal human browsing behavior. You will see the Active Sessions table in the dashboard populate with `CLEAN` connections.

---


---

## How to Retrain the Model (Optional)

If you have cleared the database or modified the simulator and need to retrain the LSTM model from scratch, follow these steps before starting the Scoring Engine:

**1. Generate Normal Training Traffic:**
`powershell
cd traffic-simulator
python simulator.py --users 30 --duration 600
`
*(Wait for this to complete and fill the database with baseline normal traffic).*

**2. Extract Features & Train:**
`powershell
cd ml-pipeline
python features/feature_builder.py
python training/train_lstm_ae.py
`
This will rebuild the sequential vocabulary, train the PyTorch LSTM Autoencoder, automatically calculate the new anomaly threshold, and save the updated weights to ml-pipeline/saved_models/.

## Simulating Cyber Attacks

To see the LSTM Autoencoder detect sequence anomalies, open a **5th Terminal** and launch any of the specialized attack scripts:

**1. Credential Stuffing / Brute Force** (Rapid repetitive `/login` attempts):
```powershell
cd traffic-simulator
python -m profiles.attacks.brute_force
```

**2. BOLA / IDOR Enumeration** (Systematically guessing `user_id` or `order_id` endpoints):
```powershell
cd traffic-simulator
python -m profiles.attacks.bola
```

**3. Web Scraping** (Aggressive traversal of all `/products` without natural dwell time):
```powershell
cd traffic-simulator
python -m profiles.attacks.scraping
```

**4. Data Exfiltration** (Downloading massive amounts of data):
```powershell
cd traffic-simulator
python -m profiles.attacks.data_exfiltration
```

You will instantly see the Dashboard graph spike above the critical threshold, triggering `WARNING` and `BLOCKED` badges in real-time.

---

## Model Details

### Why LSTM instead of Dense?
A baseline Dense Autoencoder only looks at a single API request in isolation (e.g., viewing a product). 
An **LSTM Autoencoder** processes the entire chronological sequence of a user's session (e.g., `login → view_cart → checkout`). This allows the system to detect attacks where the individual requests look perfectly normal, but the *order* or *speed* of the requests is completely abnormal (like bypassing a login screen).

### Threshold Tuning
The system automatically calculates the anomaly threshold by evaluating the 99th percentile of reconstruction errors on the validation dataset. The React UI dynamically reads this threshold to draw the graph limits and assign status badges (CLEAN vs FLAGGED vs BLOCKED).
