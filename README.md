# AI-Powered V2X Network for Real-Time Traffic Coordination, Adaptive Signal Control, and Emergency Response

**Problem Statement ID:** SIH26203  
**Theme:** Smart Vehicles  
**Category:** Software  
**Team ID:** 141781  
**Team Name:** Neural Optimizers  

---

## Architecture Overview

This project implements an end-to-end, edge-first Intelligent Transportation System (ITS) aligned directly with the 4-layer architecture of the SIH proposal:

```
+---------------------------------------------------------------------------------------------------+
| 1. ROAD EDGE - V2X PARTICIPANTS                                                                   |
|   • Connected Vehicles: OBU - CAM/BSM msgs (GPS, speed, heading)                                 |
|   • VRUs: Pedestrians, cyclists (Phone/wearable app position telemetry)                          |
|   • RSU / Sensors: Radar, LiDAR, cameras (C-V2X PC5 / DSRC)                                      |
|   • Signal Controllers: Intersection cabinets (SPaT / MAP broadcast)                              |
+---------------------------------------------------------------------------------------------------+
                                         │ C-V2X (PC5 / 5G Uu)
                                         ▼
+---------------------------------------------------------------------------------------------------+
| 2. 5G MEC - LOW-LATENCY EDGE COMPUTE (<20ms budget)                                               |
|   ┌────────────────┐      ┌────────────────┐      ┌────────────────┐      ┌────────────────────┐  |
|   │  V2X Gateway   │ ───► │ Sensor Fusion  │ ───► │Edge AI Inferenc│ ───► │Adaptive Signal Ctrl│  |
|   │  PKI & Ingest  │      │  LDM Engine    │      │  TTC & Intent  │      │RL & Preemption Ctrl│  |
|   └────────────────┘      └────────────────┘      └────────────────┘      └────────────────────┘  |
|           ▲                                               │ Safety Alerts            │ Phase Cmds |
|           │                                               ▼                          ▼            |
|           │ (Preempt Requests)                    [Vehicle / VRUs]          [Signal Cabinets]     |
+───────────┼───────────────────────────────────────────────────────────────────────────────────────+
            │                                               │ Incidents & Telemetry
            ▼                                               ▼
+----------------------------------------+   +------------------------------------------------------+
| 3. REGIONAL CLOUD PLATFORM             |   | 4. EMERGENCY RESPONSE & OPERATIONS (PSAP)            |
|   • Event Streaming Bus (Kafka topics) │   |   • Emergency Vehicle Priority (Route clearing)      |
|   • Mobility Data Lake (Trajectories)  │   |   • Traffic Ops / PSAP Dashboard (Live Digital Twin) |
|   • Network-Wide Optimizer (Corridors) │   |   • Ollama Local LLM Copilot (llama3.2:3b / llama3.1)|
|   • AI Training & MLOps Digital Twin   │   |     - Automated Incident Debriefs                    |
|                                        │   |     - Natural Language Operator Assistance           |
+----------------------------------------+   +------------------------------------------------------+
```

---

## Key Features & Highlights

1. **Sub-20ms Edge AI Inference**:
   - Vectorized closest point of approach (CPA), Time-To-Collision (TTC), and Post-Encroachment Time (PET) evaluation.
   - Evaluates dense traffic in under **2 milliseconds**, well within the 20ms edge latency budget.
2. **Local Dynamic Map (LDM)**:
   - 4-tier standard architecture (Static Road Geometry, Infrastructure, Transient Phase Timers, Dynamic Trackers with Kalman Filtering).
3. **V2X PKI Security**:
   - Digital signature verification and cryptographic replay-attack rejection.
4. **Autonomous Emergency Vehicle Preemption (EVP)**:
   - Zero-delay corridor creation: transitioning cross-traffic from yellow clearance (2.5s) to all-red (1.0s) to preemption green for incoming ambulances or fire trucks.
5. **Ollama Local LLM Copilot**:
   - Real-time incident reasoning and operator conversational briefings using local models (e.g., `llama3.2:3b` or `llama3.1:8b`).
6. **Odisha Road Safety Benchmarking**:
   - Built-in analytics matching the SIH proposal:
     - Conservative: 26% crash reduction (~1,130 lives saved/year).
     - Optimistic: 80% crash reduction (~3,476 lives saved/year).
     - Emergency Preemption: 48.5% response delay reduction.

---

## Directory Structure

```
├── backend/
│   ├── main.py                     # FastAPI server, WebSocket orchestrator & REST endpoints
│   ├── models.py                   # SAE J2735 / ETSI data models (BSM, CAM, SPaT, MAP, EVA)
│   ├── gateway/                    # PKI security engine & telemetry ingest
│   ├── fusion/                     # Kalman filter & 4-tier Local Dynamic Map (LDM)
│   ├── edge_ai/                    # Sub-20ms vectorized TTC, PET & intent engine
│   ├── signal_control/             # Max-pressure adaptive controller & EVP engine
│   ├── cloud_platform/             # Event streaming bus, mobility data lake & network optimizer
│   ├── copilot/                    # Ollama local LLM integration for Traffic Ops / PSAP
│   └── simulation/                 # Multi-intersection realistic digital twin traffic simulator
├── frontend/
│   ├── index.html                  # Cyber-ITS tactical operations dashboard
│   ├── css/style.css               # Futuristic high-contrast dark theme UI
│   └── js/                         # Canvas digital twin, Ollama chat, telemetry scripts
├── tests/
│   ├── test_pki.py                 # PKI signature & replay attack tests
│   ├── test_edge_latency.py        # Sub-20ms edge latency benchmark
│   ├── test_preemption.py          # Emergency Preemption lifecycle tests
│   ├── test_copilot.py             # Ollama local LLM generation test
│   └── test_api_endpoints.py       # REST API integration tests
├── run_system.py                   # One-click Python launcher
└── run_system.bat                  # One-click Windows batch launcher
```

---

## How to Run

### 1. Launch the System
```bash
python run_system.py
```
*(Or double-click `run_system.bat` on Windows)*

### 2. Access the Operations Center
Open your web browser and navigate to:
```
http://localhost:8000
```

### 3. Run Automated Tests
```bash
python tests/test_pki.py
python tests/test_edge_latency.py
python tests/test_preemption.py
python tests/test_copilot.py
python tests/test_api_endpoints.py
```
