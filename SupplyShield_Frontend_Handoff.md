# SupplyShield AI — Frontend Handoff & Build Plan

**For:** UI/UX designer + frontend developer joining the hackathon build  
**Goal:** Rebuild the frontend around strong information architecture, fast comprehension, trustworthy decision support, and a working API integration.  
**Deadline context:** Hackathon submission is time-constrained. Prioritize a coherent, production-looking core flow over extra screens or decorative effects.  
**Local reference:** `SupplyShield_UX_Reference.html` is a clickable, static UX reference. The provided original `SupplyShield (1).html` is useful for screen ideas, but it contains disconnected mock values and fake interactions.  

---

## 1. Project in plain English

SupplyShield AI is an **AI-agent-assisted supply-chain resilience decision-support simulator**. It helps a planner understand the consequences of a supplier shutdown, compare recovery options, inspect why a plan was recommended, and make an informed decision.

The system is not an ERP and does not make real purchases. It simulates a disruption and evaluates recovery plans under explicit modeled constraints. Its job is to make the planner's decision clearer—not to pretend a recommendation is an order that has already been approved or sent.

### Main demonstration scenario

- Primary supplier: `SUP-01`.
- Alternate supplier: `SUP-02`.
- Supported shutdown duration: 1–14 days.
- Planning horizon: 21 days.
- Seed: 42.
- Product demand: `PROD-01` = 45 units/day; `PROD-02` = 35 units/day; total = 80 units/day.
- Total demand over 21 days: 1,680 units (`PROD-01` 945; `PROD-02` 735).
- Supplier lead times: `SUP-01` = 2 days; `SUP-02` = 4 days.
- Landed unit costs: `SUP-01` = ₹12.00; `SUP-02` = ₹16.50.
- The alternate supplier has a modeled capacity of 60 units/day.
- Unmet demand uses a **lost-service convention**: each day's unfulfilled demand contributes to period-level unmet demand; it is not a rolling backlog queue.
- Factory capacity and DC topology are currently structural metadata. Downstream factory/DC transfer constraints are not enforced.
- Workflow governance: the coordinator selects a plan for review; planner approval is separate; external execution is disabled. No real PO is dispatched.

### D=7 reference snapshot

Use these as regression/illustration values only. In the application, fetch values from the running backend instead of hardcoding them.

| Strategy | Feasible/selectable | Aggregate fill | PROD-01 fill | PROD-02 fill | Unmet demand | Landed cost | Recovery day | Score |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Agent-assisted | Yes | 85.42% | 91.53% (865/945) | 77.55% (570/735) | 245 | ₹16,470 | 10 | 13,379.57 |
| OR-Tools optimized | Yes | 85.42% | 85.19% (805/945) | 85.71% (630/735) | 245 | ₹16,470 | 10 | 12,744.65 |
| Reorder baseline | **No — benchmark only** | 65.48% | 67.72% (640/945) | 62.59% (460/735) | 580 | ₹12,060 | 11 | Not ranked |

The reorder baseline is deliberately retained as a comparison case, but its order attempts violate the shutdown blackout rule. It must never be represented as a feasible/selectable plan. Do not present its lower modeled cost as though it were an equally viable option.

### Other reference scenarios

| Shutdown | Selected agent fill | Unmet | Landed cost | Recovery day | PROD-01 fill | PROD-02 fill |
|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 96.13% | 65 | ₹17,280 | 4 | 96.30% | 95.92% |
| 7 days | 85.42% | 245 | ₹16,470 | 10 | 91.53% | 77.55% |
| 14 days | 77.08% | 385 | ₹16,680 | 17 | 91.53% | 58.50% |

These are saved reference snapshots, not live data. The previous HTML contains conflicting made-up product names, supplier quotes, outages, costs and fill rates; do not port those claims into production.

---

## 2. The UX problem we are solving

A first-time evaluator should understand within **10 seconds**:

1. What happened? A critical supplier is unavailable for a configured period.
2. What is at risk? Product demand can go unmet while stock and inbound replenishment are constrained.
3. What did SupplyShield conclude? It compares strategies and selects a feasible candidate for planner review.
4. Why that candidate? Its metrics, product priority trade-off, validation results, and score should be inspectable.
5. What happens next? A human reviews the plan. The system does not send an order.

The UI must answer those questions in that order. Do not open with a wall of agent logs, generic AI branding, a giant decorative graphic, or ten equally prominent charts.

### Product experience principles

- **Cause → impact → options → evidence → decision.** Keep this story clear across pages.
- **Show comparisons, not isolated KPIs.** A fill rate without product-level allocation, cost, scenario, and feasibility is insufficient.
- **Recommendation is not approval.** Selected, approved, and executed are separate states.
- **Be honest about the model.** A `NOT_MODELED` check is never a green PASS.
- **No fake real-world activity.** Do not invent RFQs, vendor certifications, supplier acknowledgements, ERP purchase-order IDs, live timers, or approval records.
- **The API owns the numbers.** React state should hold user input and returned results—not a duplicate simulation engine.
- **Progressive disclosure.** Lead with a readable summary. Details are available through inspect panels, accordions, tables, and a decision trace.
- **Resilient layouts.** The recovery decision table and validation evidence should remain usable at laptop and tablet widths, with deliberate mobile behavior.

---

## 3. Existing backend and frontend contract

Repository structure:

```text
supplyshield-ai/
├── backend/
│   ├── main.py
│   ├── schemas.py
│   ├── simulator.py
│   ├── optimizer.py
│   ├── coordinator.py
│   ├── agents/
│   ├── test_*.py
│   └── verify_smoke.py
└── frontend/
    ├── src/
    │   ├── api/client.ts
    │   ├── types/index.ts
    │   ├── components/...
    │   └── ...
    ├── package.json
    └── vite.config.ts
```

### Existing backend routes to inspect first

- `GET /health`
- `GET /api/network`
- `GET /api/simulate?shutdown_days=7&mode=agent`
- `GET /api/optimize?shutdown_days=7`
- `GET /api/recovery?shutdown_days=7`
- `GET /api/compare?shutdown_days=7`
- `GET /openapi.json` for the actual published request/response contracts.

The strategy IDs currently used are `reorder`, `optimized`, and `agent`. The `/api/simulate` endpoint supports `mode` and the legacy alias `recovery_mode`; if both are supplied and conflict, the API returns 422.

Scenario IDs have the form `SCEN-SD{days}-H21-S42`, e.g. `SCEN-SD7-H21-S42`.

### API integration rules

1. **Read the actual OpenAPI schema and `frontend/src/api/client.ts` before changing types or routes.** These notes describe the known interface; current code is authoritative.
2. Reuse the existing API client. Do not scatter raw `fetch()` calls across components.
3. Do not rename backend fields or make frontend types more permissive just to suppress TypeScript errors.
4. Add or update typed API methods and shared TypeScript response types only when the real endpoint supports them.
5. Show loading, empty, and error states. A failed request must not silently show old mock values as though they are current.
6. If using mock data for visual development, gate it behind a clear, visible `Demo data` indicator and never fall back silently after API failure.
7. Do not derive one returned KPI from another rounded display KPI if the backend provides authoritative fields.
8. Keep scenario identity (`scenario_id`, `shutdown_days`, `horizon_days`, `seed`) together in scenario-aware sections.

### Phase B6 coordination

The backend work may add structured decision traces, validation reports, an optional demo planner approval workflow, diagnostics, and an explicit non-configured execution-adapter state. Before building those UI pieces, inspect the **actual current** `/openapi.json`, `backend/schemas.py`, and existing backend endpoints.

Do not invent a planned approval or trace endpoint. If B6 endpoints are not present yet, build the page layout in a feature branch using clearly labelled presentation fixtures, but do not pretend the action is live. Coordinate with the backend owner before the final API hookup.

---

## 4. Page architecture and expected user journeys

Keep a consistent app shell: primary navigation, current scenario identity, API/system status, and a predictable page heading. Navigation should work with mouse, keyboard, and narrow widths.

### 4.1 Command center — default landing page

**Job:** Explain the disruption and guide the user to the next best action.

Recommended layout:

1. Page heading + current scenario badge.
2. One clear incident/decision hero: supplier affected, shutdown duration, planner status, primary CTA `Review recovery plan`, secondary CTA `Inspect supply network`.
3. Four compact KPIs: aggregate fill rate, unmet units, landed cost for the selected feasible candidate, recovery day.
4. Product impact panel with PROD-01 and PROD-02 fulfilled/demand counts, fill rates, and difference in service.
5. Recommended next steps / decision state.
6. Compact strategy snapshot table to compare the recommendation against the uniform optimizer and reorder baseline.
7. Small assumptions note and `last updated`/snapshot state based on actual response data.

**Avoid:** invented countdowns, “18 hours until halt” without a backend field, unverified stockout times, fake penalty savings, made-up company/customer names, or unsupported live-system health labels.

### 4.2 Scenario lab

**Job:** Let the user change shutdown duration, run the scenario, and compare outcomes.

- Input must use the supported 1–14 range; fixed model horizon and seed should be shown as context, not incorrectly treated as editable if they are not supported.
- Strong primary action: `Run scenario` or an explicitly documented auto-run after a user changes the input. Do not make it unclear whether a recalculation has happened.
- On run: loading state, disable duplicate submissions, preserve the prior result only if it is visibly labelled as previous/stale, then update all metrics and the scenario ID atomically.
- Show a simple impact summary, product-level details, and clear before/after comparisons where the API response supports them.
- Distinguish saved reference scenario from a newly calculated result.
- Provide reset to baseline, but do not accidentally trigger multiple requests from one interaction.

### 4.3 Supply network

**Job:** Make the dependency chain legible and explain how an upstream outage propagates.

- Render Suppliers → Factories → Distribution Centers in a simple left-to-right layout on large screens.
- On smaller screens, stack the tiers; do not rely on fragile SVG edge positions or color alone to explain dependencies.
- Selecting a node should update a contextual detail panel, not navigate away unexpectedly.
- Distinguish topology metadata from enforced constraints.
- Make the disrupted primary supplier and constrained alternate supplier immediately scannable.
- Use `/api/network` as the initial data source; scenario-dependent availability must be derived from the correct scenario response rather than permanently hardcoded labels.

### 4.4 Supplier capacity / sourcing context

This can be a compact screen or a section within Supply Network. Do not invest in a fake live RFQ platform for this hackathon build.

Use only available supplier attributes: modeled capacity, lead time, landed unit cost, blackout/availability under the active scenario, and the evaluated plan's actual supplier allocations if returned. Any commercial offer, certification, quote validity, availability poll, vendor reputation, or shipment timing needs real traced data before it can be presented as a fact.

### 4.5 Recovery workspace — highest priority screen

**Job:** Compare plans and show why a recommendation is safe to review.

Recommended layout:

1. Current scenario + explicit `Selected · awaiting planner review` state.
2. Candidate comparison cards or table with feasible/selectable state, aggregate fill, product-level fill, unmet units, landed cost, recovery day, ranking score, rank.
3. Recommendation detail / order schedule for the selected candidate.
4. Validation report with named checks and status (`PASS`, `FAIL`, `NOT_MODELED`).
5. Agent evidence and/or decision trace in a readable chronological panel.
6. A concise “why this plan” explanation, including priority trade-offs.
7. Governance panel: planner approval required, approved/not approved, execution not configured.

Rules:
- The reorder candidate is a benchmark only when the backend says it is infeasible. It must not expose a selectable/approve action.
- Use backend feasibility, ranking, and selection as the source of truth.
- Candidate and ranking metrics must match. Never recompute score using rounded UI percentages.
- Never mark all checks green if the API reports a limitation.
- Approval controls are allowed only when the explicit backend demo-approval API is available, enabled, and validates the exact scenario and plan fingerprint. Otherwise show a non-interactive boundary explanation.
- Approval does not mean execution.

### 4.6 Strategy benchmark

**Job:** Let judges see the value of agent-assisted strategy relative to alternatives.

- Run all strategies under identical scenario context.
- Display feasibility alongside performance; a lower-cost infeasible plan must not appear to win.
- Show aggregate fill and product-specific fill together.
- Show unmet demand, landed cost, recovery day, and relevant score/status.
- A clean table is more valuable than a fancy chart that obscures the data. Add a simple chart only if it communicates an actual API-returned daily series accurately.
- Use `/api/compare` or the supported existing endpoints. Do not recreate simulation behavior in client code.

---

## 5. Layout and interaction guidelines

Ignore specific brand colors initially. Get hierarchy, spacing, and behavior right before theming.

- Use a consistent 12-column or simple CSS grid layout. Content should have a comfortable maximum width and must not stretch tables/text to unreasonable widths on ultrawide screens.
- Use a persistent sidebar on desktop and a compact horizontal navigation pattern on smaller widths.
- Keep a clear top-level scenario context visible across pages.
- Give each page one obvious primary action. Secondary actions should be visually quieter.
- Use cards for grouped information, not every single label or row.
- Keep KPI labels unambiguous: `Aggregate fill rate`, `Unmet demand`, `Landed cost`, `Recovery day`.
- Use consistent units and number formatting: percent, units, ₹. Use `tabular-nums` for numeric alignment.
- Show denominator information when percentages are decision-relevant (e.g. 865 / 945).
- Put the detail close to the summary metric it explains.
- Use tables for candidate comparisons where a row-wise scan is faster than cards. On mobile, use horizontally scrollable tables with meaningful first-column context or transform them into stacked candidate cards.
- Use status text and icons in addition to color. Do not encode feasible/infeasible state by color alone.
- Avoid large animations, glowing AI effects, decorative 3D assets, gradient-heavy backgrounds, and irrelevant glassmorphism. Use restrained motion and honor `prefers-reduced-motion`.
- Every button must have a working action or be visibly disabled with an explanation. Never leave a button as decoration.
- Destructive/reject actions need deliberate wording and a confirmation if their effect is non-obvious.
- Show success only after the server responds successfully. Show failed fetch / HTTP error / schema error states in the UI.

### Responsive targets

Test at minimum:
- 1440 × 900 (primary desktop)
- 1280 × 800 (common laptop)
- 1024 × 768 (tablet / small laptop)
- 768 × 1024 (tablet portrait)
- 390 × 844 (mobile)

Check that the active navigation is obvious, page heading and CTA remain visible, KPI grids reflow, the network view remains understandable, candidate comparisons are usable, and no accidental page-wide horizontal scrolling occurs.

### Accessibility minimum

- Use semantic `nav`, `main`, `header`, headings, buttons, inputs, tables, and labels.
- Keyboard-visible focus state.
- Meaningful button labels; no clickable `div` when a button is appropriate.
- Correct `aria-current` for navigation and `aria-pressed` for toggles.
- Informative loading/error status with `aria-live` where useful.
- Do not convey status through color alone.
- Respect reduced-motion settings and preserve reasonable text contrast.

---

## 6. Phase-by-phase implementation plan

Do the phases in sequence. After each phase, summarize files changed, verify the build, and commit only coherent working increments. Do not spend time perfecting low-priority animation before the core workflow works.

### Phase 0 — Repository orientation and contract verification

1. Read `README.md`, `frontend/package.json`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, the current app shell/navigation, and current recovery components.
2. Open `http://127.0.0.1:8000/openapi.json` or inspect the generated OpenAPI if the backend is running.
3. List the routes and exact fields the frontend uses. Identify any B6 additions already implemented by the backend.
4. Open `SupplyShield_UX_Reference.html` and use it for page composition only; compare against the real response fields before using any data.
5. Record the current frontend baseline: dev-server startup, `npm run build`, existing lint/test commands, any failures.

**Exit gate:** You can explain which API powers every visible metric and which page elements are not supported yet.

### Phase 1 — Setup, Git branch, and a safe working environment

On the teammate's machine, clone the approved repository URL or open the already-cloned repo provided by the project owner. Do not create a second unrelated repository.

Example PowerShell setup:

```powershell
git status --short
git pull --ff-only
git switch -c feat/frontend-ux
cd frontend
npm install
npm run build
npm run dev
```

In a separate terminal, use the existing backend setup instructions from README. If a local Windows virtual environment is already provided:

```powershell
cd ..\backend
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m compileall .
```

Do not overwrite `.env` or paste secrets into chat. If a new `.env.local` is needed, follow the existing environment example and keep it untracked. Confirm the frontend API base URL uses the established `VITE_API_URL` mechanism, with the expected local fallback documented by the project.

**Exit gate:** Frontend can run, backend can run, baseline tests/build are recorded, and work is on a feature branch—not a direct edit to `main`.

### Phase 2 — UX map and design skeleton

Before styling details, map the main user journey on paper or in the HTML prototype:

`Command center → inspect scenario → compare candidates → inspect validation/evidence → planner boundary`

Create the shared page shell and navigation. Define reusable patterns for:
- Page heading and scenario identity
- KPI tile
- Status/state label
- Data panel/card
- Metric table
- Candidate card/table row
- Validation check row
- Decision trace event
- Loading, empty, error, and stale-data states

Choose a visual theme after the hierarchy works. The prototype's current colors are not mandatory.

**Exit gate:** All main pages are reachable through navigation, the hierarchy reads well with placeholder fixtures, and the layout does not overflow at laptop width.

### Phase 3 — API client and typed data wiring

1. Make the existing typed API client the only place components invoke backend routes.
2. Ensure errors preserve status and a user-readable message without leaking internal exception details.
3. Add a central scenario state (`shutdown_days`, `horizon_days`, `seed`, `scenario_id`) populated from responses.
4. Build request/loading/error/result state patterns.
5. Remove duplicated or conflicting mock data from screen components.
6. Keep fixtures only where intentionally useful, clearly labelled and isolated from the real API path.

**Exit gate:** Network, simulation, recovery, and comparison data are loaded from the backend; changing scenario updates the active context from actual API responses.

### Phase 4 — Command center

Build the landing screen first. It must explain the event, impact, selected plan, and next action in one view. Use live response values for the metrics and product breakdown. Do not add a made-up countdown or customer penalty savings.

**Exit gate:** A judge who hasn't seen the project can tell what is disrupted, what the impact is, which plan is recommended, and where to inspect its evidence within 10 seconds.

### Phase 5 — Scenario lab and supply network

Implement scenario selection and run behavior from the actual supported input contract. Present the supply network using actual topology. Use a right-side/context panel or a responsive details drawer for node inspection.

**Exit gate:** All supported shutdown durations are validated, scenario IDs stay in sync, and the network remains understandable at tablet/mobile widths.

### Phase 6 — Recovery workspace and strategy benchmark

Recovery workspace is the highest-value page. Display candidate status, metrics, validation, ranking, and selection from `/api/recovery`. Use `/api/compare` or the actual supported equivalent for strategy comparison. Keep the selected candidate and scenario consistent across page transitions.

If B6 provides typed decision trace, validation report, diagnostics, or demo approval, integrate only the exact published fields. Make an approval request only when the backend says the feature is enabled. No frontend-only approval state.

**Exit gate:** An infeasible plan cannot be selected, the recommended candidate details match the API, and the UI clearly shows `approved = false` and `external_execution = false` until an actual supported server response says otherwise.

### Phase 7 — Supplier capacity, responsive polish, and accessibility

Use only the model's supplier data and constraints. Add responsive refinements, input validation, semantic HTML, keyboard focus, accessible status labels, empty/error states, and reduced motion. Remove any dead button or placeholder interaction.

**Exit gate:** The main user journey works from mouse and keyboard; narrow layouts remain usable; no unsupported vendor or execution claims remain.

### Phase 8 — End-to-end verification and visual QA

Run from `frontend/`:

```powershell
npm run build
```

Also run whatever existing lint, type-check, or test scripts exist in `package.json`. Do not invent a script name—inspect `package.json` first.

Run the backend test suite from `backend/` if any contract integration changes were needed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe verify_smoke.py
```

Manual test list:

- All six navigation destinations open correctly.
- Scenario duration updates result and scenario identity together.
- Failed API requests show an honest error and do not quietly display stale demo numbers.
- Refresh/re-run cannot create overlapping accidental requests.
- Product-level fill, aggregate fill, unmet demand, cost, recovery, rank, and feasibility agree with API data.
- Reorder benchmark never gets a Select or Approve action if infeasible.
- Approval controls are hidden/disabled if demo approval is not enabled.
- Approval does not change external execution state.
- No `Send Orders` action exists.
- Keyboard navigation, focus, narrow widths, and reduced-motion settings are checked.

Use the browser to check at least 1440×900, 1280×800, 768×1024 and 390×844. If possible, capture screenshots of Command center and Recovery workspace for review.

**Exit gate:** Clean build, no console errors during the core flow, no obvious overflow, and verified server-truth states.

### Phase 9 — Git commit, push, and handoff

Before committing:

```powershell
git status --short
git diff --check
git diff --stat
```

Check that `.env`, `.env.local`, `.venv`, `node_modules`, `dist`, logs, local approval ledgers, personal test data, and generated artifacts are not staged. Check `.gitignore`; do not stage everything blindly.

Commit by coherent milestone, for example:

```powershell
git add frontend/src
# Add only the specific intended frontend docs/assets, if any.
git commit -m "feat(frontend): build supply chain decision workspace"
git push -u origin feat/frontend-ux
```

If additional HTML reference/documentation belongs in the repository, ask the owner first or include only the agreed files. Do not force-push. Open a pull request into the agreed integration branch and summarize:
- Pages and interactions implemented
- API routes wired
- What remains deliberately disabled/not modeled
- Commands run and their results
- Screenshots or short walkthrough
- Any new environment variables

Do not merge over simultaneous backend changes without the repo owner's review. If another teammate is editing the same frontend branch/files, pause and coordinate rather than overwriting their work.

**Exit gate:** Code is pushed on the agreed feature branch, build/test evidence is available, and the project owner can review and integrate it.

---

## 7. Git collaboration rules

- Frontend ownership belongs to the UI/UX + frontend teammate, but backend API/schema ownership remains with the backend owner unless explicitly coordinated.
- Do not change backend calculation logic or API schemas just to make the UI convenient.
- If a required field is missing, raise the exact request and proposed schema to the backend owner. Do not fill it with a guessed constant.
- Keep PRs small enough to review. Avoid simultaneous direct edits to the same frontend files.
- Don't commit to `main` from an individual feature branch; push the branch and request review.
- Never commit secrets or private ledger entries.
- Keep `SupplyShield_UX_Reference.html` a visual reference, not the source of app state.

---

## 8. Definition of done

The frontend is done for hackathon submission when:

- A first-time evaluator understands the product in under 10 seconds.
- The Command Center's metrics are sourced from the actual backend.
- Scenario changes update results and scenario identity coherently.
- The network view explains the dependency path without overstating modeled constraints.
- Recovery workspace clearly distinguishes feasible candidates from the infeasible baseline.
- Benchmark comparison exposes aggregate and product-level trade-offs.
- Decision trace and validation states are truthful wherever implemented by the backend.
- `selected`, `approved`, and `executed` are never conflated.
- No fake live vendor offers, fake approval, fake ERP dispatch, or fake success states exist.
- All key pages work at desktop/tablet/mobile widths and use accessible interaction semantics.
- Production build passes; regression checks pass for any affected contracts.
- Changes are committed and pushed to a reviewable feature branch with a concise handoff.

**Priority order if time becomes critical:**

1. Command Center + Recovery Workspace working with real API data.
2. Strategy Benchmark working with real API data.
3. Scenario Lab with correct input/loading/error behavior.
4. Supply Network details.
5. Supplier capacity context.
6. Additional animation and decorative polish (only after the above).
