# SupplyShield AI — Supply Chain Resilience Control Tower

SupplyShield AI is an agentic supply-chain resilience simulator and decision-support control tower. It evaluates multi-echelon network disruption scenarios, generates auditable contingency recovery plans, and preserves human-in-the-loop approval governance.

---

## 1. Data Layer Architecture & Foundation

The SupplyShield AI Data Layer separates supply chain master data, topological definitions, inventory balances, and demand profiles from application logic. It replaces scattered hardcoded constants with a structured, versioned, relational data repository backed by rigorous Pydantic V2 validation and cryptographic fingerprinting.

### 1.1 Dataset Directory Structure

Canonical datasets reside in `backend/datasets/<dataset_id>/`. The active default dataset is `demo_v1`:

```
backend/datasets/demo_v1/
├── dataset_manifest.json       # Metadata, semantic version, schema version, limitations, file mapping
├── suppliers.json              # Master records: SUP-01 (Primary) and SUP-02 (Contingency)
├── products.json               # Product catalog: PROD-01 (Critical Tier 1) and PROD-02 (Tier 2)
├── network.json                # Topology nodes (suppliers, factories, DCs) and directed edges
├── inventory.json              # Day 1 opening on-hand inventory balances
├── demand_profiles.json        # Deterministic 21-day customer demand curves (lost-service convention)
├── scenarios.json              # Supported planning horizon (21d), seed (42), fill target (95%), shutdown bounds
└── cost_config.json            # Unit procurement, freight, and landed cost definitions in INR
```

---

## 2. Canonical Data Models & Contracts

### 2.1 Supplier Master Data
- **SUP-01 (Primary Components):**
  - Daily capacity: 100 units/day
  - Lead time: 2 days
  - Unit procurement cost: ₹10.00 | Freight: ₹2.00 | Total landed cost: ₹12.00
  - Disruption subject: True (offline during days 1..shutdown_days)
- **SUP-02 (Alternate Components):**
  - Daily capacity: 60 units/day (strictly enforced shared capacity limit)
  - Lead time: 4 days
  - Unit procurement cost: ₹13.00 | Freight: ₹3.50 | Total landed cost: ₹16.50
  - Disruption subject: False

### 2.2 Product Catalog & Inventory
- **PROD-01 (Essential Component A):**
  - Priority: 1 (Critical Tier)
  - Initial inventory: 100 units (Day 1)
  - Daily demand: 45 units/day (Horizon demand: 945 units)
- **PROD-02 (Essential Component B):**
  - Priority: 2 (High Tier)
  - Initial inventory: 75 units (Day 1)
  - Daily demand: 35 units/day (Horizon demand: 735 units)
- **Total Horizon Demand:** 1,680 units across 21 days.

### 2.3 Network Topology
- **Suppliers:** SUP-01, SUP-02
- **Assembly Factories:** FAC-01 (Factory North), FAC-02 (Factory South)
- **Distribution Centers:** DC-01 (North DC), DC-02 (South DC)
- **Directed Routes:** 6 inbound material and finished goods transport edges.

---

## 3. Validation Pipeline & Integrity Checks

Every dataset is loaded through `validate_and_load_dataset()` in `backend/data_repository.py`. The validation pipeline executes the following checks:

1. **Schema Validation:** Strict Pydantic V2 parsing with non-negativity constraints (`ge=0` on costs/inventory, `ge=1` on capacity/lead time).
2. **Duplicate Entity Detection:** Rejects duplicate supplier IDs, product SKUs, factory IDs, and DC IDs.
3. **Relational Referencing:**
   - Every product in `inventory.json` and `demand_profiles.json` must exist in `products.json`.
   - Every directed edge in `network.json` must connect existing topology nodes.
4. **Cost Accounting Reconciliation:** Verifies that for every supplier:
   $$\text{Procurement Cost} + \text{Freight Cost} = \text{Landed Cost}$$
5. **Scenario Horizon & Seed Bounds:** Horizon = 21 days, Seed = 42, Target fill rate = 95.0%.
6. **Data Provenance & Limitations:** Enforces presence of dataset manifest, semantic version, and explicit model limitations.

---

## 4. Cryptographic Dataset Fingerprint

A deterministic SHA-256 fingerprint is computed from canonical dataset content:
- Normalizes and sorts dictionary keys and entity lists by primary keys.
- **Invariance:** Harmless JSON key reordering or whitespace changes do NOT change the fingerprint.
- **Sensitivity:** Material changes to costs, lead times, capacity, or inventory immediately change the fingerprint.
- **Plan Binding:** Differentiates between the dataset fingerprint (source data) and the plan fingerprint (specific candidate order schedule being approved).

Active Canonical Fingerprint (`demo_v1`):
`34f1ec303d9b1eb8dfc4c87bd70569021a60d11d690f4c09b1f626b56f246617`

---

## 5. Offline CLI Validation Tool

To validate a dataset offline before activating it:

```powershell
# From the backend/ directory:
.\.venv\Scripts\python.exe -m data_repository validate datasets\demo_v1
```

The CLI prints a structured badge report:
- `[PASS]` for all validated checks.
- `[NOT_MODELED]` for declared operational boundaries.
- Returns exit code `0` on success, or `1` on failure with actionable error messages.

---

## 6. How New Datasets Are Prepared and Activated

1. Create a new directory under `backend/datasets/<new_dataset_id>/`.
2. Populate the 8 canonical JSON files adhering to the schema.
3. Validate offline using `python -m data_repository validate datasets/<new_dataset_id>`.
4. To activate, set `ACTIVE_DATASET_ID = "<new_dataset_id>"` or pass the path to `get_active_dataset(dataset_dir)`.
5. The application loads once at startup and caches an immutable in-memory snapshot (`SupplyChainDataset`), preventing mid-execution state divergence.

---

## 7. Model Boundaries & `NOT_MODELED` Constraints

To maintain absolute transparency, the system explicitly reports modeled vs. unmodeled factors:

| Factor | Status | Details |
|---|---|---|
| Primary Supplier Outage | **MODELED & ENFORCED** | SUP-01 accepts zero orders during days 1..shutdown_days |
| Contingency Supplier Capacity | **MODELED & ENFORCED** | SUP-02 shared throughput strictly capped at 60 units/day |
| Transit Lead Times | **MODELED & ENFORCED** | Orders arrive strictly on $\text{Day} + \text{Lead Time}$ |
| Horizon Arrival Boundary | **MODELED & ENFORCED** | Orders arriving after Day 21 do not contribute to in-horizon receipts; spend remains committed |
| Customer Demand Model | **LOST SERVICE** | Unfulfilled daily demand is period-specific unmet service; no backlog queue |
| Factory Assembly Capacity | `NOT_MODELED` | Factory nodes exist in topology, but assembly throughput is unconstrained |
| DC Storage Limits | `NOT_MODELED` | DC nodes exist in topology, but storage capacity is unconstrained |
| Live ERP Order Dispatch | `NOT_CONFIGURED` | Null execution adapter; no live POs or financial transactions are dispatched |

---

## 8. API Endpoints

### 8.1 Data Status Endpoint
- **URL:** `GET /api/data/status`
- **Response:** `DataStatusResponse`
  - `dataset_id`: "demo_v1"
  - `dataset_version`: "1.0.0"
  - `dataset_fingerprint`: "34f1ec303d9b1eb8dfc4c87bd70569021a60d11d690f4c09b1f626b56f246617"
  - `source_type`: "synthetic_demo"
  - `is_synthetic`: true
  - `validation_status`: "VALID"
  - Entity counts (suppliers: 2, products: 2, nodes: 6, edges: 6)

### 8.2 Operational Diagnostics
- **URL:** `GET /api/diagnostics`
- Enriched with `dataset_id`, `dataset_version`, `dataset_fingerprint`, and `data_validation_status`.

---

## 9. Future Data Source Adapters

`data_repository.py` declares typed abstract adapter contracts:
- `DemoV1FileAdapter`: Active, file-backed canonical demo dataset adapter.
- `ErpSnapshotAdapter`: Future connector for ERP inventory and PO exports (`NOT_CONFIGURED`).
- `CsvBatchImportAdapter`: Future connector for batch CSV files (`NOT_CONFIGURED`).

No credentials, real observations, or live supplier integrations are active or configured in this phase.

---

## 10. Verification Suite

Run the full verification suite from `backend/`:

```powershell
# 1. Run all unit & regression tests (138 tests)
.\.venv\Scripts\python.exe -m unittest discover -v

# 2. Python bytecode compilation
.\.venv\Scripts\python.exe -m compileall .

# 3. Live HTTP smoke tests (53 checks against running FastAPI server)
.\.venv\Scripts\python.exe verify_smoke.py

# 4. Offline dataset validation CLI
.\.venv\Scripts\python.exe -m data_repository validate datasets\demo_v1
```

From `frontend/`:
```powershell
# Production build check
npm run build
```
