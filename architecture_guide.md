# Architecture & Implementation Guide: Behavioral API Anomaly Detection

This document breaks down how your entire 7th-Semester Major Project works, from the high-level concept down to the code-level implementation. You can use this as a reference for your project report or presentation.

---

## 1. The Core Concept: Unsupervised Learning
Traditional security systems (like Web Application Firewalls) use **rule-based** detection. They look for specific keywords (like `SELECT * FROM`) or known malicious IP addresses. The problem? Attackers constantly change their tools to evade these rules.

Your project uses **Unsupervised Machine Learning (Autoencoders)**. 
Instead of teaching the AI what an attack looks like (which is impossible to do perfectly), you trained the AI *only* on normal, healthy user traffic. The AI learns the exact shape, timing, and behavior of a normal user. During real-time monitoring, if a sequence of API requests looks fundamentally different from what it learned, it throws a high **Reconstruction Error**. We use this error as the **Anomaly Score**.

---

## 2. System Architecture

The project is divided into 5 completely decoupled microservices.

### A. The Target API (`target-api/`)
* **Tech Stack**: Python, Flask, SQLite
* **Purpose**: This acts as the "dummy" application we are protecting. It simulates a standard e-commerce backend with routes for `/login`, `/products`, and `/orders`.
* **How it works**: Every time a request hits this API, a piece of **Middleware** (`middleware.py`) intercepts it before the route executes. It records the IP address, User-Agent, endpoint, and response time, and silently logs this data into the `request_logs` table in our SQLite database.

### B. The Traffic Simulator (`traffic-simulator/`)
* **Tech Stack**: Python, Threading
* **Purpose**: Machine learning models need data. This component generates thousands of synthetic API requests to build our dataset.
* **How it works**: 
  - **Normal Mode**: It simulates human-like behavior. Users log in, browse products, add items to a cart, wait a few seconds (think time), and log out.
  - **Attack Mode**: It spawns aggressive threads simulating Credential Stuffing (brute-forcing logins), Enumeration (guessing product IDs rapidly), and Scraping.

### C. The ML Pipeline (`ml-pipeline/`)
* **Tech Stack**: PyTorch, Pandas, Scikit-Learn
* **Purpose**: To convert raw database logs into mathematical features and train the Autoencoder.
* **How it works**:
  1. **Feature Engineering**: Raw logs are grouped by `session_id`. We calculate statistical features like `request_count`, `mean_inter_request_time` (time between clicks), and `failed_auth_ratio`.
  2. **Training**: The `DenseAutoencoder` (a deep neural network) compresses these 14 features into a tiny bottleneck of just 6 numbers, then tries to reconstruct the original 14 features. 
  3. **Threshold Calculation**: After training on normal data, we calculate the 99th percentile of the reconstruction error. We save this threshold (`τ`); anything with an error higher than this is officially flagged as an attack.

### D. The Scoring Engine (`scoring-engine/`)
* **Tech Stack**: Python, FastAPI, WebSockets
* **Purpose**: This is the real-time "brain" of the operation. It sits between the database and the dashboard.
* **How it works**: It runs a continuous `while True` polling loop. Every 2 seconds, it checks the SQLite database for new `request_logs`. If it finds new logs, it immediately extracts their mathematical features, passes them into the pre-trained PyTorch model, and computes the anomaly score. If the score is higher than our threshold `τ`, it generates an Alert. It instantly broadcasts the scores and alerts over a live WebSocket.

### E. The SOC Dashboard (`dashboard/`)
* **Tech Stack**: React, Vite, Recharts
* **Purpose**: To provide a Security Operations Center (SOC) analyst with a visual representation of the network.
* **How it works**: It establishes a persistent WebSocket connection to the Scoring Engine. As the engine evaluates traffic, the dashboard receives JSON payloads and dynamically updates the charts, tables, and alert feeds without ever needing to refresh the page.

---

## 3. The End-to-End Data Flow (Minute by Minute)

Let's trace exactly what happens when an attacker runs a Credential Stuffing attack against your system:

1. **Generation**: The attacker script (`traffic-simulator/profiles/attacks/credential_stuffing.py`) fires 50 POST requests to `/api/auth/login` in under 2 seconds.
2. **Ingestion**: The Flask `target-api` intercepts these 50 requests in its middleware and writes them to the `request_logs` SQLite table.
3. **Polling**: Within 2 seconds, the `scoring-engine`'s async loop fetches these 50 new logs.
4. **Feature Extraction**: The engine groups them by session. It notices that `request_count` is 50, `failed_auth_ratio` is 98%, and `mean_inter_request_time` is 0.04 seconds.
5. **Scoring**: This feature vector is pushed through the PyTorch Autoencoder. Because the Autoencoder has *never* seen a human click 50 times in 2 seconds, it fails miserably at compressing and reconstructing the data. It outputs a massive Reconstruction Error (e.g., `45.8`).
6. **Alerting**: The scoring engine sees `45.8` is much higher than our threshold (`~5.9`). It labels it `critical` and saves it to the `alerts` table.
7. **Visualization**: The engine emits a `{"type": "alert", ...}` JSON payload over the WebSocket. The React Dashboard receives this, increments the Critical Alerts counter, flashes the session red in the Active Sessions table, and pushes a notification to the side panel.
