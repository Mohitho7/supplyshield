"""
SupplyShield AI — API Layer & Workflow Integration Test Suite (Phase B5)

Verifies:
1. Validated and explicit scenario configuration across durations 1, 3, 7, 10, 14.
2. Scenario identity and propagation: single source of truth (SCEN-SD{d}-H21-S42).
3. Strategy mode parameter resolution and conflict rejection (HTTP 422).
4. Four specialist agent outputs, candidate provenance, metric parity, ranking consistency.
5. Invariant integrity enforcement (verify_recovery_integrity).
6. Workflow governance states: advisory decision-support, planner_approval_required=True,
   approved=False, no external ERP execution.
7. Safe exception handling without leaking stack traces, filesystem paths, or secrets.
8. Backward compatibility with all Phase B0-B4 response contracts.
"""

import unittest
from unittest.mock import MagicMock
from fastapi import HTTPException
from pydantic import ValidationError

from main import (
    health,
    get_network,
    simulate,
    optimize,
    recovery,
    compare_strategies,
    global_exception_handler,
    get_approval,
)
from simulator import run_simulation, NETWORK, HORIZON
from optimizer import optimize_plan
from coordinator import coordinate_recovery, verify_recovery_integrity
from schemas import (
    HealthResponse,
    NetworkTopology,
    SimulationResponse,
    OptimizationResponse,
    RecoveryResponse,
    ComparisonResponse,
    ScenarioConfig,
)


class TestPhaseB5ApiWorkflowIntegration(unittest.TestCase):
    """Phase B5 API Layer and Workflow Integration Tests."""

    # ==========================================================================
    # 1. SCENARIO CONFIGURATION & IDENTITY PROPAGATION
    # ==========================================================================

    def test_scenario_propagation_across_all_durations(self):
        """
        Verify that scenario configuration (shutdown_days, horizon=21, seed=42, scenario_id)
        is consistently formed and propagated across all endpoints for D in {1, 3, 7, 10, 14}.
        """
        for d in [1, 3, 7, 10, 14]:
            expected_scenario_id = f"SCEN-SD{d}-H21-S42"

            # 1. Simulation endpoint
            sim_res = simulate(shutdown_days=d, mode="agent")
            validated_sim = SimulationResponse.model_validate(sim_res)
            self.assertEqual(validated_sim.scenario.shutdown_days, d)
            self.assertEqual(validated_sim.scenario.horizon_days, 21)
            self.assertEqual(validated_sim.scenario.seed, 42)
            self.assertEqual(validated_sim.scenario.scenario_id, expected_scenario_id)

            # 2. Optimization endpoint
            opt_res = optimize(shutdown_days=d)
            validated_opt = OptimizationResponse.model_validate(opt_res)
            self.assertEqual(validated_opt.scenario.shutdown_days, d)
            self.assertEqual(validated_opt.scenario.horizon_days, 21)
            self.assertEqual(validated_opt.scenario.seed, 42)
            self.assertEqual(validated_opt.scenario.scenario_id, expected_scenario_id)

            # 3. Recovery endpoint
            rec_res = recovery(shutdown_days=d)
            validated_rec = RecoveryResponse.model_validate(rec_res)
            self.assertEqual(validated_rec.scenario.shutdown_days, d)
            self.assertEqual(validated_rec.scenario.horizon_days, 21)
            self.assertEqual(validated_rec.scenario.seed, 42)
            self.assertEqual(validated_rec.scenario.scenario_id, expected_scenario_id)

            # Check candidate scenarios
            for cand in validated_rec.candidates:
                self.assertEqual(cand.scenario_id, expected_scenario_id)

            # Check rankings match candidate scenarios
            for rank in validated_rec.rankings:
                self.assertIn(f"SD{d}", rank.candidate_id)

            # Check selection references the scenario
            self.assertEqual(validated_rec.selection.selected_candidate_id, f"CAND-AGENT-SD{d}")

            # 4. Comparison endpoint
            comp_res = compare_strategies(shutdown_days=d)
            validated_comp = ComparisonResponse.model_validate(comp_res)
            self.assertEqual(validated_comp.scenario.shutdown_days, d)
            self.assertEqual(validated_comp.scenario.horizon_days, 21)
            self.assertEqual(validated_comp.scenario.seed, 42)
            self.assertEqual(validated_comp.scenario.scenario_id, expected_scenario_id)

            # All three strategies under compare must share the exact same scenario
            for strat_sim in [validated_comp.strategies.reorder, validated_comp.strategies.optimized, validated_comp.strategies.agent]:
                self.assertEqual(strat_sim.scenario.shutdown_days, d)
                self.assertEqual(strat_sim.scenario.horizon_days, 21)
                self.assertEqual(strat_sim.scenario.seed, 42)
                self.assertEqual(strat_sim.scenario.scenario_id, expected_scenario_id)

    # ==========================================================================
    # 2. STRATEGY MODE RESOLUTION & CONFLICT REJECTION
    # ==========================================================================

    def test_simulate_strategy_mode_resolution(self):
        """
        Verify resolution of mode, legacy recovery_mode, and default behavior:
        - When mode is provided, it is used.
        - When legacy recovery_mode is provided, it is used.
        - When both are provided and agree, it succeeds.
        - When both are provided and disagree, an HTTP 422 is raised.
        - When neither is provided, defaults to 'agent'.
        """
        # Default behavior (both None) -> agent
        res_default = simulate(shutdown_days=7)
        self.assertEqual(res_default["strategy_info"]["id"], "agent")

        # mode only
        res_opt = simulate(shutdown_days=7, mode="optimized")
        self.assertEqual(res_opt["strategy_info"]["id"], "optimized")

        # recovery_mode only (legacy alias)
        res_reorder = simulate(shutdown_days=7, recovery_mode="reorder")
        self.assertEqual(res_reorder["strategy_info"]["id"], "reorder")

        # both provided and matching
        res_both_match = simulate(shutdown_days=7, mode="agent", recovery_mode="agent")
        self.assertEqual(res_both_match["strategy_info"]["id"], "agent")

        # both provided but conflicting -> HTTP 422
        with self.assertRaises(HTTPException) as cm:
            simulate(shutdown_days=7, mode="optimized", recovery_mode="reorder")
        self.assertEqual(cm.exception.status_code, 422)
        self.assertIn("Conflicting strategy modes", cm.exception.detail)

    # ==========================================================================
    # 3. WORKFLOW STATES & DECISION-SUPPORT GOVERNANCE
    # ==========================================================================

    def test_workflow_governance_states_truthfulness(self):
        """
        Verify that recovery output strictly maintains decision-support boundaries:
        - Candidate states: proposed -> validated against implemented constraints.
        - Selected candidate: chosen algorithmically, awaiting human review.
        - planner_approval_required = True
        - approved = False
        - governance_notice specifies no live ERP order dispatch.
        """
        rec_res = recovery(shutdown_days=7)
        rec = RecoveryResponse.model_validate(rec_res)

        # Recommendation boundaries
        self.assertTrue(rec.recommendation.planner_approval_required)
        self.assertFalse(rec.recommendation.approved)

        # Selection docket boundaries
        self.assertEqual(rec.selection.selection_status, "SELECTED")
        self.assertIn("No real-world purchase orders are dispatched", rec.selection.governance_notice)
        self.assertIn("human planner review and approval", rec.selection.governance_notice)

        # Validation status
        self.assertTrue(rec.validation.valid)
        self.assertEqual(rec.status, "awaiting_planner_approval")
        self.assertEqual(rec.validation.violation_count, 0)
        self.assertEqual(len(rec.validation.violations), 0)

        # Benchmark candidate validation
        reorder_cand = next(c for c in rec.candidates if c.strategy_id == "reorder")
        reorder_rank = next(r for r in rec.rankings if r.strategy_id == "reorder")
        self.assertFalse(reorder_cand.validation.valid)
        self.assertFalse(reorder_rank.selectable)
        self.assertIsNone(reorder_rank.rank)
        self.assertIsNone(reorder_rank.score)

    # ==========================================================================
    # 4. RECOVERY INTEGRITY & PROVENANCE VALIDATION
    # ==========================================================================

    def test_recovery_integrity_verification_function(self):
        """
        Verify that verify_recovery_integrity succeeds on valid coordinator results
        and raises ValueError on corrupted or mismatched candidate/ranking data.
        """
        res = coordinate_recovery(shutdown_days=7)
        # Should pass cleanly
        verify_recovery_integrity(res)

        # Test 1: Corrupt candidate metrics mismatch
        corrupt_res = coordinate_recovery(shutdown_days=7)
        corrupt_res["candidates"][0]["metrics"]["fill_rate"] = 999.9
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res)
        self.assertIn("Metric mismatch", str(cm.exception))

        # Test 2: Infeasible candidate incorrectly marked selectable
        corrupt_res2 = coordinate_recovery(shutdown_days=7)
        reorder_rank = next(r for r in corrupt_res2["rankings"] if r["strategy_id"] == "reorder")
        reorder_rank["selectable"] = True
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res2)
        self.assertIn("selectable=False", str(cm.exception))

        # Test 3: Selected candidate not found
        corrupt_res3 = coordinate_recovery(shutdown_days=7)
        corrupt_res3["selection"]["selected_candidate_id"] = "NON-EXISTENT"
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res3)
        self.assertIn("not found in candidate collection", str(cm.exception))

        # Test 4: Missing rankings (mismatched candidate/ranking count)
        corrupt_res4 = coordinate_recovery(shutdown_days=7)
        corrupt_res4["rankings"].pop()
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res4)
        self.assertIn("Mismatched candidate IDs", str(cm.exception))

        # Test 5: Duplicate candidate IDs
        corrupt_res5 = coordinate_recovery(shutdown_days=7)
        corrupt_res5["candidates"].append(dict(corrupt_res5["candidates"][0]))
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res5)
        self.assertIn("Duplicate candidate IDs", str(cm.exception))

        # Test 6: Mismatched scenario IDs
        corrupt_res6 = coordinate_recovery(shutdown_days=7)
        corrupt_res6["candidates"][0]["scenario_id"] = "SCEN-SD99-H21-S42"
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res6)
        self.assertIn("Scenario ID mismatch", str(cm.exception))

        # Test 7: Corrupted ranking score arithmetic
        corrupt_res7 = coordinate_recovery(shutdown_days=7)
        sel_rank = next(r for r in corrupt_res7["rankings"] if r["rank"] == 1)
        sel_rank["score"] = 99999.99
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res7)
        self.assertIn("Ranking score mismatch", str(cm.exception))

        # Test 8: Selected candidate not rank 1
        corrupt_res8 = coordinate_recovery(shutdown_days=7)
        sel_rank8 = next(r for r in corrupt_res8["rankings"] if r["candidate_id"] == corrupt_res8["selection"]["selected_candidate_id"])
        sel_rank8["rank"] = 2
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res8)
        self.assertIn("must be Rank 1", str(cm.exception))

        # Test 9: Selection strategy mismatch
        corrupt_res9 = coordinate_recovery(shutdown_days=7)
        corrupt_res9["selection"]["selected_strategy_id"] = "reorder"
        with self.assertRaises(ValueError) as cm:
            verify_recovery_integrity(corrupt_res9)
        self.assertIn("Selection strategy", str(cm.exception))

    # ==========================================================================
    # 5. ERROR HANDLING & EXCEPTION SANITIZATION
    # ==========================================================================

    def test_global_exception_handler_sanitization(self):
        """
        Verify that unexpected internal exceptions return HTTP 500 without leaking
        tracebacks, filesystem paths, or sensitive details.
        """
        import asyncio

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/recovery"

        secret_err = RuntimeError("SECRET_DB_PASSWORD=/var/secrets/key.pem: Connection failed")

        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(global_exception_handler(mock_request, secret_err))
        finally:
            loop.close()

        self.assertEqual(response.status_code, 500)
        # Check payload
        import json
        body = json.loads(response.body.decode())
        self.assertEqual(body["path"], "/api/recovery")
        self.assertIn("Internal server error occurred", body["detail"])
        # Ensure secret or paths are NOT present
        self.assertNotIn("SECRET_DB_PASSWORD", body["detail"])
        self.assertNotIn("/var/secrets/key.pem", body["detail"])

    # ==========================================================================
    # 6. CONTRACT BACKWARD COMPATIBILITY
    # ==========================================================================

    def test_all_endpoints_backward_compatibility(self):
        """
        Verify that all 6 endpoints return payloads that fully validate against
        their respective Pydantic response models, preserving established legacy fields.
        """
        # 1. /health
        h = health()
        validated_h = HealthResponse.model_validate(h)
        self.assertEqual(validated_h.status, "ok")

        # 2. /api/network
        net = get_network()
        validated_net = NetworkTopology.model_validate(net)
        self.assertEqual(len(validated_net.suppliers), 2)
        self.assertEqual(len(validated_net.products), 2)

        # 3. /api/simulate
        sim = simulate(shutdown_days=7)
        validated_sim = SimulationResponse.model_validate(sim)
        self.assertIsNotNone(validated_sim.metrics.fill_rate)
        self.assertIsNotNone(validated_sim.metrics.total_backorders)
        self.assertIsNotNone(validated_sim.metrics.total_landed_cost)
        self.assertEqual(len(validated_sim.daily_results), 21)
        self.assertTrue(any("SUP-01" in a for a in validated_sim.assumptions))

        # 4. /api/optimize
        opt = optimize(shutdown_days=7)
        validated_opt = OptimizationResponse.model_validate(opt)
        self.assertEqual(validated_opt.status, "OPTIMAL")
        self.assertIsNotNone(validated_opt.metrics.fill_rate)
        self.assertIsNotNone(validated_opt.metrics.total_landed_cost)

        # 5. /api/recovery
        rec = recovery(shutdown_days=7)
        validated_rec = RecoveryResponse.model_validate(rec)
        self.assertIsNotNone(validated_rec.agents.demand)
        self.assertIsNotNone(validated_rec.agents.inventory)
        self.assertIsNotNone(validated_rec.agents.supplier_risk)
        self.assertIsNotNone(validated_rec.agents.logistics)
        self.assertIsNotNone(validated_rec.candidates)
        self.assertIsNotNone(validated_rec.conflicts)
        self.assertIsNotNone(validated_rec.rankings)
        self.assertIsNotNone(validated_rec.selection)

        # 6. /api/compare
        comp = compare_strategies(shutdown_days=7)
        validated_comp = ComparisonResponse.model_validate(comp)
        self.assertIsNotNone(validated_comp.strategies.reorder)
        self.assertIsNotNone(validated_comp.strategies.optimized)
        self.assertIsNotNone(validated_comp.strategies.agent)

    def test_direct_python_invocation_and_query_defaults(self):
        """
        Verify that route functions can be called directly in Python without receiving
        raw FastAPI QueryParam objects as arguments or bypassing type validation:
        - get_approval() returns list cleanly without KeyError or QueryParam corruption.
        - get_approval(shutdown_days=0), get_approval(shutdown_days=True) raise 422.
        - simulate, optimize, recovery, compare reject boolean or out-of-range days with 422.
        """
        # 1. get_approval direct call without args
        records = get_approval()
        self.assertIsInstance(records, list)

        # 2. Rejection of invalid shutdown_days in get_approval
        for bad_val in [0, 15, -1, True, False]:
            with self.assertRaises(HTTPException) as cm:
                get_approval(shutdown_days=bad_val)
            self.assertEqual(cm.exception.status_code, 422)

        # 3. Rejection of boolean values across simulation/optimization/recovery/compare
        for fn in [simulate, optimize, recovery, compare_strategies]:
            with self.assertRaises(HTTPException) as cm:
                fn(shutdown_days=True)
            self.assertEqual(cm.exception.status_code, 422)

            with self.assertRaises(HTTPException) as cm:
                fn(shutdown_days=False)
            self.assertEqual(cm.exception.status_code, 422)

            with self.assertRaises(HTTPException) as cm:
                fn(shutdown_days=0)
            self.assertEqual(cm.exception.status_code, 422)

            with self.assertRaises(HTTPException) as cm:
                fn(shutdown_days=15)
            self.assertEqual(cm.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
