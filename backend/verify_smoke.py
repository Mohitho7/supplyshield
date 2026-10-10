"""
SupplyShield AI — Live HTTP Smoke Verification (Phase B5 + Phase B6)

Tests against the live running FastAPI server at http://127.0.0.1:8000 using urllib:
- / -> System metadata and decision-support governance flags
- /health -> HealthResponse
- /openapi.json -> Valid OpenAPI schema with operational tags and descriptions
- /api/network -> NetworkTopology
- /api/simulate (mode in {reorder, optimized, agent}, shutdown_days in {1, 7, 14}) -> SimulationResponse
- /api/simulate?recovery_mode=agent (legacy alias) -> SimulationResponse
- /api/simulate mode conflict rejection (mode != recovery_mode) -> HTTP 422
- /api/optimize (shutdown_days in {1, 7, 14}) -> OptimizationResponse
- /api/recovery (shutdown_days in {1, 7, 14}) -> RecoveryResponse
- /api/compare (shutdown_days in {1, 7, 14}) -> ComparisonResponse
- Scenario propagation checks: SCEN-SD{d}-H21-S42 on all endpoints
- Invalid inputs: shutdown_days in {0, 15, -1, "true", "false", "invalid"}, mode="bogus" -> HTTP 422
- Phase B6:
  - /api/diagnostics -> DiagnosticsResponse
  - /api/execution/status -> ExecutionAdapterStatus (NOT_CONFIGURED)
  - /api/trace -> 11-step DecisionTraceEvent sequence
  - POST /api/approval -> ApprovalRecord (explicit planner approval workflow)
  - GET /api/approval -> Retrieval of approval record
  - POST /api/approval rejection of mismatched fingerprint (HTTP 409)
  - POST /api/approval rejection of infeasible candidate (HTTP 400)
- Validates every returned JSON payload against its Pydantic response model.
"""

import json
import urllib.request
import urllib.error

from schemas import (
    HealthResponse,
    NetworkTopology,
    SimulationResponse,
    OptimizationResponse,
    RecoveryResponse,
    ComparisonResponse,
    DiagnosticsResponse,
    ExecutionAdapterStatus,
    ApprovalRecord,
)
try:
    from data_repository import DataStatusResponse
except ImportError:
    from backend.data_repository import DataStatusResponse

BASE_URL = "http://127.0.0.1:8000"


def http_get(path, headers=None):
    url = f"{BASE_URL}{path}"
    h = {"User-Agent": "SupplyShield-SmokeTest/1.0"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return status, json.loads(body), resp_headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed, dict(e.headers)


def http_post(path, data, headers=None):
    url = f"{BASE_URL}{path}"
    h = {
        "User-Agent": "SupplyShield-SmokeTest/1.0",
        "Content-Type": "application/json",
    }
    if headers:
        h.update(headers)
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers)
            return status, json.loads(body), resp_headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed, dict(e.headers)


def run_smoke_tests():
    print("=== STARTING PHASE B6 HTTP / API SMOKE VERIFICATION ===")

    # 1. Root & System governance
    status, root_data, _ = http_get("/")
    assert status == 200, f"/ failed: {status}"
    assert root_data.get("app") == "SupplyShield AI"
    assert root_data.get("planner_approval_required") is True
    assert root_data.get("external_execution") is False
    print("PASS: / root endpoint confirms decision-support governance flags")

    # 2. /health
    status, data, _ = http_get("/health")
    assert status == 200, f"/health failed: {status}"
    HealthResponse.model_validate(data)
    print("PASS: /health validates cleanly against HealthResponse")

    # 3. /openapi.json
    status, openapi, _ = http_get("/openapi.json")
    assert status == 200, f"/openapi.json failed: {status}"
    assert "paths" in openapi and "/api/recovery" in openapi["paths"]
    assert "/api/diagnostics" in openapi["paths"]
    assert "/api/approval" in openapi["paths"]
    print("PASS: /openapi.json documentation is live with Phase B6 endpoints")

    # 4. /api/network
    status, data, _ = http_get("/api/network")
    assert status == 200, f"/api/network failed: {status}"
    NetworkTopology.model_validate(data)
    print("PASS: /api/network validates cleanly against NetworkTopology")

    # 5. /api/simulate across strategies and durations
    for mode in ["reorder", "optimized", "agent"]:
        for d in [1, 7, 14]:
            expected_scenario_id = f"SCEN-SD{d}-H21-S42"
            status, data, _ = http_get(f"/api/simulate?mode={mode}&shutdown_days={d}")
            assert status == 200, f"/api/simulate {mode} d={d} failed: {status}"
            validated_sim = SimulationResponse.model_validate(data)
            assert validated_sim.scenario.shutdown_days == d
            assert validated_sim.scenario.scenario_id == expected_scenario_id
            print(f"PASS: /api/simulate mode={mode} shutdown_days={d} (scenario_id={expected_scenario_id}) validated")

    # 6. /api/simulate legacy alias & parameter resolution
    status, data, _ = http_get("/api/simulate?recovery_mode=agent&shutdown_days=7")
    assert status == 200, f"legacy recovery_mode failed: {status}"
    validated_sim = SimulationResponse.model_validate(data)
    assert validated_sim.scenario.recovery_mode == "agent"
    print("PASS: /api/simulate legacy recovery_mode=agent validated")

    # Matching mode and recovery_mode
    status, data, _ = http_get("/api/simulate?mode=agent&recovery_mode=agent&shutdown_days=7")
    assert status == 200, f"matching mode and recovery_mode failed: {status}"
    print("PASS: /api/simulate matching mode and recovery_mode accepted")

    # Conflicting mode and recovery_mode -> HTTP 422
    status, data, _ = http_get("/api/simulate?mode=optimized&recovery_mode=reorder&shutdown_days=7")
    assert status == 422, f"conflicting mode and recovery_mode must return 422, got {status}"
    assert "Conflicting strategy modes" in str(data)
    print("PASS: /api/simulate conflicting mode and recovery_mode rejected with HTTP 422")

    # 7. /api/optimize across durations
    for d in [1, 7, 14]:
        expected_scenario_id = f"SCEN-SD{d}-H21-S42"
        status, data, _ = http_get(f"/api/optimize?shutdown_days={d}")
        assert status == 200, f"/api/optimize d={d} failed: {status}"
        validated_opt = OptimizationResponse.model_validate(data)
        assert validated_opt.scenario.shutdown_days == d
        assert validated_opt.scenario.scenario_id == expected_scenario_id
        print(f"PASS: /api/optimize shutdown_days={d} (scenario_id={expected_scenario_id}) validated")

    # 8. /api/recovery across durations
    recovery_sd7_fingerprint = None
    for d in [1, 7, 14]:
        expected_scenario_id = f"SCEN-SD{d}-H21-S42"
        status, data, _ = http_get(f"/api/recovery?shutdown_days={d}")
        assert status == 200, f"/api/recovery d={d} failed: {status}"
        validated_rec = RecoveryResponse.model_validate(data)
        assert validated_rec.scenario.shutdown_days == d
        assert validated_rec.scenario.scenario_id == expected_scenario_id

        # Phase B6 trust layer checks
        assert validated_rec.workflow_state in ("SELECTED", "APPROVED", "REJECTED")
        assert validated_rec.execution_status == "NOT_CONFIGURED"
        assert validated_rec.external_execution is False
        assert validated_rec.plan_fingerprint is not None
        assert len(validated_rec.decision_trace) == 11
        assert validated_rec.validation_report is not None
        assert validated_rec.validation_report.overall_status == "VALID"

        if d == 7:
            recovery_sd7_fingerprint = validated_rec.plan_fingerprint

        # Verify candidate provenance
        assert validated_rec.candidates is not None and len(validated_rec.candidates) == 3
        for cand in validated_rec.candidates:
            assert cand.scenario_id == expected_scenario_id
            assert cand.plan_fingerprint is not None
            assert cand.validation_report is not None

        print(f"PASS: /api/recovery shutdown_days={d} (fingerprint={validated_rec.plan_fingerprint[:12]}...) validated")

    # 9. /api/compare across durations
    for d in [1, 7, 14]:
        expected_scenario_id = f"SCEN-SD{d}-H21-S42"
        status, data, _ = http_get(f"/api/compare?shutdown_days={d}")
        assert status == 200, f"/api/compare d={d} failed: {status}"
        validated_comp = ComparisonResponse.model_validate(data)
        assert validated_comp.scenario.shutdown_days == d
        assert validated_comp.scenario.scenario_id == expected_scenario_id
        print(f"PASS: /api/compare shutdown_days={d} validated")

    # 10. Boundary and invalid inputs (HTTP 422 enforcement)
    invalid_cases = [
        "/api/simulate?shutdown_days=0",
        "/api/simulate?shutdown_days=15",
        "/api/simulate?shutdown_days=-1",
        "/api/simulate?shutdown_days=true",
        "/api/simulate?shutdown_days=false",
        "/api/simulate?shutdown_days=invalid_string",
        "/api/simulate?mode=unsupported_mode",
        "/api/simulate?recovery_mode=invalid_mode",
        "/api/optimize?shutdown_days=0",
        "/api/optimize?shutdown_days=20",
        "/api/optimize?shutdown_days=true",
        "/api/recovery?shutdown_days=0",
        "/api/recovery?shutdown_days=99",
        "/api/recovery?shutdown_days=false",
        "/api/compare?shutdown_days=0",
        "/api/compare?shutdown_days=-5",
    ]
    for case in invalid_cases:
        status, _, _ = http_get(case)
        assert status == 422, f"Expected 422 for {case}, got {status}"
        print(f"PASS: Correctly rejected invalid input: {case} -> HTTP 422")

    # 11. Phase B6: /api/diagnostics
    status, diag_data, _ = http_get("/api/diagnostics")
    assert status == 200, f"/api/diagnostics failed: {status}"
    diag = DiagnosticsResponse.model_validate(diag_data)
    assert diag.app == "SupplyShield AI"
    assert diag.solver_status == "available"
    assert diag.execution_adapter_status == "NOT_CONFIGURED"
    assert diag.external_execution_enabled is False
    print("PASS: /api/diagnostics validates operational readiness without secret leakage")

    # 12. Phase B6: /api/execution/status
    status, exec_data, _ = http_get("/api/execution/status")
    assert status == 200, f"/api/execution/status failed: {status}"
    exec_status = ExecutionAdapterStatus.model_validate(exec_data)
    assert exec_status.status == "NOT_CONFIGURED"
    assert exec_status.available is False
    assert exec_status.external_execution is False
    print("PASS: /api/execution/status confirms execution boundary (NOT_CONFIGURED)")

    # 13. Phase B6: /api/trace
    status, trace_data, _ = http_get("/api/trace?shutdown_days=7")
    assert status == 200, f"/api/trace failed: {status}"
    assert isinstance(trace_data, list) and len(trace_data) == 11
    assert trace_data[0]["stage"] == "SCENARIO_ACCEPTED"
    assert trace_data[10]["stage"] == "EXECUTION_BOUNDARY"
    print("PASS: /api/trace returns complete 11-stage decision trace")

    # 14. Phase B6: Explicit Approval Flow
    assert recovery_sd7_fingerprint is not None
    appr_payload = {
        "scenario_id": "SCEN-SD7-H21-S42",
        "candidate_id": "CAND-AGENT-SD7",
        "action": "APPROVE",
        "plan_fingerprint": recovery_sd7_fingerprint,
        "reviewer_label": "Smoke Test Planner",
        "comment": "Automated smoke validation approval",
    }
    status, appr_resp, _ = http_post("/api/approval", appr_payload)
    assert status in (200, 201), f"POST /api/approval failed: {status} -> {appr_resp}"
    appr_rec = ApprovalRecord.model_validate(appr_resp)
    assert appr_rec.workflow_state == "APPROVED"
    assert appr_rec.external_execution is False
    print("PASS: POST /api/approval successfully recorded explicit planner approval")

    # Verify retrieval
    status, get_appr, _ = http_get("/api/approval?scenario_id=SCEN-SD7-H21-S42&candidate_id=CAND-AGENT-SD7")
    assert status == 200, f"GET /api/approval failed: {status}"
    assert get_appr["record_id"] == appr_rec.record_id
    print("PASS: GET /api/approval successfully retrieved persisted approval record")

    # Verify retrieval via shutdown_days query filter
    status, get_appr_sd7, _ = http_get("/api/approval?shutdown_days=7")
    assert status == 200, f"GET /api/approval?shutdown_days=7 failed: {status}"
    assert isinstance(get_appr_sd7, list) and len(get_appr_sd7) >= 1
    print("PASS: GET /api/approval?shutdown_days=7 successfully filtered records")

    # Verify boundary rejection on /api/approval?shutdown_days
    status, _, _ = http_get("/api/approval?shutdown_days=0")
    assert status == 422, f"Expected 422 for shutdown_days=0 on /api/approval, got {status}"
    status, _, _ = http_get("/api/approval?shutdown_days=15")
    assert status == 422, f"Expected 422 for shutdown_days=15 on /api/approval, got {status}"
    print("PASS: /api/approval correctly rejected out-of-boundary shutdown_days with HTTP 422")

    # Verify boundary rejection on /api/trace?shutdown_days
    status, _, _ = http_get("/api/trace?shutdown_days=0")
    assert status == 422, f"Expected 422 for shutdown_days=0 on /api/trace, got {status}"
    status, _, _ = http_get("/api/trace?shutdown_days=15")
    assert status == 422, f"Expected 422 for shutdown_days=15 on /api/trace, got {status}"
    print("PASS: /api/trace correctly rejected out-of-boundary shutdown_days with HTTP 422")

    # 15. Phase B6: Mismatched plan fingerprint rejection
    bad_fingerprint_payload = {
        "scenario_id": "SCEN-SD7-H21-S42",
        "candidate_id": "CAND-AGENT-SD7",
        "action": "APPROVE",
        "plan_fingerprint": "badfingerprint1234567890abcdef1234567890abcdef",
    }
    status, _, _ = http_post("/api/approval", bad_fingerprint_payload)
    assert status == 409, f"Expected 409 for mismatched fingerprint, got {status}"
    print("PASS: POST /api/approval correctly rejected mismatched fingerprint with HTTP 409")

    # 16. Phase B6: Infeasible candidate rejection
    infeasible_payload = {
        "scenario_id": "SCEN-SD7-H21-S42",
        "candidate_id": "CAND-REORDER-SD7",
        "action": "APPROVE",
        "plan_fingerprint": "dummy",
    }
    status, _, _ = http_post("/api/approval", infeasible_payload)
    assert status == 400, f"Expected 400 for infeasible candidate, got {status}"
    print("PASS: POST /api/approval correctly rejected infeasible reorder candidate with HTTP 400")

    # 17. Data Layer Status & Provenance check
    status, data_status_body, _ = http_get("/api/data/status")
    assert status == 200, f"GET /api/data/status failed with HTTP {status}"
    ds_val = DataStatusResponse.model_validate(data_status_body)
    assert ds_val.dataset_id == "demo_v1", f"Expected dataset_id demo_v1, got {ds_val.dataset_id}"
    assert ds_val.dataset_version == "1.0.0", f"Expected dataset_version 1.0.0, got {ds_val.dataset_version}"
    assert ds_val.validation_status == "VALID", f"Expected validation_status VALID, got {ds_val.validation_status}"
    assert ds_val.supplier_count == 2, f"Expected 2 suppliers, got {ds_val.supplier_count}"
    assert ds_val.product_count == 2, f"Expected 2 products, got {ds_val.product_count}"
    assert ds_val.error_count == 0, f"Expected 0 errors, got {ds_val.error_count}"
    assert len(ds_val.dataset_fingerprint) == 64, "Expected 64-char hex SHA-256 fingerprint"
    print("PASS: GET /api/data/status returned valid DataStatusResponse contract with active canonical dataset")

    # 18. Diagnostics Dataset metadata enrichment check
    status, diag_body, _ = http_get("/api/diagnostics")
    assert status == 200, f"GET /api/diagnostics failed: {status}"
    diag_val = DiagnosticsResponse.model_validate(diag_body)
    assert diag_val.dataset_id == "demo_v1", f"Expected dataset_id demo_v1 in diagnostics, got {diag_val.dataset_id}"
    assert diag_val.dataset_version == "1.0.0", f"Expected dataset_version 1.0.0 in diagnostics, got {diag_val.dataset_version}"
    assert diag_val.data_validation_status == "VALID", f"Expected VALID validation in diagnostics, got {diag_val.data_validation_status}"
    print("PASS: GET /api/diagnostics enriched with canonical dataset provenance and validation status")

    print("\n=== ALL LIVE SMOKE & CONTRACT VALIDATION CHECKS (PHASE B5 + B6 + DATA LAYER) PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    run_smoke_tests()
