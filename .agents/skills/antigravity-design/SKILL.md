---
name: antigravity-design
description: Design principles and guidelines for Google Antigravity applications. Focuses on cinematic control-tower layouts, glassmorphism, glowing status badges, spatial depth, and human-in-the-loop decision cards.
---

# Antigravity Design System

The Antigravity design aesthetic combines developer-grade control-tower precision with modern cinematic polish.

## 1. Aesthetic Hallmarks

1. **Spatial Depth & Layering**:
   - Depth created through layered dark surfaces (`--bg-base: #080c14`, `--bg-panel: #101724`, `--bg-surface: #141f2f`).
   - Subtle outer glow on brand marks (`box-shadow: 0 0 24px rgba(85, 215, 237, 0.15)`).
   - Translucent backdrops (`backdrop-filter: blur(12px)`).

2. **Live Status Indicators**:
   - Pulsing status dots with radiant box-shadows:
     ```css
     .status-live span {
       width: 6px;
       height: 6px;
       border-radius: 50%;
       background: var(--green);
       box-shadow: 0 0 8px #56d6a1aa;
     }
     ```
   - Color semantic tokens:
     - Normal / Available / Valid: `#56d6a1` (Emerald)
     - Informational / AI Telemetry: `#55d7ed` (Cyan)
     - Warning / Review Required: `#f3b85b` (Amber)
     - Critical / Disrupted / Error: `#ff6c78` (Coral Red)

3. **Decision & Governance Cards**:
   - Prominently feature human approval state (`Pending`, `Approved`, `Rejected`).
   - Explicitly note demo/sandbox status to avoid confusing simulations with live system execution.
   - Display constraint violation counts with color coding (`0` = good, `>0` = alert).

4. **Multi-Agent Representation**:
   - Distinct icons and color-coded avatar backdrops for specialized agent modules.
   - Confidence percentage chips (`95% CONFIDENCE`).
   - Clear audit trails showing agent reasoning and actionable recommendations.
