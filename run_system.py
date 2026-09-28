"""
One-click Runner for AI-Powered V2X Network (SIH26203).
Starts Uvicorn server hosting FastAPI backend, Edge AI loop, and Web Dashboard.
"""

import sys
import os
import uvicorn

if __name__ == "__main__":
    # Ensure current directory is on PYTHONPATH
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    print("=" * 70)
    print(" AI-POWERED V2X NETWORK - SMART TRAFFIC & EMERGENCY PREEMPTION")
    print(" SIH26203 | Smart Vehicles | Team: Neural Optimizers")
    print("=" * 70)
    print("Starting 5G MEC Edge Low-Latency Engine & Digital Twin Dashboard...")
    print("Dashboard URL: http://localhost:8000")
    print("Ollama Copilot: http://127.0.0.1:11434 (Auto-detected)")
    print("=" * 70)

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, log_level="info", reload=False)
