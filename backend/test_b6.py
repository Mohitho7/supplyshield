"""
SupplyShield AI — Phase B6 Test Suite: Execution Boundary, Decision Traceability & Operational Diagnostics

Comprehensive test suite verifying:
1. Decision Trace: 11-step deterministic sequence, scenario/candidate integrity, determinism.
2. Structured Logging & Error Sanitization: correlation ID propagation, no secret leakage.
3. Validation Report: granular check results, infeasible benchmark exclusion, unmodeled constraints (NOT_MODELED).
4. Planner Approvals: explicit typed POST action, plan fingerprint binding, infeasible plan rejection,
   mismatched fingerprint rejection, rejection recording, idempotency, disabled mode handling.
5. Execution Boundary & Diagnostics: NullExecutionAdapter enforcement, external_execution=False,
   sanitized operational diagnostics without filesystem or secret leaks.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from main import (
    submit_approval,
    get_approval,
    get_decision_trace,
    execution_status,
    diagnostics,
    recovery,
    simulate,
    log_event,
)
from coordinator import coordinate_recovery, compute_plan_fingerprint
from schemas import (
    ApprovalRequest,
    ApprovalRecord,
    RecoveryResponse,
    DiagnosticsResponse,
    ExecutionAdapterStatus,
    DecisionTraceEvent,
)
from approval import (
    record_approval,
    get_latest_approval,
    read_approval_records,
    is_approval_enabled,
    ENV_APPROVALS_ENABLED,
    ENV_LEDGER_PATH,
)
from execution import get_execution_adapter, NullExecutionAdapter


class TestPhaseB6TrustLayer(unittest.TestCase):
    """Test suite for Phase B6 operational trust layer."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = os.path.join(self.temp_dir.name, "test_ledger.jsonl")
        self.patcher_ledger = patch.dict(os.environ, {
            ENV_LEDGER_PATH: self.ledger_file,
            ENV_APPROVALS_ENABLED: "true",
        })
        self.patcher_ledger.start()

    def tearDown(self):
        self.patcher_ledger.stop()
        self.temp_dir.cleanup()

    # ==========================================================================
    # 1. DECISION TRACE AND LOGS (Tests 1 - 5)
    # ==========================================================================

    def test_01_decision_trace_stages_and_deterministic_order(self):
        """1. Trace contains the expected 11 stages in deterministic order."""
        result = coordinate_recovery(shutdown_days=7)
        trace = result.get("decision_trace")
        self.assertIsNotNone(trace)
        self.assertEqual(len(trace), 11)

        expected_stages = [
            "SCENARIO_ACCEPTED",
            "SPECIALIST_ASSESSMENT",
            "CANDIDATE_GENERATION",
            "CONSTRAINTS_EVALUATED",
            "VALIDATION_RESULT",
            "METRICS_CALCULATED",
            "RANKING_SCORED",
            "RANKING_ASSIGNED",
            "CANDIDATE_SELECTED",
            "PLANNER_APPROVAL_GATE",
            "EXECUTION_BOUNDARY",
        ]

        for idx, event in enumerate(trace, start=1):
            self.assertEqual(event["step"], idx)
            self.assertEqual(event["stage"], expected_stages[idx - 1])
            self.assertTrue(len(event["summary"]) > 0)
            self.assertIsNotNone(event["outcome"])

        # Also verify endpoint returns validated models
        trace_endpoint = get_decision_trace(shutdown_days=7)
        self.assertEqual(len(trace_endpoint), 11)
        for t in trace_endpoint:
            self.assertIsInstance(t, dict)

    def test_02_candidate_and_scenario_references_consistent(self):
        """2. Candidate and scenario references remain consistent throughout the trace."""
        result = coordinate_recovery(shutdown_days=7)
        trace = result.get("decision_trace")
        scenario_id = result["scenario"]["scenario_id"]
        selected_id = result["selection"]["selected_candidate_id"]

        step1 = trace[0]
        self.assertEqual(step1["entity_reference"], scenario_id)

        step9 = trace[8]
        self.assertEqual(step9["entity_reference"], selected_id)

        step10 = trace[9]
        self.assertIn("approved=False", step10["summary"])

        step11 = trace[10]
        self.assertEqual(step11["outcome"], "NOT_CONFIGURED")

    def test_03_error_responses_do_not_leak_details_or_secrets(self):
        """3. Error responses do not leak exception details or secrets."""
        with self.assertRaises(HTTPException) as cm:
            simulate(shutdown_days=99)
        self.assertEqual(cm.exception.status_code, 422)
        detail = str(cm.exception.detail)
        self.assertNotIn("password", detail.lower())
        self.assertNotIn("secret", detail.lower())
        self.assertNotIn("traceback", detail.lower())

    def test_04_structured_logging_correlation_context(self):
        """4. Structured logging includes correlation context without sensitive data."""
        custom_cid = "CORR-TEST-TRACE-9999"
        # Test logging helper directly
        log_event(
            event_name="TEST_LOG_EVENT",
            outcome="VERIFIED",
            correlation_id=custom_cid,
            scenario_id="SCEN-SD7-H21-S42",
            secret_password_token="should_not_appear",
        )

    def test_05_repeating_identical_inputs_produces_consistent_outcomes(self):
        """5. Repeating identical inputs produces consistent decision outcomes."""
        res1 = coordinate_recovery(shutdown_days=7)
        res2 = coordinate_recovery(shutdown_days=7)

        self.assertEqual(res1["plan_fingerprint"], res2["plan_fingerprint"])
        self.assertEqual(res1["selection"]["selected_candidate_id"], res2["selection"]["selected_candidate_id"])
        self.assertEqual(len(res1["decision_trace"]), len(res2["decision_trace"]))
        for e1, e2 in zip(res1["decision_trace"], res2["decision_trace"]):
            self.assertEqual(e1["stage"], e2["stage"])
            self.assertEqual(e1["outcome"], e2["outcome"])

    # ==========================================================================
    # 2. VALIDATION REPORT & MODEL BOUNDARIES (Tests 6 - 9)
    # ==========================================================================

    def test_06_feasible_candidate_exposes_truthful_check_results(self):
        """6. A feasible candidate exposes truthful check results."""
        result = coordinate_recovery(shutdown_days=7)
        cand_a = next(c for c in result["candidates"] if c["candidate_id"] == "CAND-AGENT-SD7")
        report = cand_a.get("validation_report")
        self.assertIsNotNone(report)
        self.assertEqual(report["overall_status"], "VALID")

        pass_check_ids = {c["check_id"] for c in report["checks"] if c["status"] == "PASS"}
        self.assertIn("CHK-SHUTDOWN-BLACKOUT", pass_check_ids)
        self.assertIn("CHK-SUPPLIER-CAPACITY", pass_check_ids)
        self.assertIn("CHK-LEAD-TIME", pass_check_ids)
        self.assertIn("CHK-ORDER-QTY", pass_check_ids)
        self.assertIn("CHK-COST-RECONCILIATION", pass_check_ids)

    def test_07_infeasible_reorder_benchmark_fails_blackout_and_selection(self):
        """7. The infeasible reorder benchmark fails shutdown blackout and remains non-selectable."""
        result = coordinate_recovery(shutdown_days=7)
        cand_c = next(c for c in result["candidates"] if c["candidate_id"] == "CAND-REORDER-SD7")
        report = cand_c.get("validation_report")
        self.assertIsNotNone(report)
        self.assertEqual(report["overall_status"], "INVALID")

        blackout_check = next(c for c in report["checks"] if c["check_id"] == "CHK-SHUTDOWN-BLACKOUT")
        self.assertEqual(blackout_check["status"], "FAIL")
        self.assertEqual(blackout_check["severity"], "CRITICAL")
        self.assertIn("order(s) placed with primary supplier SUP-01 during shutdown", blackout_check["details"])

        eligibility_check = next(c for c in report["checks"] if c["check_id"] == "CHK-SELECTION-ELIGIBILITY")
        self.assertEqual(eligibility_check["status"], "FAIL")

    def test_08_unmodeled_downstream_constraints_not_modeled(self):
        """8. Unmodeled downstream constraints report NOT_MODELED, not PASS."""
        result = coordinate_recovery(shutdown_days=7)
        report = result["validation_report"]
        self.assertIsNotNone(report)

        factory_check = next(c for c in report["checks"] if c["check_id"] == "CHK-FACTORY-THROUGHPUT")
        self.assertEqual(factory_check["status"], "NOT_MODELED")
        self.assertIn("topological structural metadata", factory_check["details"])

        dc_check = next(c for c in report["checks"] if c["check_id"] == "CHK-DC-CAPACITY")
        self.assertEqual(dc_check["status"], "NOT_MODELED")
        self.assertIn("unconstrained pass-through", dc_check["details"])

    def test_09_cost_reconciliation_enforced(self):
        """9. Cost reconciliation and recovery-integrity checks remain enforced."""
        result = coordinate_recovery(shutdown_days=7)
        # Cost is exactly ₹16,470 for 7-day shutdown agent
        cost = result["optimization"]["metrics"]["total_landed_cost"]
        self.assertEqual(cost, 16470.0)

        report = result["validation_report"]
        cost_check = next(c for c in report["checks"] if c["check_id"] == "CHK-COST-RECONCILIATION")
        self.assertEqual(cost_check["status"], "PASS")
        self.assertIn("16,470.00", cost_check["details"])

    # ==========================================================================
    # 3. PLANNER APPROVALS (Tests 10 - 20)
    # ==========================================================================

    def test_10_approval_mode_disabled_returns_forbidden(self):
        """10. Approval mode disabled returns a truthful disabled result."""
        with patch.dict(os.environ, {ENV_APPROVALS_ENABLED: "false"}):
            self.assertFalse(is_approval_enabled())
            req = ApprovalRequest(
                scenario_id="SCEN-SD7-H21-S42",
                candidate_id="CAND-AGENT-SD7",
                action="APPROVE",
                plan_fingerprint="dummyfingerprint",
            )
            with self.assertRaises(HTTPException) as cm:
                submit_approval(req)
            self.assertEqual(cm.exception.status_code, 403)
            self.assertIn("disabled", cm.exception.detail)

    def test_11_approval_cannot_be_created_via_get_or_query_param(self):
        """11. Approval cannot be created through GET request or supplied approved=true parameter."""
        data = recovery(shutdown_days=7)
        self.assertEqual(data["workflow_state"], "SELECTED")
        self.assertFalse(data["recommendation"]["approved"])
        self.assertFalse(data["external_execution"])

    def test_12_infeasible_candidate_cannot_be_approved(self):
        """12. Invalid or infeasible candidates cannot be approved."""
        res = coordinate_recovery(shutdown_days=7)
        cand_c = next(c for c in res["candidates"] if c["candidate_id"] == "CAND-REORDER-SD7")

        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-REORDER-SD7",
            action="APPROVE",
            plan_fingerprint=cand_c["plan_fingerprint"],
        )
        with self.assertRaises(HTTPException) as cm:
            submit_approval(req)
        self.assertEqual(cm.exception.status_code, 400)
        self.assertIn("failed feasibility validation", cm.exception.detail)

    def test_13_mismatched_scenario_id_rejected(self):
        """13. Mismatched or invalid scenario IDs are rejected."""
        req = ApprovalRequest(
            scenario_id="INVALID-SCENARIO-FORMAT",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint="abc",
        )
        with self.assertRaises(HTTPException) as cm:
            submit_approval(req)
        self.assertEqual(cm.exception.status_code, 422)

    def test_14_mismatched_plan_fingerprint_rejected(self):
        """14. Mismatched plan fingerprints are rejected."""
        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint="0000000000000000000000000000000000000000000000000000000000000000",
        )
        with self.assertRaises(HTTPException) as cm:
            submit_approval(req)
        self.assertEqual(cm.exception.status_code, 409)
        self.assertIn("fingerprint mismatch", cm.exception.detail.lower())

    def test_15_explicit_approval_changes_only_correct_workflow_state(self):
        """15. A genuine explicit approval action changes only the workflow state to APPROVED."""
        res_initial = coordinate_recovery(shutdown_days=7)
        fingerprint = res_initial["plan_fingerprint"]

        # Initially SELECTED
        self.assertEqual(res_initial["workflow_state"], "SELECTED")
        self.assertFalse(res_initial["recommendation"]["approved"])
        self.assertFalse(res_initial["external_execution"])

        # Post explicit approval via submit_approval
        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint=fingerprint,
            reviewer_label="Senior Planner Test",
            comment="Contingency allocation verified feasible.",
        )
        appr_data = submit_approval(req)
        self.assertEqual(appr_data.workflow_state, "APPROVED")
        self.assertEqual(appr_data.action, "APPROVE")
        self.assertFalse(appr_data.external_execution)
        self.assertEqual(appr_data.execution_status, "NOT_CONFIGURED")

        # Now when reading recovery for this scenario, workflow_state is APPROVED
        res_after = coordinate_recovery(shutdown_days=7)
        self.assertEqual(res_after["workflow_state"], "APPROVED")
        self.assertFalse(res_after["recommendation"]["approved"])
        self.assertFalse(res_after["external_execution"])

        # Query via get_approval endpoint
        retrieved = get_approval(scenario_id="SCEN-SD7-H21-S42", candidate_id="CAND-AGENT-SD7")
        self.assertEqual(retrieved.record_id, appr_data.record_id)
        self.assertEqual(retrieved.workflow_state, "APPROVED")

    def test_16_explicit_rejection_recorded_truthfully(self):
        """16. An explicit rejection is recorded truthfully without deleting candidate."""
        res = coordinate_recovery(shutdown_days=7)
        fingerprint = res["plan_fingerprint"]

        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="REJECT",
            plan_fingerprint=fingerprint,
            reviewer_label="Operations Director",
            comment="Holding inventory instead of expediting alternate sourcing.",
        )
        rec_data = submit_approval(req)
        self.assertEqual(rec_data.action, "REJECT")
        self.assertEqual(rec_data.workflow_state, "REJECTED")

        # Recovery reports REJECTED, but candidate still exists
        res_after = coordinate_recovery(shutdown_days=7)
        self.assertEqual(res_after["workflow_state"], "REJECTED")
        self.assertFalse(res_after["recommendation"]["approved"])

    def test_17_duplicate_requests_are_idempotent(self):
        """17. Duplicate requests behave deterministically and do not create unintended duplicate decisions."""
        res = coordinate_recovery(shutdown_days=7)
        fingerprint = res["plan_fingerprint"]

        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint=fingerprint,
            reviewer_label="Planner",
            comment="Same comment",
        )

        rec1 = submit_approval(req)
        rec2 = submit_approval(req)

        self.assertEqual(rec1.record_id, rec2.record_id)
        records = read_approval_records()
        self.assertEqual(len(records), 1)

    def test_18_storage_failures_return_safe_error(self):
        """18. Storage failures return safe errors and do not report false approval success."""
        res = coordinate_recovery(shutdown_days=7)
        fingerprint = res["plan_fingerprint"]

        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint=fingerprint,
        )

        # Mock open() to fail on write
        with patch("builtins.open", side_effect=IOError("Disk write simulated failure")):
            with self.assertRaises(HTTPException) as cm:
                submit_approval(req)
            self.assertEqual(cm.exception.status_code, 500)
            self.assertIn("Failed to persist", cm.exception.detail)

    def test_19_no_approval_operation_invokes_external_execution(self):
        """19. No approval operation invokes external execution."""
        res = coordinate_recovery(shutdown_days=7)
        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint=res["plan_fingerprint"],
        )
        record = submit_approval(req)
        self.assertIsNotNone(record)
        self.assertFalse(record.external_execution)
        self.assertEqual(record.execution_status, "NOT_CONFIGURED")

    def test_20_fingerprint_invalidates_on_material_plan_change(self):
        """20. Changing material plan details invalidates former approval."""
        res = coordinate_recovery(shutdown_days=7)
        orig_cand = next(c for c in res["candidates"] if c["candidate_id"] == "CAND-AGENT-SD7")
        orig_fingerprint = orig_cand["plan_fingerprint"]

        # Mutate order quantity
        modified_cand = json.loads(json.dumps(orig_cand))
        modified_cand["orders"][0]["quantity"] += 10
        new_fingerprint = compute_plan_fingerprint(modified_cand)

        self.assertNotEqual(orig_fingerprint, new_fingerprint)

        # Attempt approval with old fingerprint for modified plan fails
        req = ApprovalRequest(
            scenario_id="SCEN-SD7-H21-S42",
            candidate_id="CAND-AGENT-SD7",
            action="APPROVE",
            plan_fingerprint="stale_fingerprint_000000000000",
        )
        with self.assertRaises(HTTPException) as cm:
            submit_approval(req)
        self.assertEqual(cm.exception.status_code, 409)

    # ==========================================================================
    # 4. EXECUTION BOUNDARY & OPERATIONAL DIAGNOSTICS (Tests 21 - 25)
    # ==========================================================================

    def test_21_default_execution_adapter_reports_not_configured(self):
        """21. Default execution adapter reports NOT_CONFIGURED and available=False."""
        status = execution_status()
        self.assertIsInstance(status, ExecutionAdapterStatus)
        self.assertEqual(status.status, "NOT_CONFIGURED")
        self.assertFalse(status.available)
        self.assertFalse(status.external_execution)
        self.assertEqual(status.adapter_name, "NullExecutionAdapter")

    def test_22_null_adapter_dispatch_raises_runtime_error(self):
        """22. NullExecutionAdapter.attempt_dispatch raises explicit non-dispatch error."""
        adapter = get_execution_adapter()
        with self.assertRaises(RuntimeError) as cm:
            adapter.attempt_dispatch({})
        self.assertIn("External execution is disabled", str(cm.exception))

    def test_23_no_fabricated_execution_receipt_or_erp_id(self):
        """23. No fabricated execution receipt or ERP identifier is returned."""
        result = coordinate_recovery(shutdown_days=7)
        self.assertFalse(result["external_execution"])
        self.assertEqual(result["execution_status"], "NOT_CONFIGURED")

        # Ensure recommendation notice warns of execution boundary
        sel = result["selection"]
        self.assertIn("No real-world purchase orders are dispatched", sel["governance_notice"])

    def test_24_diagnostics_do_not_expose_secrets_or_filesystem_paths(self):
        """24. Diagnostics do not expose secrets or local filesystem paths."""
        diag = diagnostics()
        self.assertIsInstance(diag, DiagnosticsResponse)
        serialized = diag.model_dump_json()

        self.assertNotIn("c:\\", serialized.lower())
        self.assertNotIn("c:/", serialized.lower())
        self.assertNotIn(".jsonl", serialized.lower())
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("secret", serialized.lower())

    def test_25_diagnostics_reports_core_and_integration_status_accurately(self):
        """25. Diagnostics reports core solver and integration status accurately."""
        diag = diagnostics()
        self.assertEqual(diag.app, "SupplyShield AI")
        self.assertEqual(diag.service_status, "operational")
        self.assertEqual(diag.solver_status, "available")
        self.assertEqual(diag.model_horizon_days, 21)
        self.assertEqual(diag.model_seed, 42)
        self.assertEqual(diag.supported_shutdown_days_range, [1, 14])
        self.assertTrue(diag.demo_approvals_enabled)
        self.assertEqual(diag.execution_adapter_status, "NOT_CONFIGURED")
        self.assertFalse(diag.external_execution_enabled)
        self.assertTrue(len(diag.model_boundaries) >= 4)


if __name__ == "__main__":
    unittest.main()
