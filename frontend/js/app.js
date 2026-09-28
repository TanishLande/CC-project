/**
 * Main Client Application Coordinator for V2X Tactical Operations Center.
 * Handles WebSocket telemetry, canvas digital twin, SPaT, analytics,
 * scenario controls, and the real-time C-V2X Protocol Packet Sniffer.
 */

document.addEventListener('DOMContentLoaded', () => {
  const renderer = new TrafficCanvasRenderer('traffic-canvas');
  const copilot = new CopilotManager();
  const analytics = new AnalyticsManager();

  const preemptionOverlay = document.getElementById('preemption-overlay');
  const preemptionDetails = document.getElementById('preemption-details');
  const scenarioBadge = document.getElementById('active-scenario-badge');
  const btnToggleTracks = document.getElementById('btn-toggle-tracks');
  const btnTriggerEvp = document.getElementById('btn-trigger-evp');

  // Packet Sniffer Elements
  const packetBody = document.getElementById('v2x-packet-body');
  const packetCounterBadge = document.getElementById('packet-counter-badge');
  const btnPausePackets = document.getElementById('btn-pause-packets');
  const btnClearPackets = document.getElementById('btn-clear-packets');
  const filterChips = document.querySelectorAll('.filter-chips .chip');

  let isPacketStreamPaused = false;
  let currentPacketFilter = 'ALL';
  let packetStore = [];
  let totalPacketsReceived = 0;

  // Toggle velocity vector arrows
  btnToggleTracks.addEventListener('click', () => {
    renderer.showVectors = !renderer.showVectors;
    btnToggleTracks.textContent = renderer.showVectors ? 'Hide Vectors' : 'Show Vectors';
  });

  // Scenario Buttons
  document.querySelectorAll('.btn-scenario').forEach(btn => {
    btn.addEventListener('click', async () => {
      const scenario = btn.dataset.scenario;
      scenarioBadge.textContent = scenario.replace('_', ' ');
      try {
        await fetch('/api/scenario', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario })
        });
      } catch (err) {
        console.error('Failed to trigger scenario:', err);
      }
    });
  });

  // Emergency Ambulance Dispatch Button
  btnTriggerEvp.addEventListener('click', async () => {
    scenarioBadge.textContent = 'EMERGENCY AMBULANCE';
    try {
      // 1. Spawn ambulance directly in simulation view
      await fetch('/api/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: 'EMERGENCY_AMBULANCE' })
      });
      // 2. Trigger preemption corridor
      await fetch('/api/preempt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vehicle_id: 'AMB_911', approach: 'SOUTH', eta_seconds: 7.0 })
      });
      // Also announce in copilot chat
      copilot.appendMessage('TACTICAL DISPATCH', 'EMERGENCY DISPATCH INITIATED: High-priority green-wave corridor cleared on South approach for AMB_911.', 'ai');
    } catch (err) {
      console.error('Failed to dispatch preemption:', err);
    }
  });

  // --- Packet Sniffer Handlers ---
  btnPausePackets.addEventListener('click', () => {
    isPacketStreamPaused = !isPacketStreamPaused;
    btnPausePackets.textContent = isPacketStreamPaused ? 'Resume' : 'Pause';
    btnPausePackets.style.color = isPacketStreamPaused ? '#f59e0b' : '';
  });

  btnClearPackets.addEventListener('click', () => {
    packetStore = [];
    if (packetBody) packetBody.innerHTML = '';
    if (packetCounterBadge) packetCounterBadge.textContent = 'STREAMING: 0 PKTS';
  });

  filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentPacketFilter = chip.dataset.filter;
      renderPackets();
    });
  });

  function processIncomingPackets(packets) {
    if (!packets || !packets.length || isPacketStreamPaused) return;

    totalPacketsReceived += packets.length;
    for (const pkt of packets) {
      // Avoid duplicate msg_id in recent list
      if (!packetStore.some(p => p.msg_id === pkt.msg_id)) {
        packetStore.unshift(pkt);
      }
    }
    if (packetStore.length > 80) {
      packetStore = packetStore.slice(0, 80);
    }

    renderPackets();
  }

  function renderPackets() {
    if (!packetBody) return;

    const filtered = packetStore.filter(p => {
      if (currentPacketFilter === 'ALL') return true;
      if (currentPacketFilter === 'EVA') return p.protocol_type.includes('EVA');
      if (currentPacketFilter === 'BSM') return p.protocol_type.includes('BSM');
      if (currentPacketFilter === 'VRU') return p.protocol_type.includes('VRU');
      if (currentPacketFilter === 'SPAT') return p.protocol_type.includes('SPaT');
      return true;
    });

    if (packetCounterBadge) {
      packetCounterBadge.textContent = `LIVE: ${packetStore.length} RECENT (${totalPacketsReceived} TOTAL)`;
    }

    let rowsHtml = '';
    for (const pkt of filtered.slice(0, 25)) {
      let badgeClass = 'bsm';
      let icon = '🚗';
      if (pkt.protocol_type.includes('EVA')) {
        badgeClass = 'eva';
        icon = '🚨';
      } else if (pkt.protocol_type.includes('VRU')) {
        badgeClass = 'vru';
        icon = '🚶';
      } else if (pkt.protocol_type.includes('SPaT')) {
        badgeClass = 'spat';
        icon = '🚦';
      }

      rowsHtml += `
        <tr>
          <td style="color: #94a3b8;">${pkt.time_str}</td>
          <td><span class="pkt-badge ${badgeClass}">${icon} ${pkt.protocol_type}</span></td>
          <td style="font-weight: 700; color: ${pkt.entity_id.includes('AMB') ? '#ef4444' : '#e2e8f0'};">${pkt.entity_id}</td>
          <td style="color: #38bdf8;">${pkt.approach}</td>
          <td style="color: #cbd5e1;">${pkt.telemetry}</td>
          <td>
            <span class="pki-verified-tag">
              ✓ ${pkt.pki_status} <span style="color: #64748b; font-size: 0.65rem;">[${pkt.cert_id}]</span>
            </span>
          </td>
        </tr>
      `;
    }

    packetBody.innerHTML = rowsHtml;
  }

  // --- WebSocket Telemetry Client ---
  let ws = null;
  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;
    
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('Connected to 5G MEC edge telemetry stream.');
      document.getElementById('edge-status-val').textContent = '5G MEC ACTIVE';
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'TELEMETRY_UPDATE') {
          // Render Canvas Digital Twin
          renderer.render(msg.ldm, msg.spat, msg.preemption_active);

          // Update SPaT & Queues
          analytics.updateSPaT(msg.spat, msg.ldm.queue_lengths);

          // Update Telemetry & Benchmarks
          analytics.updateEdgeTelemetry(msg.edge_latency_ms, msg.gateway_stats, msg.metrics);

          // Update Safety Alerts
          analytics.updateAlerts(msg.ldm.active_alerts || []);

          // Update Live C-V2X Packet Sniffer
          if (msg.v2x_packets) {
            processIncomingPackets(msg.v2x_packets);
          }

          // Preemption Banner
          if (msg.preemption_active) {
            preemptionOverlay.classList.remove('hidden');
            preemptionDetails.textContent = `Stage: ${msg.preemption_stage || 'ACTIVE_GREEN'} | Priority Corridor: Janpath South (AMB_911)`;
          } else {
            preemptionOverlay.classList.add('hidden');
          }
        }
      } catch (e) {
        console.error('Error processing telemetry frame:', e);
      }
    };

    ws.onclose = () => {
      document.getElementById('edge-status-val').textContent = 'RECONNECTING...';
      setTimeout(connectWebSocket, 1500);
    };

    ws.onerror = (err) => {
      console.warn('WebSocket encountered error:', err);
    };
  }

  connectWebSocket();
});
