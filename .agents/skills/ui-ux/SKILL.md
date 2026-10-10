---
name: ui-ux
description: Comprehensive UI/UX engineering skill for web applications. Provides guidelines for curated design tokens, dark control-tower styling, accessible typography scales, responsive layouts, micro-animations, and visual excellence.
---

# UI/UX Engineering Skill

This skill provides modern, high-craft UI/UX design standards for front-end web applications, dashboards, and control towers.

## 1. Design Principles

- **Visual Hierarchy**: Guide user attention with clear contrast, typographic scale, and deliberate spatial grouping.
- **Dark Control-Tower Aesthetics**:
  - Background palette: Deep slate/black (`#080c14`, `#0b111d`, `#101724`).
  - Panel borders: Subtle slate borders (`#1e293b`, `#253145`) with 1px thickness.
  - Accent colors: Purpose-driven semantic accents (Cyan `#55d7ed`, Emerald `#56d6a1`, Amber `#f3b85b`, Coral `#ff6c78`).
  - Avoid generic pure primaries (`#ff0000`, `#00ff00`, `#0000ff`).
- **Typography**:
  - Headings: Geometric or modern grotesque (e.g. `Space Grotesk`, `Outfit`, `Inter`).
  - Data / Metrics: Monospace font (e.g. `DM Mono`, `JetBrains Mono`) with `tabular-nums` for numerical clarity.
  - Body: High-legibility sans-serif (`DM Sans`, `Inter`).
- **Micro-Animations & Feedback**:
  - Smooth transitions (`transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1)`).
  - Hover glows on interactive elements.
  - Visible active/pending/disabled states.

## 2. Component Best Practices

- **KPI Cards**:
  - Display label, primary value, trend badge, and explanatory subtitle.
  - Format numbers with appropriate locale grouping (e.g., thousands separators, percentages, currency symbols).
- **Data Visualizations**:
  - Tooltips with high-contrast containers and legible typography.
  - Legend bars with distinct color dots.
  - Reference lines for key thresholds (e.g., target service levels, capacity limits).
- **Forms & Controls**:
  - Explicit labels and focus rings (`outline: 2px solid var(--accent); outline-offset: 3px`).
  - Loading indicators on submission buttons to prevent double-clicks.
