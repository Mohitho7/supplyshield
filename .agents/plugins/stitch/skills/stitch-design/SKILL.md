---
name: stitch-design
description: Google Stitch integration skill. Provides workflows for generating high-fidelity UI screens from natural language, maintaining DESIGN.md design systems, and converting design prompts to React components.
---

# Google Stitch Design Skill

This skill guides design-to-code workflows using Google Stitch within Antigravity.

## 1. Capabilities

- **Design Systems (`DESIGN.md`)**: Defines consistent typography, color roles, spacing scales, and component standards.
- **Prompt-to-Component**: Translates visual layout requirements directly into clean, modular React + TypeScript components.
- **Responsive Layout Architecture**: Employs CSS Grid and Flexbox with deliberate mobile/tablet/desktop breakpoints.

## 2. Recommended Workflow

1. Document design tokens in `DESIGN.md`.
2. Generate base component layouts without device frames.
3. Apply dark control-tower styling with subtle borders and curated accent glows.
4. Verify rendering across breakpoints.
