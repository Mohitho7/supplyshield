# SupplyShield AI — Industrial Control Tower Design Specification

## 1. Visual Direction & Target Aesthetics
Inspired by the **XCaliber Industrial Control Tower** reference, tailored with SupplyShield's distinctive enterprise product identity:
- **Environment**: Deep matte charcoal base (`#0c0e14`) with low-reflection elevated surfaces (`#131622`, `#171c2b`).
- **Signature Accent**: Warm industrial orange (`#ff7a18`, `#ff8e38`) as the deliberate brand and primary action accent.
- **Analytical Precision**: Tabular monospace figures (`DM Mono`), high-contrast slate typography (`#f8fafc`, `#94a3b8`), and micro-gauges.
- **Visual Restraint**: Zero decorative AI gimmicks, no neon rainbow gradients, and no generic container nesting. Subtle glows are strictly confined to critical operational alerts (`#ef4444`) and confirmed authorizations (`#10b981`).

---

## 2. Design Tokens & CSS Architecture

### Canvas & Structural Surfaces
```css
--bg-canvas: #0c0e14;          /* Matte charcoal root background */
--bg-sidebar: #0e1017;         /* Sticky operational navigation */
--bg-topbar: #10131c;          /* Header utility strip */
--bg-surface: #131622;         /* Primary analytical panels */
--bg-surface-elevated: #171c2b;/* Interactive elevated cards & tooltips */
--bg-surface-subtle: #0f121a;  /* Inset telemetry rows & matrix cells */
--bg-surface-active: #1c2236;  /* Highlighted row / focused control */
```

### Hairline Borders
```css
--border-subtle: rgba(255, 255, 255, 0.06); /* Default structural boundary */
--border-medium: rgba(255, 255, 255, 0.10); /* Panel outlines & dividers */
--border-strong: rgba(255, 255, 255, 0.16); /* Interactive button borders */
--border-focus: #ff7a18;                     /* Active focus boundary */
```

### Signature Warm Orange Accent
```css
--orange: #ff7a18;                               /* Primary CTA background */
--orange-hover: #ff8e38;                         /* Hover interaction */
--orange-subtle: rgba(255, 122, 24, 0.10);       /* Badge background fill */
--orange-border: rgba(255, 122, 24, 0.32);       /* Accent border boundary */
--orange-glow: rgba(255, 122, 24, 0.18);         /* Restrained focus glow */
```

### Semantic Operational States
```css
/* Critical Disruption / Facility Outage */
--red: #ef4444;
--red-subtle: rgba(239, 68, 68, 0.12);
--red-border: rgba(239, 68, 68, 0.35);

/* Transit Gap / Advisory Notice */
--amber: #f59e0b;
--amber-subtle: rgba(245, 158, 11, 0.12);
--amber-border: rgba(245, 158, 11, 0.35);

/* Validated Guardrail / Planner Authorized */
--green: #10b981;
--green-subtle: rgba(16, 185, 129, 0.12);
--green-border: rgba(16, 185, 129, 0.35);
```

---

## 3. Typography System

| Role | Family | Size | Weight | Tracking | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Eyebrow Tag** | `DM Mono` | 10px | 600 | +0.8px | Section context and status identifiers |
| **Incident Title (H1)** | `Space Grotesk` | 24px | 700 | -0.3px | Clear incident statement |
| **Section Heading (H3)**| `Space Grotesk` | 16px | 600 | -0.2px | Analytical panel titles |
| **Metric Figure** | `DM Mono` | 28px | 600 | -0.5px | Numerical telemetry with tabular lining |
| **Status Chip** | `DM Mono` | 10px | 600 | +0.4px | State indicators and variances |
| **Body Narrative** | `DM Sans` | 13.5px| 400 | Normal | Executive summaries and reasoning |
| **Fine Print / Footers**| `DM Mono` | 11px | 400 | Normal | Audit notes and legal disclaimers |

---

## 4. First Viewport ("The 2-Second Comprehension Test")

The top of the dashboard is designed so a manufacturing planner understands the entire operational situation in under 2 seconds:
1. **Incident Header**:
   - Status chip: `SUPPLIER OUTAGE DETECTED · EVENT #DISRUPT-SUP-01` with pulsing red dot.
   - Title: `Primary Supplier SUP-01 Offline · Facility Shutdown Active`.
   - Clear operational summary: Tier-1 primary sourcing halted. On-hand inventory of 175 units sustains production through Day 2. Alternate vendor SUP-02 (4-day transit lead time) activated; an unavoidable 2-day pipeline stockout occurs on Days 3–4 before recovery begins on Day 5.
   - **Segmented Scenario Control**: Custom segmented buttons (`3 Days`, `7 Days`, `10 Days`, `14 Days`) replace generic browser dropdowns.
   - **Primary Action**: Single warm-orange button `[Review Recovery Plan ↓]` that smoothly guides the user to the recovery action docket.
2. **Executive Telemetry Ribbon (KPI Quartet)**:
   - Formatted as an integrated 4-column instrument strip with micro-progress gauges:
     - **Service Fill Rate**: `85.42%` (Target: 95.0%, with fill gauge)
     - **Unmet Demand**: `245 units` (14.6% Deficit, transit pipeline lag)
     - **Total Landed Cost**: `₹16,470` (`₹52.00 / u avg`, includes ₹2,490 expedited freight premium)
     - **Sustained Recovery**: `Day 10` (Sustained $\ge 95\%$ for 3 consecutive days)

---

## 5. Analytical Narrative Below the Fold

1. **Daily Demand Fulfillment Timeline**:
   - Clean slate (`#cbd5e1`) and crimson (`#ef4444`) bars replace bright template cyan.
   - Disruption window marker (`Days 1 to {shutdownDays}`).
   - Tooltip displays fulfilled receipts, unmet backlog, and landed cost breakdown.
2. **3-Phase Disruption Pipeline (Syncause Diagnostics)**:
   - Phase 1: `Runway Buffer (Days 1–2)` — 175 units opening stock fulfills 100% of demand for 2.18 days.
   - Phase 2: `Transit Gap (Days 3–4)` — SUP-02 4-day transit lag creates an unavoidable void before Day 5 receipts.
   - Phase 3: `Full Stabilization (Days 5–10)` — SUP-02 supplies 60u/d on Days 5–9; SUP-01 reopens Day 8 and arrives Day 10.
3. **Supply Network Topology**:
   - Schematic physical flow from Tier-1 Suppliers (`SUP-01 Offline`, `SUP-02 Backup`) → Assembly Plants (`FAC-01`, `FAC-02`) → Distribution Centers (`DC-01 Priority 1`, `DC-02 Priority 2`).
4. **Recovery Decision & Governance Docket**:
   - Clear trade-off matrix: Sourcing shift to SUP-02, Priority 1 protected at 91.5%, freight impact +₹2,490.
   - 4 deterministic guardrails verified by OR-Tools.
   - Interactive human approval with session authorization state (`#AUTH-SS-2026`).
5. **Strategy Showdown Comparative Matrix**:
   - Unified comparative matrix showing Reorder Rules vs Optimization-Only vs Agent-Assisted Recovery.
   - Proves the key differentiator: Agent-Assisted delivers **91.53% fill rate on critical Component A** vs 85.19% under uniform optimization.
6. **Multi-Agent Intelligence Console**:
   - 2x2 grid representing Demand Intelligence, Inventory Analyst, Supplier Risk, and Logistics Planner with live backend proposal data.
