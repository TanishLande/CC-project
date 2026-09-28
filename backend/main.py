"""
Main FastAPI Application & Low-Latency Edge Orchestrator.
Coordinates:
- V2X Ingest Gateway & PKI Validation
- Sensor Fusion & Local Dynamic Map (LDM)
- Edge AI Collision Risk & Intent Engine (<20ms latency)
- Adaptive Signal Control & Emergency Vehicle Preemption
- Regional Cloud Data Lake & Event Streaming Bus
- Ollama Local LLM Traffic Ops / PSAP Copilot
- Real-Time WebSocket Streaming & Web Dashboard
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.gateway.pki import PKISecurityEngine
from backend.gateway.ingest import V2XIngestGateway
from backend.fusion.ldm import LocalDynamicMapEngine
from backend.edge_ai.ttc_engine import EdgeAIEngine
from backend.edge_ai.safety_alerts import SafetyAlertManager
from backend.signal_control.adaptive_controller import AdaptiveSignalController
from backend.signal_control.spat_broadcaster import SPaTBroadcaster
from backend.cloud_platform.event_bus import EventStreamingBus
from backend.cloud_platform.data_lake import MobilityDataLake
from backend.cloud_platform.network_optimizer import NetworkOptimizer
from backend.copilot.ollama_copilot import OllamaTrafficCopilot
from backend.simulation.world_sim import WorldSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("V2XSystem")

app = FastAPI(
    title="AI-Powered V2X Network (SIH26203)",
    description="Edge-first real-time traffic coordination, adaptive signal control, and automated emergency preemption",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Subsystem Initialization ---
pki_engine = PKISecurityEngine()
gateway = V2XIngestGateway(pki_engine=pki_engine)
ldm_engine = LocalDynamicMapEngine(intersection_id="INT_01")
edge_ai = EdgeAIEngine()
alert_manager = SafetyAlertManager()
signal_controller = AdaptiveSignalController(intersection_id="INT_01")
spat_broadcaster = SPaTBroadcaster(intersection_id="INT_01")
event_bus = EventStreamingBus()
data_lake = MobilityDataLake()
network_optimizer = NetworkOptimizer()
copilot = OllamaTrafficCopilot()
world_sim = WorldSimulator(pki=pki_engine)

# Active WebSocket connections
connected_clients: List[WebSocket] = []
simulation_task: Optional[asyncio.Task] = None
is_network_outage_simulated = False


# --- Background Edge AI & Simulation Loop ---
async def edge_inference_loop():
    """
    Simulates high-speed 5G MEC edge compute execution at 10 Hz (every 100ms).
    Ingests messages, executes Kalman fusion, runs vectorized TTC inference (<20ms),
    updates adaptive signals, and streams telemetry to connected dashboards.
    """
    logger.info("Starting Edge AI Low-Latency Inference Loop...")
    last_time = time.perf_counter()

    while True:
        try:
            now = time.perf_counter()
            dt = min(0.2, max(0.05, now - last_time))
            last_time = now

            # 1. Step Simulation & Generate V2X telemetry
            bsm_list, vru_list = world_sim.step(dt, signal_controller.phases)

            # 2. Ingest via Gateway with PKI validation
            for bsm_raw in bsm_list:
                valid, bsm, reason = gateway.ingest_bsm(bsm_raw)
                if valid and bsm:
                    fused_track = ldm_engine.update_vehicle(bsm)
                    data_lake.trajectories_logged += 1
                    event_bus.publish("v2x.telemetry.raw", bsm.model_dump())

                    # Auto-detect approaching emergency vehicle for autonomous preemption
                    if fused_track.is_emergency and not signal_controller.preemption_engine.active_preemption:
                        # Determine approach direction
                        approach = "SOUTH" if fused_track.y < -35.0 else ("NORTH" if fused_track.y > 35.0 else "EAST")
                        eta = max(1.0, abs(fused_track.y if approach in ["NORTH", "SOUTH"] else fused_track.x) / max(fused_track.speed, 5.0))
                        logger.info(f"AUTONOMOUS EVP: Detected {fused_track.track_id} approaching on {approach} (ETA: {eta:.1f}s)")
                        event = signal_controller.trigger_preemption(fused_track.track_id, approach, eta_seconds=eta)
                        data_lake.log_preemption_event(event)
                        event_bus.publish("v2x.emergency.preemption", event)

            for vru_raw in vru_list:
                valid, vru, reason = gateway.ingest_vru(vru_raw)
                if valid and vru:
                    ldm_engine.update_vru(vru)

            # 3. Step Adaptive Signal Controller with live queue pressure
            queues = ldm_engine.calculate_approach_queues()
            spat = signal_controller.step(dt, queues)
            ldm_engine.update_spat(spat)

            # 4. Run Edge AI Collision Risk & Intent Inference (< 20ms budget)
            t_edge_start = time.perf_counter()
            raw_alerts, edge_latency_ms = edge_ai.compute_risk_and_alerts(ldm_engine.fused_tracks, spat)
            dispatched_alerts = alert_manager.filter_and_broadcast(raw_alerts)
            
            # Log incidents into data lake
            for alert in dispatched_alerts:
                data_lake.log_incident(alert.model_dump())
                event_bus.publish("v2x.safety.alerts", alert.model_dump())

            # Log SPaT packets periodically into sniffer
            gateway.log_spat_packet(spat.intersection_id, spat.active_phase_ids, spat.preemption_active)

            # 5. Check if Emergency Vehicle has passed intersection to clear preemption
            if signal_controller.preemption_engine.active_preemption:
                ev_id = signal_controller.preemption_engine.active_preemption["vehicle_id"]
                if ev_id in ldm_engine.fused_tracks:
                    ev_track = ldm_engine.fused_tracks[ev_id]
                    # Cleared when vehicle completely crosses the entire intersection (y > 48m)
                    if ev_track.y > 48.0 or ev_track.y < -55.0:
                        logger.info(f"Preemption cleared for {ev_id}. Intersection flushed.")
                        cleared = signal_controller.clear_preemption()
                        if cleared:
                            event_bus.publish("v2x.emergency.preemption", cleared)

            # 6. Assemble LDM Snapshot & Broadcast via WebSockets
            snapshot = ldm_engine.get_snapshot()
            snapshot.active_alerts = dispatched_alerts
            snapshot.edge_inference_latency_ms = edge_latency_ms

            if connected_clients:
                ws_payload = {
                    "type": "TELEMETRY_UPDATE",
                    "timestamp": time.time(),
                    "ldm": snapshot.model_dump(),
                    "spat": spat_broadcaster.format_spat_broadcast(spat),
                    "gateway_stats": gateway.stats,
                    "v2x_packets": gateway.get_recent_packets(25),
                    "metrics": data_lake.get_summary_metrics(),
                    "edge_latency_ms": edge_latency_ms,
                    "preemption_active": signal_controller.preemption_engine.active_preemption is not None,
                    "preemption_stage": signal_controller.preemption_engine.active_preemption["stage"] if signal_controller.preemption_engine.active_preemption else None,
                }
                
                # Send to all connected frontend clients
                disconnected = []
                for ws in connected_clients:
                    try:
                        await ws.send_json(ws_payload)
                    except Exception:
                        disconnected.append(ws)
                for ws in disconnected:
                    if ws in connected_clients:
                        connected_clients.remove(ws)

        except Exception as e:
            logger.error(f"Error in edge inference loop: {e}", exc_info=True)

        await asyncio.sleep(0.1)  # 10 Hz refresh rate


@app.on_event("startup")
async def startup_event():
    global simulation_task
    simulation_task = asyncio.create_task(edge_inference_loop())


@app.on_event("shutdown")
async def shutdown_event():
    if simulation_task:
        simulation_task.cancel()


# --- REST API Endpoints ---
@app.get("/api/status")
async def get_status():
    ollama_ready = copilot.is_available()
    return {
        "status": "ONLINE",
        "system": "AI-Powered V2X Network",
        "team": "Neural Optimizers",
        "problem_statement": "SIH26203",
        "edge_compute": {
            "platform": "5G MEC / Jetson Edge Simulator",
            "last_latency_ms": edge_ai.last_inference_latency_ms,
            "latency_budget_ms": 20.0,
            "within_budget": edge_ai.last_inference_latency_ms < 20.0,
        },
        "ollama": {
            "status": "READY" if ollama_ready else "OFFLINE",
            "model": copilot.model_name
        },
        "gateway": gateway.stats
    }


@app.get("/api/ldm")
async def get_ldm():
    return ldm_engine.get_snapshot()


@app.get("/api/metrics")
async def get_metrics():
    return data_lake.get_summary_metrics()


@app.get("/api/corridor")
async def get_corridor_plan():
    return {
        "corridor_name": "Janpath Smart Arterial Corridor (Bhubaneswar)",
        "intersections": network_optimizer.calculate_green_wave_offsets(),
        "target_speed_kmh": 50.0
    }


class ScenarioRequest(BaseModel):
    scenario: str  # "NORMAL_FLOW", "PEAK_HOUR", "EMERGENCY_AMBULANCE", "VRU_HAZARD", "NETWORK_OUTAGE"


@app.post("/api/scenario")
async def set_scenario(req: ScenarioRequest):
    global is_network_outage_simulated
    world_sim.active_scenario = req.scenario

    if req.scenario == "EMERGENCY_AMBULANCE":
        veh = world_sim.trigger_ambulance_scenario(approach="SOUTH")
        return {"status": "TRIGGERED", "scenario": req.scenario, "vehicle_id": veh.vehicle_id}
    elif req.scenario == "VRU_HAZARD":
        vru = world_sim.trigger_jaywalking_scenario()
        return {"status": "TRIGGERED", "scenario": req.scenario, "vru_id": vru.vru_id}
    elif req.scenario == "NETWORK_OUTAGE":
        is_network_outage_simulated = True
        return {"status": "TRIGGERED", "scenario": req.scenario, "message": "Cloud network disconnected. Edge AI continues autonomous signal control."}
    else:
        is_network_outage_simulated = False
        return {"status": "ACTIVATED", "scenario": req.scenario}


class PreemptRequest(BaseModel):
    vehicle_id: str = "AMB_911"
    approach: str = "SOUTH"
    eta_seconds: float = 8.0


@app.post("/api/preempt")
async def manual_preempt(req: PreemptRequest):
    event = signal_controller.trigger_preemption(req.vehicle_id, req.approach, req.eta_seconds)
    data_lake.log_preemption_event(event)
    event_bus.publish("v2x.emergency.preemption", event)
    return {"status": "PREEMPTION_ACTIVE", "event": event}


class CopilotChatRequest(BaseModel):
    query: str


@app.post("/api/copilot/chat")
async def copilot_chat(req: CopilotChatRequest):
    q_lower = req.query.lower()
    # If operator asks to dispatch/send an ambulance, trigger the real-time simulation preemption
    if any(k in q_lower for k in ["ambulance", "dispatch ambulance", "send ambulance", "send a ambulance", "send an ambulance", "fire truck", "emergency"]):
        logger.info("Copilot detected natural language ambulance dispatch request. Triggering EVP corridor!")
        world_sim.trigger_ambulance_scenario(approach="SOUTH")
        event = signal_controller.trigger_preemption("AMB_911", "SOUTH", eta_seconds=7.0)
        data_lake.log_preemption_event(event)
        event_bus.publish("v2x.emergency.preemption", event)

    snapshot = ldm_engine.get_snapshot()
    context = {
        "total_vehicles": snapshot.total_vehicles,
        "total_vrus": snapshot.total_vrus,
        "edge_latency_ms": edge_ai.last_inference_latency_ms,
        "active_phases": signal_controller.cycle_state,
        "queues": snapshot.queue_lengths,
        "preemption_active": signal_controller.preemption_engine.active_preemption is not None
    }
    answer = copilot.chat(req.query, context)
    return {
        "query": req.query,
        "answer": answer,
        "model": copilot.model_name
    }


@app.post("/api/copilot/debrief")
async def copilot_debrief():
    """Generates an intelligent LLM debrief on recent incidents or preemption."""
    recent_incidents = data_lake.near_miss_incidents
    snapshot = ldm_engine.get_snapshot()
    
    if recent_incidents:
        last_incident = recent_incidents[-1]
        debrief = copilot.generate_incident_report(last_incident, snapshot.model_dump())
        return {"type": "INCIDENT_DEBRIEF", "content": debrief, "data": last_incident}
    elif signal_controller.preemption_engine.active_preemption:
        brief = copilot.generate_preemption_brief(signal_controller.preemption_engine.active_preemption)
        return {"type": "PREEMPTION_BRIEF", "content": brief, "data": signal_controller.preemption_engine.active_preemption}
    else:
        return {
            "type": "STATUS_BRIEF",
            "content": f"Nominal operations across Janpath corridor. {snapshot.total_vehicles} vehicles and {snapshot.total_vrus} VRUs actively tracked in Local Dynamic Map. Edge inference latency benchmarked at {edge_ai.last_inference_latency_ms:.2f}ms (well within <20ms budget)."
        }


# --- WebSocket Streaming ---
@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"Client connected to telemetry stream (total: {len(connected_clients)})")
    try:
        while True:
            # Keep connection alive and listen for client messages
            msg = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        logger.info(f"Client disconnected (total: {len(connected_clients)})")


# --- Mount Frontend Static Assets Safely Without Breaking WebSockets ---
import os
from starlette.responses import FileResponse

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

app.mount("/css", StaticFiles(directory="frontend/css"), name="css")
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")

@app.get("/{filename:path}")
async def serve_static_fallback(filename: str):
    file_path = os.path.join("frontend", filename)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

