/**
 * Telemetry and Analytics Manager for V2X Dashboard.
 * Updates SPaT signals, latency metrics, safety alerts feed, and SIH impact stats.
 */

class AnalyticsManager {
  constructor() {
    this.edgeLatencyVal = document.getElementById('edge-latency-val');
    this.alertCount = document.getElementById('alert-count');
    this.alertsContainer = document.getElementById('alerts-stream-container');
    this.livesSavedVal = document.getElementById('stat-lives-saved');
    this.corridorsClearedVal = document.getElementById('stat-corridors-cleared');
    this.valBsmCount = document.getElementById('val-bsm-count');
    this.valVruCount = document.getElementById('val-vru-count');
    this.rejCount = document.getElementById('rej-count');
  }

  updateEdgeTelemetry(latencyMs, gatewayStats, metrics) {
    if (this.edgeLatencyVal) {
      this.edgeLatencyVal.textContent = `${latencyMs.toFixed(2)} ms`;
      if (latencyMs > 20.0) {
        this.edgeLatencyVal.style.color = '#ef4444';
      } else {
        this.edgeLatencyVal.style.color = '#06b6d4';
      }
    }

    if (gatewayStats) {
      if (this.valBsmCount) this.valBsmCount.textContent = gatewayStats.by_type.BSM || 0;
      if (this.valVruCount) this.valVruCount.textContent = gatewayStats.by_type.VRU || 0;
      if (this.rejCount) this.rejCount.textContent = gatewayStats.rejected_count || 0;
    }

    if (metrics) {
      if (this.corridorsClearedVal) {
        this.corridorsClearedVal.textContent = metrics.preemptions_count || 0;
      }
      if (this.livesSavedVal && metrics.simulated_lives_saved !== undefined) {
        this.livesSavedVal.textContent = `~${metrics.simulated_lives_saved} lives (Est)`;
      }
    }
  }

  updateSPaT(spat, queues) {
    if (!spat || !spat.phases) return;

    const dirMap = { 1: 'north', 2: 'south', 3: 'east', 4: 'west' };
    const queueNames = { 1: 'NORTH', 2: 'SOUTH', 3: 'EAST', 4: 'WEST' };

    for (let pid = 1; pid <= 4; pid++) {
      const dir = dirMap[pid];
      const p = spat.phases[pid];
      if (!p) continue;

      const card = document.getElementById(`sig-${dir}`);
      const timer = document.getElementById(`timer-${dir}`);
      const queueEl = document.getElementById(`queue-${dir}`);

      if (timer) timer.textContent = `${Math.ceil(p.time_remaining_sec)}s`;
      if (queueEl && queues) {
        queueEl.textContent = `Q: ${queues[queueNames[pid]] || 0} veh`;
      }

      if (card) {
        const redBulb = card.querySelector('.bulb.red');
        const yellowBulb = card.querySelector('.bulb.yellow');
        const greenBulb = card.querySelector('.bulb.green');

        redBulb.className = 'bulb red' + (p.state === 'RED' ? ' active' : '');
        yellowBulb.className = 'bulb yellow' + (p.state === 'YELLOW' ? ' active' : '');
        greenBulb.className = 'bulb green' + (p.state === 'GREEN' || p.state === 'PREEMPTION_GREEN' ? ' active' : '');
      }
    }
  }

  updateAlerts(alerts) {
    if (!this.alertsContainer) return;
    this.alertCount.textContent = `${alerts.length} Active`;

    if (alerts.length === 0) {
      this.alertsContainer.innerHTML = '<div class="empty-alerts">All approaches clear. Edge AI continuously screening collision cones.</div>';
      return;
    }

    let html = '';
    for (const alert of alerts) {
      const isCritical = alert.severity === 'CRITICAL';
      html += `
        <div class="alert-item ${isCritical ? 'critical' : 'warning'}">
          <strong>${alert.alert_type}</strong> [TTC: ${alert.ttc_seconds}s]
          <div>${alert.message}</div>
          <div style="color: #60a5fa; font-size: 0.65rem;">Action: ${alert.recommended_action}</div>
        </div>
      `;
    }
    this.alertsContainer.innerHTML = html;
  }
}
