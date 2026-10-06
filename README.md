# Behavioral Anomaly Detection for API Security

An unsupervised anomaly detection system that learns normal API usage patterns and flags deviations in real time — without hardcoded rules or labeled attack data for training.

## Architecture

```
[Sample Web App w/ REST API] → generates real request logs
        ↓
[Log Collector] → timestamp, user_id, endpoint, method, status_code, response_time, IP, user-agent
        ↓
[Feature/Sequence Builder] → converts raw logs into model input
        ↓
[Anomaly Detection Model] → autoencoder / LSTM-autoencoder → anomaly score
        ↓
[Scoring + Alerting Engine] → threshold-based flagging, severity levels
        ↓
[Live Dashboard] → real-time request timeline, anomaly score graph, flagged users/IPs, alert feed
```

## Tech Stack

| Component | Technology |
|---|---|
| Target API | Flask (Python) |
| ML Models | PyTorch |
| Database | SQLite |
| Scoring Engine | FastAPI |
| Dashboard | React (Vite) |
| Traffic Simulator | Python |

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Initialize DB & Start Target API
Open **Terminal 1**:
```bash
cd target-api
pip install -r requirements.txt
python ../init_sqlite.py
python seed_db.py
python app.py
```

### 2. Generate Training Data
Open **Terminal 2**:
```bash
cd traffic-simulator
pip install -r requirements.txt
python simulator.py --mode normal --users 30 --duration 600
```

### 3. Train Model
Keep **Terminal 2** open:
```bash
cd ../ml-pipeline
pip install -r requirements.txt
python features/feature_builder.py
python training/train_dense_ae.py
```

### 4. Start Scoring Engine
Open **Terminal 3**:
```bash
cd scoring-engine
pip install -r requirements.txt
python -m uvicorn main:app --port 8001
```

### 5. Start Dashboard
Open **Terminal 4**:
```bash
cd dashboard
npm install
npm run dev
```

### 6. Run Attack Simulation (Demo)
In **Terminal 2** (or any available terminal):
```bash
cd ../traffic-simulator
python simulator.py --mode mixed --attack all --users 10
```

## Project Structure

```
├── target-api/           # Flask sample web app (traffic source)
├── traffic-simulator/    # Normal + attack traffic generation
├── ml-pipeline/          # Feature engineering + model training
├── scoring-engine/       # Real-time scoring backend (FastAPI)
├── dashboard/            # React frontend (Vite)
└── validation/           # Public dataset validation (CSIC 2010, CICIDS2017)
```

## Attack Types Detected
- Credential stuffing (rapid /login attempts)
- Web scraping (systematic endpoint traversal)
- Enumeration attacks (incrementing resource IDs)
- Anomalous privilege/endpoint access

## Models
1. **Dense Autoencoder** (baseline) — per-window feature vectors
2. **LSTM Autoencoder** (stretch) — API call sequences per session
