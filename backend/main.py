import contextvars
import json
import logging
import re
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Optional, Any, List

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from coordinator import coordinate_recovery
from optimizer import optimize_plan
from simulator import run_simulation, NETWORK, HORIZON
from approval import (
    record_approval,
    get_latest_approval,
    read_approval_records,
    get_approval_records_count,
    is_approval_enabled,
)
from execution import get_execution_adapter
try:
    from data_repository import get_active_dataset, DataStatusResponse
except ImportError:
    from backend.data_repository import get_active_dataset, DataStatusResponse
from schemas import (
    HealthResponse,
    NetworkTopology,
    SimulationResponse,
    OptimizationResponse,
    RecoveryResponse,
    ComparisonResponse,
    ApprovalRequest,
    ApprovalRecord,
    ExecutionAdapterStatus,
    DiagnosticsResponse,
    DecisionTraceEvent,
)

logger = logging.getLogger("supplyshield.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")

CORRELATION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
current_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="internal")


def log_event(
    event_name: str,
    outcome: str,
    correlation_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    strategy_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    error_category: Optional[str] = None,
    **extra: Any,
) -> None:
    """
    Standardized structured JSON logger for operational workflow tracing.
    Guarantees no sensitive credentials, keys, or passwords are included.
    """
    cid = correlation_id or current_correlation_id.get()
    safe_cid = cid if isinstance(cid, str) else "internal"
    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_name": str(event_name),
        "correlation_id": safe_cid,
        "outcome": str(outcome),
    }
    if scenario_id and isinstance(scenario_id, str):
        entry["scenario_id"] = scenario_id
    if candidate_id and isinstance(candidate_id, str):
        entry["candidate_id"] = candidate_id
    if strategy_id and isinstance(strategy_id, str):
        entry["strategy_id"] = strategy_id
    if duration_ms is not None and isinstance(duration_ms, (int, float)):
        entry["duration_ms"] = duration_ms
    if error_category and isinstance(error_category, str):
        entry["error_category"] = error_category
    for k, v in extra.items():
        if v is not None and not any(s in k.lower() for s in ("secret", "token", "password", "key", "auth")):
            if isinstance(v, (str, int, float, bool, list, dict)):
                entry[k] = v
            else:
                entry[k] = str(v)
    try:
        logger.info(json.dumps(entry, separators=(",", ":")))
    except Exception:
        pass


app = FastAPI(
    title="SupplyShield AI",
    description=(
        "SupplyShield AI is an agentic supply chain resilience simulator and control tower API.\n\n"
        "### Operational Scope & Modeling Assumptions:\n"
        "- **Planning Horizon:** Fixed 21-day deterministic evaluation horizon.\n"
        "- **Supplier Disruption:** Evaluates primary supplier (SUP-01) shutdowns from 1 to 14 days.\n"
        "- **Demand Model:** Deterministic daily consumption (PROD-01: 45 u/day, PROD-02: 35 u/day).\n"
        "- **Service Level Accounting:** Lost-service convention (unmet daily demand is period-specific and not carried forward in a backlog queue).\n"
        "- **Cost Model:** Landed cost = Procurement unit cost + Freight unit cost (SUP-01 = ₹12.00/u, SUP-02 = ₹16.50/u).\n"
        "- **Decision Support Governance:** This system generates advisory decision-support recommendations. "
        "No live ERP purchase orders are executed, and human planner review is strictly required (`planner_approval_required=True`, `approved=False`).\n"
        "- **Topology Metadata:** Factory assembly throughput and DC storage are modeled as topological metadata; downstream multi-echelon transfer is unconstrained in the current supplier sourcing model."
    ),
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Validates or generates a correlation ID at the API boundary,
    attaches it to request state and contextvar, records structured request telemetry,
    and returns it via the X-Correlation-ID header.
    """
    raw_cid = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID")
    if raw_cid and CORRELATION_ID_REGEX.match(raw_cid.strip()):
        correlation_id = raw_cid.strip()
    else:
        correlation_id = str(uuid.uuid4())

    token = current_correlation_id.set(correlation_id)
    request.state.correlation_id = correlation_id
    start_time = time.perf_counter()

    log_event(
        event_name="REQUEST_RECEIVED",
        outcome="RECEIVED",
        path=request.url.path,
        method=request.method,
    )

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        log_event(
            event_name="REQUEST_COMPLETED",
            outcome="COMPLETED",
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        log_event(
            event_name="APPLICATION_ERROR",
            outcome="FAILED",
            path=request.url.path,
            duration_ms=duration_ms,
            error_category=type(exc).__name__,
        )
        raise
    finally:
        current_correlation_id.reset(token)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler for unexpected internal errors.
    Returns a safe, structured HTTP 500 error without exposing stack traces, filesystem paths, or internal secrets.
    """
    if isinstance(exc, (HTTPException, RequestValidationError)):
        raise exc
    req_path = getattr(getattr(request, "url", None), "path", "/unknown")
    if not isinstance(req_path, str):
        req_path = "/api/recovery"
    log_event(
        event_name="UNHANDLED_EXCEPTION",
        outcome="CRASH",
        error_category=type(exc).__name__,
        path=req_path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error occurred while processing the supply chain workflow. Please check server logs.",
            "path": req_path,
        },
    )


@app.get("/", tags=["System"])
def root():
    return {
        "app": "SupplyShield AI",
        "status": "running",
        "version": "0.6.0",
        "environment": "decision_support_simulation",
        "planner_approval_required": True,
        "approved": False,
        "external_execution": False,
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health & Liveness Probe",
    description="Returns service health status. Does not expose internal secrets or environment paths.",
)
def health():
    return HealthResponse(status="ok")


@app.get(
    "/api/network",
    response_model=NetworkTopology,
    tags=["Network"],
    summary="Supply Chain Network Topology",
    description=(
        "Returns the synthetic multi-echelon supply network configuration: 2 suppliers, 2 factories, "
        "2 distribution centers, and 2 products. Supplier capacities, lead times, and unit costs represent "
        "enforced replenishment constraints; factory and DC node properties represent topological structural metadata."
    ),
)
def get_network():
    return deepcopy(NETWORK)


from fastapi.params import Query as QueryParam


def _resolve_param(val: Any) -> Any:
    if isinstance(val, QueryParam):
        return val.default
    return val


def _validate_shutdown_days(days: Any) -> int:
    resolved = _resolve_param(days)
    if isinstance(resolved, bool) or not isinstance(resolved, int) or not (1 <= resolved <= 14):
        raise HTTPException(
            status_code=422,
            detail=f"shutdown_days must be an integer between 1 and 14, got {resolved!r}",
        )
    return resolved


@app.get(
    "/api/simulate",
    response_model=SimulationResponse,
    tags=["Simulation"],
    summary="Simulate Supply Chain Policy",
    description=(
        "Executes a deterministic 21-day simulation for the specified planning policy ('reorder', 'optimized', or 'agent') "
        "under a primary supplier shutdown of 1 to 14 days. Unmet demand is reported as lost service (not carried forward). "
        "Supports 'mode' and legacy 'recovery_mode' query parameters; if both are specified, they must agree or HTTP 422 is returned."
    ),
)
def simulate(
    shutdown_days: int = Query(
        default=7,
        ge=1,
        le=14,
        description="Duration in days of primary supplier (SUP-01) shutdown window (1 to 14 days)",
    ),
    mode: Optional[str] = Query(
        default=None,
        pattern="^(reorder|optimized|agent)$",
        description="Planning strategy mode: 'reorder', 'optimized', or 'agent'",
    ),
    recovery_mode: Optional[str] = Query(
        default=None,
        pattern="^(reorder|optimized|agent)$",
        description="Legacy alias for mode parameter: 'reorder', 'optimized', or 'agent'",
    ),
):
    shutdown_days = _validate_shutdown_days(shutdown_days)
    resolved_mode = _resolve_param(mode)
    resolved_rec_mode = _resolve_param(recovery_mode)

    # Resolve strategy mode with explicit conflict validation
    if resolved_mode is not None and resolved_rec_mode is not None:
        if resolved_mode != resolved_rec_mode:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Conflicting strategy modes specified: mode='{resolved_mode}' and recovery_mode='{resolved_rec_mode}'. "
                    "Please specify only one strategy mode or ensure both parameters match."
                ),
            )
        effective_mode = resolved_mode
    elif resolved_mode is not None:
        effective_mode = resolved_mode
    elif resolved_rec_mode is not None:
        effective_mode = resolved_rec_mode
    else:
        effective_mode = "agent"

    log_event(
        event_name="SIMULATION_EXECUTION_STARTED",
        outcome="RUNNING",
        strategy_id=effective_mode,
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )

    result = run_simulation(
        shutdown_days=shutdown_days,
        recovery_mode=effective_mode,
    )

    log_event(
        event_name="SIMULATION_COMPLETED",
        outcome="SUCCESS",
        strategy_id=effective_mode,
        fill_rate=result.get("metrics", {}).get("fill_rate"),
    )
    return result


@app.get(
    "/api/compare",
    response_model=ComparisonResponse,
    tags=["Benchmark"],
    summary="Compare Planning Strategies",
    description=(
        "Evaluates and compares all three distinct planning strategies ('reorder', 'optimized', and 'agent') "
        "under identical scenario conditions (same shutdown days, 21-day horizon, and seed). "
        "Preserves distinct policy mechanics and product allocations."
    ),
)
def compare_strategies(
    shutdown_days: int = Query(
        default=7,
        ge=1,
        le=14,
        description="Duration in days of primary supplier (SUP-01) shutdown window (1 to 14 days)",
    ),
):
    shutdown_days = _validate_shutdown_days(shutdown_days)

    log_event(
        event_name="COMPARISON_BENCHMARK_STARTED",
        outcome="RUNNING",
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )

    reorder_res = run_simulation(shutdown_days=shutdown_days, recovery_mode="reorder")
    optimized_res = run_simulation(shutdown_days=shutdown_days, recovery_mode="optimized")
    agent_res = run_simulation(shutdown_days=shutdown_days, recovery_mode="agent")

    log_event(
        event_name="COMPARISON_BENCHMARK_COMPLETED",
        outcome="SUCCESS",
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )

    return {
        "scenario": {
            "shutdown_days": shutdown_days,
            "horizon_days": HORIZON,
            "seed": 42,
            "scenario_id": f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
        },
        "strategies": {
            "reorder": reorder_res,
            "optimized": optimized_res,
            "agent": agent_res,
        },
    }


@app.get(
    "/api/optimize",
    response_model=OptimizationResponse,
    tags=["Optimization"],
    summary="Direct Mathematical Optimization",
    description=(
        "Executes direct OR-Tools CP-SAT multi-period optimization under a uniform shortage penalty. "
        "Minimizes total system procurement, freight, and shortage costs symmetrically. "
        "Optimizes supplier replenishment orders across the 21-day horizon."
    ),
)
def optimize(
    shutdown_days: int = Query(
        default=7,
        ge=1,
        le=14,
        description="Duration in days of primary supplier (SUP-01) shutdown window (1 to 14 days)",
    ),
):
    shutdown_days = _validate_shutdown_days(shutdown_days)

    log_event(
        event_name="OPTIMIZATION_STARTED",
        outcome="RUNNING",
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )

    result = optimize_plan(shutdown_days)

    log_event(
        event_name="OPTIMIZATION_COMPLETED",
        outcome=result.get("status", "SUCCESS"),
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )
    return result


@app.get(
    "/api/recovery",
    response_model=RecoveryResponse,
    tags=["Coordination"],
    summary="Multi-Agent Recovery Coordination",
    description=(
        "Executes the full SupplyShield AI recovery workflow: specialist agent assessments (Demand Intelligence, "
        "Inventory Analyst, Supplier Risk, Logistics Optimization), multi-candidate generation (Agent, Optimized, Reorder), "
        "deterministic constraint validation, metric-based candidate ranking, and auditable selection docket. "
        "Advisory decision support only: planner_approval_required=True, approved=False. No external purchase orders are dispatched."
    ),
)
def recovery(
    shutdown_days: int = Query(
        default=7,
        ge=1,
        le=14,
        description="Duration in days of primary supplier (SUP-01) shutdown window (1 to 14 days)",
    ),
):
    shutdown_days = _validate_shutdown_days(shutdown_days)

    log_event(
        event_name="RECOVERY_COORDINATION_STARTED",
        outcome="RUNNING",
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )

    result = coordinate_recovery(shutdown_days)

    log_event(
        event_name="RECOVERY_COORDINATION_COMPLETED",
        outcome="SUCCESS",
        scenario_id=result.get("scenario", {}).get("scenario_id"),
        candidate_id=result.get("selection", {}).get("selected_candidate_id"),
        workflow_state=result.get("workflow_state"),
    )
    return result


@app.post(
    "/api/approval",
    response_model=ApprovalRecord,
    status_code=201,
    tags=["Governance"],
    summary="Record Human Planner Decision",
    description=(
        "Explicit server-side approval or rejection of a recovery candidate. "
        "Validates candidate feasibility and cryptographic plan fingerprint. "
        "Persists decision to append-only JSONL ledger. "
        "Does NOT dispatch external purchase orders (demo workflow only)."
    ),
)
def submit_approval(request_body: ApprovalRequest):
    log_event(
        event_name="PLANNER_APPROVAL_REQUESTED",
        outcome="PENDING",
        scenario_id=request_body.scenario_id,
        candidate_id=request_body.candidate_id,
        action=request_body.action,
    )

    record, err, status_code = record_approval(request_body)
    if err or not record:
        log_event(
            event_name="PLANNER_APPROVAL_REJECTED",
            outcome="REJECTED",
            scenario_id=request_body.scenario_id,
            candidate_id=request_body.candidate_id,
            error_category="Validation" if status_code < 500 else "Storage",
            detail=err,
        )
        raise HTTPException(status_code=status_code, detail=err)

    log_event(
        event_name="APPROVAL_LEDGER_RECORD_COMPLETED",
        outcome="SAVED",
        scenario_id=record.scenario_id,
        candidate_id=record.candidate_id,
        record_id=record.record_id,
        workflow_state=record.workflow_state,
    )
    return record


@app.get(
    "/api/approval",
    tags=["Governance"],
    summary="Retrieve Demo Approval Records",
    description="Retrieves the latest demo approval record or records matching scenario and candidate.",
)
def get_approval(
    scenario_id: Optional[str] = Query(default=None, description="Scenario ID filter"),
    candidate_id: Optional[str] = Query(default=None, description="Candidate ID filter"),
    shutdown_days: Optional[int] = Query(default=None, ge=1, le=14, description="Shutdown days filter"),
):
    resolved_scenario_id = _resolve_param(scenario_id)
    resolved_candidate_id = _resolve_param(candidate_id)
    resolved_shutdown_days = _resolve_param(shutdown_days)

    if resolved_shutdown_days is not None:
        if isinstance(resolved_shutdown_days, bool) or not isinstance(resolved_shutdown_days, int) or not (1 <= resolved_shutdown_days <= 14):
            raise HTTPException(
                status_code=422,
                detail=f"shutdown_days must be an integer between 1 and 14, got {resolved_shutdown_days!r}",
            )
        if not resolved_scenario_id:
            resolved_scenario_id = f"SCEN-SD{resolved_shutdown_days}-H{HORIZON}-S42"

    if resolved_scenario_id and resolved_candidate_id:
        record = get_latest_approval(resolved_scenario_id, resolved_candidate_id)
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"No approval record found for scenario '{resolved_scenario_id}' and candidate '{resolved_candidate_id}'.",
            )
        return record

    records = read_approval_records()
    if resolved_scenario_id:
        records = [r for r in records if r.get("scenario_id") == resolved_scenario_id]
    if resolved_candidate_id:
        records = [r for r in records if r.get("candidate_id") == resolved_candidate_id]
    return records


@app.get(
    "/api/trace",
    response_model=List[DecisionTraceEvent],
    tags=["Coordination"],
    summary="Machine-Readable Decision Trace",
    description="Returns the 11-stage deterministic decision trace for the specified disruption scenario.",
)
def get_decision_trace(
    shutdown_days: int = Query(default=7, ge=1, le=14, description="Outage duration in days"),
):
    shutdown_days = _validate_shutdown_days(shutdown_days)

    log_event(
        event_name="DECISION_TRACE_REQUESTED",
        outcome="FETCHING",
        scenario_id=f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
    )

    recovery_result = coordinate_recovery(shutdown_days)
    trace = recovery_result.get("decision_trace") or []
    return trace


@app.get(
    "/api/execution/status",
    response_model=ExecutionAdapterStatus,
    tags=["Governance"],
    summary="Execution Adapter Status",
    description="Reports external execution integration status (NOT_CONFIGURED in current advisory model).",
)
def execution_status():
    adapter = get_execution_adapter()
    status = adapter.check_status()

    log_event(
        event_name="EXECUTION_ADAPTER_STATUS_CHECKED",
        outcome=status.status,
        adapter_name=status.adapter_name,
    )
    return status


@app.get(
    "/api/data/status",
    response_model=DataStatusResponse,
    tags=["System"],
    summary="Canonical Dataset Status & Data Quality",
    description="Returns public health, version, fingerprint, and validation status of the active supply chain dataset.",
)
def data_status():
    dataset = get_active_dataset()
    status_resp = dataset.to_data_status()

    log_event(
        event_name="DATA_STATUS_INSPECTED",
        outcome=status_resp.validation_status,
        dataset_id=status_resp.dataset_id,
        dataset_version=status_resp.dataset_version,
    )
    return status_resp


@app.get(
    "/api/diagnostics",
    response_model=DiagnosticsResponse,
    tags=["System"],
    summary="Operational Diagnostics & Readiness",
    description=(
        "Returns operational diagnostics, model parameters, solver availability, demo approval state, and active dataset provenance. "
        "Does not expose internal paths, secrets, or environment credentials."
    ),
)
def diagnostics():
    # Lightweight solver check: instantiate CpSolver
    solver_status = "unavailable"
    try:
        from ortools.sat.python import cp_model
        _ = cp_model.CpSolver()
        solver_status = "available"
    except Exception as e:
        logger.error(f"Solver diagnostics check failed: {e}")
        solver_status = "error"

    approval_enabled = is_approval_enabled()
    records_count = get_approval_records_count()
    adapter_status = get_execution_adapter().check_status()
    active_dataset = get_active_dataset()

    log_event(
        event_name="DIAGNOSTICS_INSPECTED",
        outcome="HEALTHY",
        solver_status=solver_status,
        demo_approvals_enabled=approval_enabled,
        dataset_id=active_dataset.dataset_id,
    )

    return DiagnosticsResponse(
        app="SupplyShield AI",
        version="0.6.0",
        service_status="operational",
        model_horizon_days=HORIZON,
        model_seed=42,
        supported_shutdown_days_range=[1, 14],
        supported_strategies=["reorder", "optimized", "agent"],
        solver_status=solver_status,
        demo_approvals_enabled=approval_enabled,
        approval_storage_type="jsonl_ledger",
        approval_records_count=records_count,
        execution_adapter_status=adapter_status.status,
        external_execution_enabled=False,
        dataset_id=active_dataset.dataset_id,
        dataset_version=active_dataset.dataset_version,
        dataset_fingerprint=active_dataset.fingerprint,
        data_source_type=active_dataset.manifest.source_type,
        data_validation_status=active_dataset.quality_report.status,
        model_boundaries=[
            "Supplier outage blackout and shared daily capacity strictly enforced",
            "Transit lead times and deterministic arrival physics strictly enforced",
            "Downstream factory assembly throughput (FAC-01: 100u/d, FAC-02: 80u/d) is topological structural metadata (unconstrained transfer)",
            "Downstream DC storage buffers (DC-01, DC-02) are topological structural metadata (unconstrained staging)",
            "Unmet demand is accounted under period-specific lost service (no backlog queue carryover)",
            "Real-world purchase order dispatch and ERP integrations are NOT_CONFIGURED",
        ],
    )
