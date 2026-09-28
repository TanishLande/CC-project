/**
 * High-Performance Digital Twin Canvas Renderer for V2X Local Dynamic Map.
 * Renders intersection geometry, lane topology, SPaT lights, vehicles, VRUs,
 * collision risk cones (TTC), and emergency preemption corridors.
 */

class TrafficCanvasRenderer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    
    // Scale: meters to pixels (shows ~85 meters in all directions)
    this.scale = 3.2;
    this.showVectors = true;
    this.radarAngle = 0.0;
    
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width || 800;
    this.canvas.height = 580;
    this.cx = this.canvas.width / 2;
    this.cy = this.canvas.height / 2;
  }

  worldToScreen(x, y) {
    // x: East (+), West (-)
    // y: North (+), South (-)
    return {
      sx: this.cx + x * this.scale,
      sy: this.cy - y * this.scale
    };
  }

  render(ldm, spat, preemptionActive) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // 1. Draw Road Geometry (Layer 1)
    this.drawRoads(ctx, preemptionActive);

    // 2. Draw Crosswalks and Stop Lines (Layer 2)
    this.drawCrosswalks(ctx);

    // 3. Draw RSU Radar Sweeper
    this.drawRSURadar(ctx);

    // 4. Draw SPaT Signal Heads on Roadways
    if (spat) {
      this.drawSignalHeads(ctx, spat);
    }

    if (!ldm || !ldm.tracks) return;

    // 5. Draw Collision Risk Vectors / Cones (Layer 3)
    if (ldm.active_alerts && ldm.active_alerts.length > 0) {
      this.drawCollisionAlerts(ctx, ldm.active_alerts, ldm.tracks);
    }

    // 6. Draw Dynamic Participants (Layer 4)
    for (const [tid, track] of Object.entries(ldm.tracks)) {
      if (track.entity_type === 'vehicle') {
        this.drawVehicle(ctx, track);
      } else if (track.entity_type === 'vru') {
        this.drawVRU(ctx, track);
      }
    }
  }

  drawRoads(ctx, preemptionActive) {
    const roadWidth = 30 * this.scale;

    ctx.fillStyle = '#111625';
    // North-South Road
    ctx.fillRect(this.cx - roadWidth / 2, 0, roadWidth, this.canvas.height);
    // East-West Road
    ctx.fillRect(0, this.cy - roadWidth / 2, this.canvas.width, roadWidth);

    // If preemption active, illuminate corridor in translucent green
    if (preemptionActive) {
      ctx.fillStyle = 'rgba(16, 185, 129, 0.22)';
      ctx.fillRect(this.cx - roadWidth / 2, 0, roadWidth, this.canvas.height);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2.5;
      ctx.strokeRect(this.cx - roadWidth / 2, 0, roadWidth, this.canvas.height);
    }

    // Lane Dividers
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 8]);

    // NS Center line
    ctx.beginPath();
    ctx.moveTo(this.cx, 0);
    ctx.lineTo(this.cx, this.cy - roadWidth / 2);
    ctx.moveTo(this.cx, this.cy + roadWidth / 2);
    ctx.lineTo(this.cx, this.canvas.height);
    ctx.stroke();

    // EW Center line
    ctx.beginPath();
    ctx.moveTo(0, this.cy);
    ctx.lineTo(this.cx - roadWidth / 2, this.cy);
    ctx.moveTo(this.cx + roadWidth / 2, this.cy);
    ctx.lineTo(this.canvas.width, this.cy);
    ctx.stroke();

    ctx.setLineDash([]);
  }

  drawCrosswalks(ctx) {
    const roadWidth = 30 * this.scale;
    const cwDist = 24 * this.scale;

    ctx.fillStyle = '#475569';
    for (let i = -roadWidth / 2 + 5; i < roadWidth / 2 - 5; i += 12) {
      ctx.fillRect(this.cx + i, this.cy - cwDist - 10, 7, 18);
      ctx.fillRect(this.cx + i, this.cy + cwDist - 8, 7, 18);
    }

    for (let i = -roadWidth / 2 + 5; i < roadWidth / 2 - 5; i += 12) {
      ctx.fillRect(this.cx + cwDist - 8, this.cy + i, 18, 7);
      ctx.fillRect(this.cx - cwDist - 10, this.cy + i, 18, 7);
    }

    // Stop lines
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(this.cx, this.cy - cwDist - 14);
    ctx.lineTo(this.cx + roadWidth / 2, this.cy - cwDist - 14);
    ctx.moveTo(this.cx - roadWidth / 2, this.cy + cwDist + 14);
    ctx.lineTo(this.cx, this.cy + cwDist + 14);
    ctx.moveTo(this.cx + cwDist + 14, this.cy);
    ctx.lineTo(this.cx + cwDist + 14, this.cy + roadWidth / 2);
    ctx.moveTo(this.cx - cwDist - 14, this.cy - roadWidth / 2);
    ctx.lineTo(this.cx - cwDist - 14, this.cy);
    ctx.stroke();
  }

  drawRSURadar(ctx) {
    const rsuPos = this.worldToScreen(22, 22);
    this.radarAngle = (this.radarAngle + 0.04) % (Math.PI * 2);

    const sweepRadius = 150;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(rsuPos.sx, rsuPos.sy);
    ctx.arc(rsuPos.sx, rsuPos.sy, sweepRadius, this.radarAngle, this.radarAngle + 0.35);
    ctx.closePath();
    ctx.fillStyle = 'rgba(6, 182, 212, 0.08)';
    ctx.fill();

    ctx.fillStyle = '#06b6d4';
    ctx.beginPath();
    ctx.arc(rsuPos.sx, rsuPos.sy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.font = '9px monospace';
    ctx.fillText('RSU-5G', rsuPos.sx + 8, rsuPos.sy + 3);
    ctx.restore();
  }

  drawSignalHeads(ctx, spat) {
    if (!spat.phases) return;
    const roadWidth = 30 * this.scale;
    const offset = roadWidth / 2 + 15;

    const renderLight = (sx, sy, state) => {
      ctx.save();
      let color = '#ef4444';
      if (state === 'GREEN' || state === 'PREEMPTION_GREEN') color = '#10b981';
      else if (state === 'YELLOW') color = '#f59e0b';

      ctx.beginPath();
      ctx.arc(sx, sy, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.restore();
    };

    if (spat.phases[1]) renderLight(this.cx + 20, this.cy - offset, spat.phases[1].state);
    if (spat.phases[2]) renderLight(this.cx - 20, this.cy + offset, spat.phases[2].state);
    if (spat.phases[3]) renderLight(this.cx + offset, this.cy + 20, spat.phases[3].state);
    if (spat.phases[4]) renderLight(this.cx - offset, this.cy - 20, spat.phases[4].state);
  }

  drawVehicle(ctx, track) {
    const pos = this.worldToScreen(track.x, track.y);
    const isAmb = track.is_emergency || track.track_id.includes('AMB');
    
    // Ambulance dimensions: larger, more visible
    const w = (isAmb ? 3.4 : (track.width || 2.2)) * this.scale;
    const l = (isAmb ? 7.2 : (track.length || 4.6)) * this.scale;

    // Siren pulse waves radiating from ambulance
    if (isAmb) {
      const t = Date.now() / 350;
      for (let r = 0; r < 3; r++) {
        const rad = (((t + r * 0.33) % 1.0) * 45) + 8;
        ctx.beginPath();
        ctx.arc(pos.sx, pos.sy, rad, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(239, 68, 68, ${0.85 - rad / 55})`;
        ctx.lineWidth = 2.0;
        ctx.stroke();
      }
    }

    ctx.save();
    ctx.translate(pos.sx, pos.sy);
    ctx.rotate((track.heading * Math.PI) / 180);

    if (isAmb) {
      // High-visibility Emergency Ambulance
      const flash = (Math.floor(Date.now() / 140) % 2 === 0);

      // Body (Pure White)
      ctx.fillStyle = '#ffffff';
      ctx.shadowColor = flash ? '#ef4444' : '#00f0ff';
      ctx.shadowBlur = 24;
      ctx.fillRect(-w / 2, -l / 2, w, l);

      // Red side safety stripes
      ctx.fillStyle = '#dc2626';
      ctx.fillRect(-w / 2, -l / 2, 2.5, l);
      ctx.fillRect(w / 2 - 2.5, -l / 2, 2.5, l);

      // Windshield (Dark Blue Tint)
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(-w / 2 + 2, -l / 2 + 3, w - 4, l * 0.22);

      // Medical Red Cross on roof
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(-1.5, -1.5, 3, 7);
      ctx.fillRect(-3.5, 0.5, 7, 3);

      // Dual Emergency Lightbar (Strobe red and blue)
      ctx.fillStyle = flash ? '#ef4444' : '#00f0ff';
      ctx.fillRect(-w / 2 + 1, -l / 2 + 1, w / 2 - 2, 3);
      ctx.fillStyle = flash ? '#00f0ff' : '#ef4444';
      ctx.fillRect(1, -l / 2 + 1, w / 2 - 2, 3);

      // Headlight beams casting forward
      ctx.fillStyle = 'rgba(254, 240, 138, 0.25)';
      ctx.beginPath();
      ctx.moveTo(-w / 2 + 1, -l / 2);
      ctx.lineTo(-w * 1.2, -l * 1.6);
      ctx.lineTo(w * 1.2, -l * 1.6);
      ctx.lineTo(w / 2 - 1, -l / 2);
      ctx.fill();

    } else if (track.sub_type === 'bus') {
      ctx.fillStyle = '#f59e0b';
      ctx.fillRect(-w / 2, -l / 2, w, l);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(-w / 2 + 2, -l / 2 + 3, w - 4, l * 0.2);
    } else {
      // Normal Passenger Car
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(-w / 2, -l / 2, w, l);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(-w / 2 + 2, -l / 2 + 3, w - 4, l * 0.25);
    }

    ctx.restore();

    // Velocity Vector
    if (this.showVectors && track.speed > 0.5) {
      ctx.strokeStyle = isAmb ? '#ef4444' : '#06b6d4';
      ctx.lineWidth = isAmb ? 2.5 : 1.5;
      ctx.beginPath();
      ctx.moveTo(pos.sx, pos.sy);
      ctx.lineTo(pos.sx + track.vx * this.scale * 1.5, pos.sy - track.vy * this.scale * 1.5);
      ctx.stroke();
    }

    // Vehicle ID & HUD Badge
    if (isAmb) {
      // Glowing Emergency HUD Badge
      ctx.save();
      const badgeText = `🚨 AMBULANCE [AMB-911] ${(track.speed * 3.6).toFixed(0)} km/h`;
      ctx.font = 'bold 11px monospace';
      const textWidth = ctx.measureText(badgeText).width;
      
      ctx.fillStyle = 'rgba(239, 68, 68, 0.95)';
      ctx.fillRect(pos.sx - textWidth / 2 - 6, pos.sy - 26, textWidth + 12, 16);
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(pos.sx - textWidth / 2 - 6, pos.sy - 26, textWidth + 12, 16);

      ctx.fillStyle = '#ffffff';
      ctx.fillText(badgeText, pos.sx - textWidth / 2, pos.sy - 14);
      ctx.restore();
    } else {
      ctx.fillStyle = '#cbd5e1';
      ctx.font = '9px monospace';
      ctx.fillText(`${track.track_id} (${(track.speed * 3.6).toFixed(0)}kph)`, pos.sx + 8, pos.sy - 8);
    }
  }

  drawVRU(ctx, track) {
    const pos = this.worldToScreen(track.x, track.y);

    ctx.save();
    ctx.beginPath();
    ctx.arc(pos.sx, pos.sy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#f43f5e'; // Pink/red for VRU
    ctx.shadowColor = '#f43f5e';
    ctx.shadowBlur = 8;
    ctx.fill();

    // Walking orientation line
    if (this.showVectors) {
      ctx.strokeStyle = '#fda4af';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(pos.sx, pos.sy);
      ctx.lineTo(pos.sx + track.vx * this.scale * 3.0, pos.sy - track.vy * this.scale * 3.0);
      ctx.stroke();
    }
    ctx.restore();

    ctx.fillStyle = '#fda4af';
    ctx.font = '9px monospace';
    ctx.fillText(`VRU [${track.track_id}]`, pos.sx + 7, pos.sy + 3);
  }

  drawCollisionAlerts(ctx, alerts, tracks) {
    for (const alert of alerts) {
      const p1 = tracks[alert.primary_entity_id];
      const p2 = tracks[alert.target_entity_id];
      if (!p1 || !p2) continue;

      const pos1 = this.worldToScreen(p1.x, p1.y);
      const pos2 = this.worldToScreen(p2.x, p2.y);

      // Draw pulsating hazard collision line
      ctx.save();
      ctx.strokeStyle = alert.severity === 'CRITICAL' ? '#ef4444' : '#f59e0b';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pos1.sx, pos1.sy);
      ctx.lineTo(pos2.sx, pos2.sy);
      ctx.stroke();

      // TTC label in center of collision vector
      const midX = (pos1.sx + pos2.sx) / 2;
      const midY = (pos1.sy + pos2.sy) / 2;
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 11px monospace';
      ctx.fillText(`⚠️ TTC: ${alert.ttc_seconds}s`, midX - 25, midY - 6);
      ctx.restore();
    }
  }
}
