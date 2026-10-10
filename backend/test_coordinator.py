"""
SupplyShield AI — Coordinator & Multi-Agent Reasoning Test Suite (Phase B2)

Exhaustively verifies:
1. Dynamic recommendation percentages across shutdown durations 1, 3, 7, 10, 14.
2. Removal of hardcoded 91.5% defect and explicit distinction between Component A vs aggregate fill rate.
3. Recommendation resilience when metrics are missing or nullable.
4. Feasibility validation agreement between coordinator and simulator.
5. Combined daily supplier capacity violation detection across multiple orders.
6. Order rejection behavior (no receipts, no landed cost for rejected orders).
7. Demonstrative governance flags: planner_approval_required=True, approved=False.
8. Safe fallbacks on incomplete agent assessments or optimization failure.
9. Strict input validation in coordinate_recovery.
10. Full contract compatibility with Pydantic RecoveryResponse schema.
"""

import unittest
from coordinator import (
    coordinate_recovery,
    validate_order_plan,
    generate_recovery_recommendation,
    demand_agent,
    inventory_agent,
    supplier_risk_agent,
    logistics_agent,
)
from simulator import simulate_order_plan, NETWORK, HORIZON
from optimizer import optimize_plan
from schemas import RecoveryResponse


class TestCoordinatorStabilization(unittest.TestCase):
    """Phase B2 Coordinator, multi-agent reasoning, and recommendation verification."""

    DURATIONS = [1, 3, 7, 10, 14]

    # ==========================================================================
    # 1. DYNAMIC RECOMMENDATION PERCENTAGES ACROSS ALL DURATIONS
    # ==========================================================================

    def test_dynamic_recommendation_percentages_across_all_durations(self):
        """
        Verify that recommendation text dynamically reflects actual metrics
        for the scenario and does not retain the hardcoded 91.5% defect.
        """
        for d in self.DURATIONS:
            result = coordinate_recovery(shutdown_days=d)
            rec = result["recommendation"]
            self.assertIsNotNone(rec)

            summary = rec["summary"]
            opt_metrics = result["optimization"]["metrics"]
            p1_metrics = opt_metrics["product_breakdown"]["PROD-01"]
            overall_fill = opt_metrics["fill_rate"]
            p1_fill = p1_metrics["fill_rate"]

            # Format expected percentage strings
            expected_p1_str = f"{p1_fill:.1f}%"
            expected_overall_str = f"{overall_fill:.1f}%"

            # 1. Summary contains the actual Component A fill rate
            self.assertIn(
                expected_p1_str,
                summary,
                f"Summary for shutdown {d} did not contain Component A fill rate {expected_p1_str}",
            )

            # 2. Summary contains the actual aggregate network fill rate
            self.assertIn(
                expected_overall_str,
                summary,
                f"Summary for shutdown {d} did not contain aggregate fill rate {expected_overall_str}",
            )

            # 3. For 1-day shutdown, Component A fill rate is 96.3% - MUST NOT contain stale 91.5%
            if d == 1:
                self.assertIn("96.3%", summary)
                self.assertNotIn(
                    "91.5%",
                    summary,
                    "1-day shutdown recommendation incorrectly retained hardcoded 91.5%!",
                )

            # 4. Summary explicitly mentions the alternate vendor SUP-02 and re-engaging SUP-01
            self.assertIn("SUP-02", summary)
            self.assertIn("SUP-01", summary)
            self.assertIn(f"Day {d + 1}", summary)

            # 5. Governance flags
            self.assertTrue(rec["planner_approval_required"])
            self.assertFalse(rec["approved"])

    # ==========================================================================
    # 2. AGGREGATE VS PRODUCT-LEVEL FILL RATE DISTINCTION
    # ==========================================================================

    def test_aggregate_vs_product_level_fill_rate_distinction(self):
        """
        Verify that the recommendation summary explicitly distinguishes between
        Priority 1 component fill rate and aggregate network fill rate.
        """
        for d in [7, 10, 14]:
            result = coordinate_recovery(shutdown_days=d)
            summary = result["recommendation"]["summary"]

            # Component A should be clearly identified with Priority 1
            self.assertIn("Essential Component A (Priority 1)", summary)

            # Aggregate network fill rate should be explicitly labeled
            self.assertIn("aggregate network fill rate:", summary)

            # Component A achieves 91.5% while aggregate is significantly lower (85.4%, 81.9%, 77.1%)
            opt_metrics = result["optimization"]["metrics"]
            p1_fill = opt_metrics["product_breakdown"]["PROD-01"]["fill_rate"]
            overall_fill = opt_metrics["fill_rate"]

            self.assertGreater(
                p1_fill,
                overall_fill,
                f"Priority 1 fill rate should exceed aggregate fill rate at shutdown {d}",
            )

    # ==========================================================================
    # 3. RECOMMENDATION RESILIENCE ON MISSING OR NULLABLE METRICS
    # ==========================================================================

    def test_recommendation_with_missing_or_nullable_metrics(self):
        """
        Verify that generate_recovery_recommendation handles missing or None
        metric fields gracefully without crashing or fabricating numbers.
        """
        # Case 1: Empty metrics dictionary
        empty_opt = {
            "status": "OPTIMAL",
            "scenario": {"shutdown_days": 7, "horizon_days": 21},
            "metrics": {},
        }
        valid_val = {"valid": True, "violation_count": 0, "violations": []}

        rec = generate_recovery_recommendation(
            shutdown_days=7,
            optimization=empty_opt,
            validation=valid_val,
        )
        self.assertIn("projected target", rec["summary"])
        self.assertIn("N/A", rec["summary"])
        self.assertIn("unachieved within horizon", rec["summary"])
        self.assertTrue(rec["planner_approval_required"])
        self.assertFalse(rec["approved"])

        # Case 2: Explicit None values for metrics
        none_opt = {
            "status": "OPTIMAL",
            "scenario": {"shutdown_days": 7, "horizon_days": 21},
            "metrics": {
                "fill_rate": None,
                "recovery_day": None,
                "product_breakdown": None,
            },
        }
        rec_none = generate_recovery_recommendation(
            shutdown_days=7,
            optimization=none_opt,
            validation=valid_val,
        )
        self.assertIn("projected target", rec_none["summary"])
        self.assertIn("N/A", rec_none["summary"])

    # ==========================================================================
    # 4. INVALID PLANS NOT DESCRIBED AS VALID RECOVERY PLANS
    # ==========================================================================

    def test_invalid_plan_not_described_as_feasible(self):
        """
        If a plan fails validation, the coordinator recommendation must NOT describe it
        as feasible or claim 0 constraint violations.
        """
        dummy_opt = {
            "status": "OPTIMAL",
            "scenario": {"shutdown_days": 7, "horizon_days": 21},
            "metrics": {
                "fill_rate": 85.0,
                "product_breakdown": {"PROD-01": {"fill_rate": 90.0}},
            },
        }
        infeasible_val = {
            "valid": False,
            "violation_count": 2,
            "violations": [
                {"type": "supplier_capacity_exceeded"},
                {"type": "arrival_mismatch"},
            ],
        }

        rec = generate_recovery_recommendation(
            shutdown_days=7,
            optimization=dummy_opt,
            validation=infeasible_val,
        )

        # 1. Headline reflects review requirement
        self.assertIn("Requires Planner Review", rec["title"])

        # 2. Summary states plan failed feasibility with 2 violations
        self.assertIn("failed feasibility checks with 2 constraint violation(s)", rec["summary"])
        self.assertNotIn("verified mathematically feasible with 0 constraint violations", rec["summary"])

        # 3. Action plan directs resolving violations
        self.assertIn("Resolve 2 constraint violation(s)", rec["action_plan"])

        # 4. Governance flags preserved
        self.assertTrue(rec["planner_approval_required"])
        self.assertFalse(rec["approved"])

    # ==========================================================================
    # 5. COMBINED SUPPLIER CAPACITY VIOLATIONS
    # ==========================================================================

    def test_combined_supplier_capacity_across_multiple_orders(self):
        """
        Verify that multiple orders placed on the same day sharing a supplier
        trigger capacity violations when their SUM exceeds daily capacity,
        even if each order individually is below capacity.
        SUP-02 capacity: 60 units/day.
        Order 1: 35 units on Day 1.
        Order 2: 35 units on Day 1.
        Combined: 70 units > 60 units.
        """
        combined_orders = [
            {"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": 35, "arrival_day": 5},
            {"order_day": 1, "product": "PROD-02", "supplier": "SUP-02", "quantity": 35, "arrival_day": 5},
        ]

        # 1. Coordinator validation flags combined capacity exceeded
        val_res = validate_order_plan(combined_orders, shutdown_days=7)
        self.assertFalse(val_res["valid"])
        self.assertEqual(val_res["violation_count"], 1)
        self.assertEqual(val_res["violations"][0]["type"], "supplier_capacity_exceeded")
        self.assertEqual(val_res["violations"][0]["used"], 70)
        self.assertEqual(val_res["violations"][0]["capacity"], 60)

        # 2. Simulator flags violation and rejects the order exceeding capacity
        sim_res = simulate_order_plan(combined_orders, shutdown_days=7)
        self.assertEqual(sim_res["metrics"]["constraint_violations"], 1)
        self.assertEqual(sim_res["violations"][0]["type"], "supplier_capacity_exceeded")

        # The accepted order was 35 units; the second order (35 units) was rejected
        # Landed cost on SUP-02 is 16.5 per unit. Accepted cost = 35 * 16.5 = 577.5
        self.assertEqual(sim_res["metrics"]["total_landed_cost"], 577.5)

    # ==========================================================================
    # 6. AGREEMENT BETWEEN COORDINATOR VALIDATION & SIMULATOR ACCEPTANCE
    # ==========================================================================

    def test_coordinator_and_simulator_agreement_on_invalid_orders(self):
        """
        Verify that coordinator validation and simulator engine agree on
        rejection and violation classification for all invalid candidate order types.
        """
        test_cases = [
            # 1. Shutdown violation
            {"order": {"order_day": 2, "product": "PROD-01", "supplier": "SUP-01", "quantity": 40, "arrival_day": 4}, "type": "supplier_shutdown_violation"},
            # 2. Unknown supplier
            {"order": {"order_day": 1, "product": "PROD-01", "supplier": "SUP-99", "quantity": 10, "arrival_day": 3}, "type": "unknown_supplier"},
            # 3. Unknown product
            {"order": {"order_day": 1, "product": "PROD-99", "supplier": "SUP-02", "quantity": 10, "arrival_day": 5}, "type": "unknown_product"},
            # 4. Non-positive integer quantity (0)
            {"order": {"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": 0, "arrival_day": 5}, "type": "invalid_quantity"},
            # 5. Boolean quantity (True)
            {"order": {"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": True, "arrival_day": 5}, "type": "invalid_quantity"},
            # 6. Float quantity (10.5)
            {"order": {"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10.5, "arrival_day": 5}, "type": "invalid_quantity"},
            # 7. Out-of-bounds order day (25)
            {"order": {"order_day": 25, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10, "arrival_day": 29}, "type": "invalid_order_day"},
            # 8. Arrival mismatch (lead time 4, claims arrival on day 3)
            {"order": {"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10, "arrival_day": 3}, "type": "arrival_mismatch"},
        ]

        for tc in test_cases:
            order = tc["order"]
            expected_type = tc["type"]

            # Coordinator validator
            coord_val = validate_order_plan([order], shutdown_days=7)
            self.assertFalse(coord_val["valid"], f"Coordinator failed to reject {order}")
            coord_types = [v["type"] for v in coord_val["violations"]]
            self.assertIn(expected_type, coord_types)

            # Simulator
            sim_res = simulate_order_plan([order], shutdown_days=7)
            self.assertEqual(sim_res["metrics"]["constraint_violations"], 1, f"Simulator failed to reject {order}")
            sim_types = [v["type"] for v in sim_res["violations"]]
            self.assertIn(expected_type, sim_types)
            # Rejected order must not create landed cost
            self.assertEqual(sim_res["metrics"]["total_landed_cost"], 0.0)

    # ==========================================================================
    # 7. SPECIALIST AGENT REPRODUCIBILITY & ISOLATION
    # ==========================================================================

    def test_specialist_agent_outputs_and_reproducibility(self):
        """
        Verify each specialist agent produces structured, consistent, deterministic proposals
        governed by actual network parameters.
        """
        net = NETWORK

        # 1. Demand Agent: Prioritizes PROD-01 (Priority 1) over PROD-02 (Priority 2)
        d_props = demand_agent(net)
        self.assertEqual(len(d_props), 2)
        p1 = next(p for p in d_props if p["product"] == "PROD-01")
        p2 = next(p for p in d_props if p["product"] == "PROD-02")
        self.assertEqual(p1["criticality"], "CRITICAL (Tier 1)")
        self.assertEqual(p2["criticality"], "STANDARD (Tier 2)")
        self.assertEqual(p1["priority"], 1)
        self.assertEqual(p2["priority"], 2)

        # 2. Inventory Agent: Accurately projects stockout day from initial stock & burn rate
        i_props = inventory_agent(net)
        self.assertEqual(len(i_props), 2)
        # PROD-01: 100 stock / 45 burn = 2.22 days -> Day 3 stockout
        p1_inv = next(p for p in i_props if p["product"] == "PROD-01")
        self.assertEqual(p1_inv["stockout_day"], 3)
        self.assertEqual(p1_inv["risk"], "HIGH")

        # 3. Supplier Risk Agent: Flags SUP-01 during shutdown, identifies SUP-02 backup
        r_props = supplier_risk_agent(net, shutdown_days=7)
        self.assertEqual(len(r_props), 2)
        sup1 = next(p for p in r_props if p["supplier"] == "SUP-01")
        sup2 = next(p for p in r_props if p["supplier"] == "SUP-02")
        self.assertEqual(sup1["risk"], "CRITICAL")
        self.assertEqual(sup2["risk"], "AVAILABLE")

        # 4. Logistics Agent: Identifies SUP-02 lead time 4 days & earliest arrival Day 5
        l_props = logistics_agent(net, shutdown_days=7)
        sup2_log = next(p for p in l_props if p["supplier"] == "SUP-02")
        self.assertEqual(sup2_log["lead_time_days"], 4)
        self.assertEqual(sup2_log["earliest_possible_arrival_day"], 5)

        # Repeat run produces bit-for-bit identical results
        self.assertEqual(demand_agent(net), d_props)
        self.assertEqual(inventory_agent(net), i_props)
        self.assertEqual(supplier_risk_agent(net, shutdown_days=7), r_props)
        self.assertEqual(logistics_agent(net, shutdown_days=7), l_props)

    # ==========================================================================
    # 8. COORDINATOR INPUT VALIDATION
    # ==========================================================================

    def test_coordinate_recovery_input_validation(self):
        """Verify coordinate_recovery rejects invalid, non-integer, or out-of-bounds inputs."""
        invalid_inputs = [0, -1, 15, 20, True, False, "7", None, 3.5]

        for inv in invalid_inputs:
            with self.assertRaises(ValueError, msg=f"coordinate_recovery should reject {inv!r}"):
                coordinate_recovery(shutdown_days=inv)

    # ==========================================================================
    # 9. RECOVERY RESPONSE CONTRACT VALIDATION
    # ==========================================================================

    def test_recovery_response_contract_across_all_durations(self):
        """Verify real coordinate_recovery output validates against Pydantic RecoveryResponse."""
        for d in self.DURATIONS:
            res = coordinate_recovery(shutdown_days=d)
            validated = RecoveryResponse.model_validate(res)

            self.assertEqual(validated.scenario.shutdown_days, d)
            self.assertEqual(validated.status, "awaiting_planner_approval")
            self.assertTrue(validated.validation.valid)
            self.assertEqual(validated.validation.violation_count, 0)
            self.assertIsNotNone(validated.recommendation)
            self.assertTrue(validated.recommendation.planner_approval_required)
            self.assertFalse(validated.recommendation.approved)


# ==============================================================================
# PHASE B4: AUDITABLE PLAN SELECTION & MULTI-CANDIDATE RECOVERY TESTS
# ==============================================================================

class TestPhaseB4AuditablePlanSelection(unittest.TestCase):
    """
    Exhaustive verification of Phase B4 Recovery Coordinator requirements:
    1. Multi-candidate generation (agent, optimized, reorder)
    2. Candidate feasibility validation before ranking
    3. Simulation-derived operational metrics provenance
    4. Deterministic multi-criteria candidate ranking
    5. Structured conflict identification across agent findings
    6. Traceable selection docket and trade-off explanations
    7. Invalidation handling (infeasible candidates excluded from selection)
    8. Coverage across short (1-day) and extended (7, 14-day) shutdowns
    9. Repeat-run determinism
    10. Full Pydantic contract compliance
    """

    DURATIONS = [1, 7, 14]

    def test_multi_candidate_generation_and_strategy_provenance(self):
        """Verify that coordinator generates 3 genuinely distinct candidates reflecting real strategies."""
        res = coordinate_recovery(shutdown_days=7)
        candidates = res.get("candidates")
        self.assertIsNotNone(candidates)
        self.assertEqual(len(candidates), 3)

        cand_map = {c["strategy_id"]: c for c in candidates}
        self.assertIn("agent", cand_map)
        self.assertIn("optimized", cand_map)
        self.assertIn("reorder", cand_map)

        # Candidate A: Agent-assisted
        cand_a = cand_map["agent"]
        self.assertEqual(cand_a["candidate_id"], "CAND-AGENT-SD7")
        self.assertEqual(cand_a["objective_mode"], "CP-SAT MIP (Demand Priority Weighted)")
        self.assertEqual(cand_a["product_weights"]["PROD-01"], 2.0)
        self.assertEqual(cand_a["product_weights"]["PROD-02"], 1.0)
        self.assertEqual(cand_a["generation_status"], "SUCCESS")
        self.assertTrue(len(cand_a["orders"]) > 0)

        # Candidate B: Optimization-only
        cand_b = cand_map["optimized"]
        self.assertEqual(cand_b["candidate_id"], "CAND-OPT-SD7")
        self.assertEqual(cand_b["objective_mode"], "CP-SAT MIP (Uniform Cost Minimization)")
        self.assertEqual(cand_b["product_weights"]["PROD-01"], 1.0)
        self.assertEqual(cand_b["product_weights"]["PROD-02"], 1.0)
        self.assertEqual(cand_b["generation_status"], "SUCCESS")
        self.assertTrue(len(cand_b["orders"]) > 0)

        # Candidate C: Reorder baseline
        cand_c = cand_map["reorder"]
        self.assertEqual(cand_c["candidate_id"], "CAND-REORDER-SD7")
        self.assertIn("Greedy Target Stock", cand_c["objective_mode"])
        self.assertEqual(cand_c["generation_status"], "SUCCESS")
        self.assertTrue(len(cand_c["orders"]) > 0)

    def test_feasibility_validation_before_ranking(self):
        """Verify every candidate is validated against implemented constraints before ranking."""
        res = coordinate_recovery(shutdown_days=7)
        candidates = res["candidates"]
        cand_map = {c["strategy_id"]: c for c in candidates}

        # Candidates A and B satisfy all constraints
        for strat in ["agent", "optimized"]:
            c = cand_map[strat]
            val = c.get("validation")
            self.assertIsNotNone(val)
            self.assertTrue(val["valid"], f"Candidate {c['candidate_id']} unexpectedly failed validation")
            self.assertEqual(val["violation_count"], 0)
            self.assertEqual(len(val["violations"]), 0)

        # Candidate C (naive reorder) attempts orders to SUP-01 during shutdown and is flagged
        cand_c = cand_map["reorder"]
        val_c = cand_c.get("validation")
        self.assertIsNotNone(val_c)
        self.assertFalse(val_c["valid"])
        self.assertEqual(val_c["violation_count"], 14)
        self.assertTrue(all(v["type"] == "supplier_shutdown_violation" for v in val_c["violations"]))

    def test_candidate_simulation_and_metrics_provenance(self):
        """Verify candidate metrics are derived strictly from shared simulation engine execution."""
        for d in self.DURATIONS:
            res = coordinate_recovery(shutdown_days=d)
            for c in res["candidates"]:
                m = c.get("metrics")
                self.assertIsNotNone(m, f"Candidate {c['candidate_id']} has null metrics")
                self.assertIn("fill_rate", m)
                self.assertIn("total_landed_cost", m)
                self.assertIn("product_breakdown", m)

                # Reconcile metrics against direct simulator execution
                direct_sim = simulate_order_plan(
                    orders=c["orders"],
                    shutdown_days=d,
                    recovery_mode=c["strategy_id"],
                )
                self.assertAlmostEqual(m["fill_rate"], direct_sim["metrics"]["fill_rate"], places=2)
                self.assertAlmostEqual(m["total_landed_cost"], direct_sim["metrics"]["total_landed_cost"], places=2)

    def test_deterministic_multi_criteria_ranking(self):
        """Verify deterministic ranking order, criteria evaluation, and comparative notes."""
        res = coordinate_recovery(shutdown_days=7)
        rankings = res.get("rankings")
        self.assertIsNotNone(rankings)
        self.assertEqual(len(rankings), 3)

        # Under 7-day shutdown:
        # Rank 1: Agent (P1 fill rate 91.53%, Agg 85.42%) -> selectable=True, rank=1
        # Rank 2: Optimized (P1 fill rate 85.19%, Agg 85.42%) -> selectable=True, rank=2
        # Infeasible Benchmark: Reorder -> selectable=False, rank=None, score=None
        self.assertEqual(rankings[0]["rank"], 1)
        self.assertEqual(rankings[0]["strategy_id"], "agent")
        self.assertTrue(rankings[0]["selectable"])
        self.assertIsNotNone(rankings[0]["score"])
        self.assertIn("Rank 1", rankings[0]["comparison_notes"])

        self.assertEqual(rankings[1]["rank"], 2)
        self.assertEqual(rankings[1]["strategy_id"], "optimized")
        self.assertTrue(rankings[1]["selectable"])
        self.assertIsNotNone(rankings[1]["score"])
        self.assertIn("Rank 2", rankings[1]["comparison_notes"])

        self.assertIsNone(rankings[2]["rank"])
        self.assertEqual(rankings[2]["strategy_id"], "reorder")
        self.assertFalse(rankings[2]["selectable"])
        self.assertIsNone(rankings[2]["score"])
        self.assertIn("Infeasible benchmark", rankings[2]["comparison_notes"])

        # Check scores decrease strictly among selectable candidates
        self.assertGreater(rankings[0]["score"], rankings[1]["score"])

    def test_conflict_identification_across_agent_findings(self):
        """Verify structured conflict records identify operational tensions across specialists."""
        res = coordinate_recovery(shutdown_days=7)
        conflicts = res.get("conflicts")
        self.assertIsNotNone(conflicts)
        self.assertEqual(len(conflicts), 3)

        c_types = {c["conflict_id"]: c for c in conflicts}

        # 1. Capacity vs Demand Allocation
        self.assertIn("CAPACITY_VS_DEMAND_ALLOCATION", c_types)
        c1 = c_types["CAPACITY_VS_DEMAND_ALLOCATION"]
        self.assertEqual(c1["status"], "ACCEPTED_TRADEOFF")
        self.assertEqual(c1["severity"], "HIGH")
        self.assertIn("SUP-02", c1["affected_entity"])
        self.assertIn("Demand Intelligence Agent", c1["agents_involved"])
        self.assertIn("Supplier Risk Agent", c1["agents_involved"])

        # 2. Transit Lead Time Gap
        self.assertIn("TRANSIT_LEAD_TIME_DEPLETION_GAP", c_types)
        c2 = c_types["TRANSIT_LEAD_TIME_DEPLETION_GAP"]
        self.assertEqual(c2["status"], "ACCEPTED_TRADEOFF")
        self.assertIn("Inventory Intelligence Agent", c2["agents_involved"])
        self.assertIn("Logistics Optimization Agent", c2["agents_involved"])

        # 3. Supplier Outage Restriction
        self.assertIn("SUPPLIER_OUTAGE_RESTRICTION", c_types)
        c3 = c_types["SUPPLIER_OUTAGE_RESTRICTION"]
        self.assertEqual(c3["status"], "RESOLVED")

    def test_traceable_selection_docket_and_governance(self):
        """Verify auditable selection rationale, trade-offs, rejected alternatives, and governance."""
        res = coordinate_recovery(shutdown_days=7)
        sel = res.get("selection")
        self.assertIsNotNone(sel)

        self.assertEqual(sel["selected_candidate_id"], "CAND-AGENT-SD7")
        self.assertEqual(sel["selected_strategy_id"], "agent")
        self.assertEqual(sel["selection_status"], "SELECTED")
        self.assertIn("Selected Priority-Weighted Contingency Recovery", sel["selection_rationale"])
        self.assertIn("91.5%", sel["selection_rationale"])

        # Trade-offs accepted
        self.assertTrue(len(sel["tradeoffs_accepted"]) >= 3)
        self.assertTrue(any("Component B" in t for t in sel["tradeoffs_accepted"]))
        self.assertTrue(any("transit" in t.lower() for t in sel["tradeoffs_accepted"]))

        # Rejected alternatives
        self.assertEqual(len(sel["rejected_alternatives"]), 2)
        rejected_strats = {r["strategy_id"] for r in sel["rejected_alternatives"]}
        self.assertEqual(rejected_strats, {"optimized", "reorder"})

        # Unresolved risks
        self.assertTrue(len(sel["unresolved_risks"]) >= 3)
        self.assertTrue(any("ERP" in r or "vendor" in r.lower() for r in sel["unresolved_risks"]))

        # Governance notices
        self.assertIn("No real-world purchase orders are dispatched", sel["governance_notice"])
        self.assertIn("planner review", sel["governance_notice"].lower())

    def test_invalid_candidate_excluded_from_selection(self):
        """Verify that infeasible candidates are marked unselectable, excluded from rank, and cannot be chosen."""
        from coordinator import rank_candidates, select_and_explain_plan

        bad_candidate = {
            "candidate_id": "CAND-BAD-ORDERS",
            "strategy_id": "agent",
            "name": "Corrupted Candidate",
            "orders": [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-01", "quantity": 100, "arrival_day": 3}],
            "validation": {
                "valid": False,
                "violation_count": 1,
                "violations": [{"type": "supplier_shutdown_violation"}],
            },
            "metrics": None,
        }

        # 1. Ranking marks bad candidate unselectable with no rank
        rankings = rank_candidates([bad_candidate])
        self.assertEqual(len(rankings), 1)
        self.assertFalse(rankings[0]["selectable"])
        self.assertIsNone(rankings[0]["rank"])
        self.assertIsNone(rankings[0]["score"])
        self.assertIn("BENCHMARK ONLY", rankings[0]["criteria_summary"])

        # 2. Selection returns BLOCKED state when all candidates fail
        sel = select_and_explain_plan(
            ranked_candidates=rankings,
            candidates_by_id={"CAND-BAD-ORDERS": bad_candidate},
            conflicts=[],
            shutdown_days=7,
        )
        self.assertEqual(sel["selection_status"], "BLOCKED")
        self.assertIsNone(sel["selected_candidate_id"])
        self.assertIn("failed feasibility validation", sel["selection_rationale"])
        self.assertIn("Resolve blocking constraint violations", sel["planner_action_required"])

    def test_short_and_extended_shutdown_coverage(self):
        """Verify coordinator behavior across shutdown durations 1, 7, and 14."""
        for d in self.DURATIONS:
            res = coordinate_recovery(shutdown_days=d)
            self.assertEqual(res["status"], "awaiting_planner_approval")
            self.assertEqual(len(res["candidates"]), 3)
            self.assertEqual(len(res["rankings"]), 3)
            self.assertEqual(res["selection"]["selection_status"], "SELECTED")

            # Check specific duration properties
            if d == 1:
                self.assertEqual(res["selection"]["selected_candidate_id"], "CAND-AGENT-SD1")
                # At D=1, both agent and optimized achieve 96.3% on P1 and 96.1% overall
                rank1 = res["rankings"][0]
                self.assertEqual(rank1["strategy_id"], "agent")
                self.assertEqual(rank1["p1_fill_rate"], 96.3)
            elif d == 7:
                self.assertEqual(res["selection"]["selected_candidate_id"], "CAND-AGENT-SD7")
                self.assertEqual(res["rankings"][0]["p1_fill_rate"], 91.53)
            elif d == 14:
                self.assertEqual(res["selection"]["selected_candidate_id"], "CAND-AGENT-SD14")
                self.assertEqual(res["rankings"][0]["p1_fill_rate"], 91.53)
                # Optimized dropped to 72.49%
                self.assertEqual(res["rankings"][1]["p1_fill_rate"], 72.49)

    def test_repeat_run_determinism(self):
        """Verify identical inputs produce bit-for-bit identical candidate plans, metrics, and rankings."""
        res1 = coordinate_recovery(shutdown_days=7)
        res2 = coordinate_recovery(shutdown_days=7)

        self.assertEqual(res1["status"], res2["status"])
        self.assertEqual(len(res1["candidates"]), len(res2["candidates"]))

        for c1, c2 in zip(res1["candidates"], res2["candidates"]):
            self.assertEqual(c1["candidate_id"], c2["candidate_id"])
            self.assertEqual(c1["orders"], c2["orders"])
            self.assertEqual(c1["validation"], c2["validation"])
            self.assertEqual(c1["metrics"], c2["metrics"])

        for r1, r2 in zip(res1["rankings"], res2["rankings"]):
            self.assertEqual(r1["candidate_id"], r2["candidate_id"])
            self.assertEqual(r1["rank"], r2["rank"])
            self.assertEqual(r1["score"], r2["score"])

        self.assertEqual(res1["selection"]["selected_candidate_id"], res2["selection"]["selected_candidate_id"])
        self.assertEqual(res1["selection"]["selection_rationale"], res2["selection"]["selection_rationale"])

    def test_pydantic_recovery_response_schema_validation_full_contracts(self):
        """Verify coordinate_recovery output validates against RecoveryResponse with full B4 extensions."""
        for d in self.DURATIONS:
            res = coordinate_recovery(shutdown_days=d)
            val = RecoveryResponse.model_validate(res)

            self.assertEqual(val.scenario.shutdown_days, d)
            self.assertEqual(val.status, "awaiting_planner_approval")
            self.assertIsNotNone(val.candidates)
            self.assertEqual(len(val.candidates), 3)
            self.assertIsNotNone(val.conflicts)
            self.assertEqual(len(val.conflicts), 3)
            self.assertIsNotNone(val.rankings)
            self.assertEqual(len(val.rankings), 3)
            self.assertIsNotNone(val.selection)
            self.assertEqual(val.selection.selection_status, "SELECTED")
            self.assertTrue(val.recommendation.planner_approval_required)
            self.assertFalse(val.recommendation.approved)

    def test_candidate_validity_selectability_rank_invariants(self):
        """
        Regression invariant: candidate validity, selectability, score, and rank cannot contradict one another.
        Enforces:
        - valid == False ==> selectable == False, rank is None, score is None
        - selectable == True ==> valid == True, rank is int >= 1, score is float
        - selected candidate in selection is selectable == True and rank == 1
        - selected candidate must exist in ranked list
        """
        for d in self.DURATIONS:
            res = coordinate_recovery(shutdown_days=d)
            cands = {c["candidate_id"]: c for c in res["candidates"]}
            rankings = res["rankings"]
            sel = res["selection"]

            for r in rankings:
                cid = r["candidate_id"]
                c = cands[cid]
                is_valid = c["validation"]["valid"]

                if not is_valid:
                    self.assertFalse(r["selectable"], f"Candidate {cid} is invalid but marked selectable")
                    self.assertIsNone(r["rank"], f"Candidate {cid} is invalid but received rank {r['rank']}")
                    self.assertIsNone(r["score"], f"Candidate {cid} is invalid but received score {r['score']}")
                    self.assertIn("BENCHMARK ONLY", r["criteria_summary"])
                else:
                    self.assertTrue(r["selectable"], f"Candidate {cid} is valid but marked unselectable")
                    self.assertIsInstance(r["rank"], int)
                    self.assertGreaterEqual(r["rank"], 1)
                    self.assertIsInstance(r["score"], (int, float))

            # Selected candidate verification
            if sel["selection_status"] == "SELECTED":
                top_id = sel["selected_candidate_id"]
                top_r = next(r for r in rankings if r["candidate_id"] == top_id)
                self.assertTrue(top_r["selectable"])
                self.assertEqual(top_r["rank"], 1)
                self.assertIsNotNone(top_r["score"])
                top_c = cands[top_id]
                self.assertTrue(top_c["validation"]["valid"])

    def test_scenario_specific_transit_conflicts_all_durations(self):
        """
        Verify scenario-specific derivation of TRANSIT_LEAD_TIME_DEPLETION_GAP:
        - For 1-day shutdown: SUP-01 ordered Day 2 arrives Day 4; uncovered gap is strictly Day 3.
        - For extended shutdowns (3, 7, 14): SUP-02 ordered Day 1 arrives Day 5; uncovered gap is Days 3-4.
        """
        for d in [1, 3, 7, 10, 14]:
            res = coordinate_recovery(shutdown_days=d)
            conflicts = {c["conflict_id"]: c for c in res["conflicts"]}
            self.assertIn("TRANSIT_LEAD_TIME_DEPLETION_GAP", conflicts)
            c_gap = conflicts["TRANSIT_LEAD_TIME_DEPLETION_GAP"]
            self.assertEqual(c_gap["status"], "ACCEPTED_TRADEOFF")
            self.assertEqual(c_gap["severity"], "HIGH")

            if d == 1:
                self.assertEqual(c_gap["affected_entity"], "Network Inventory (Day 3)")
                self.assertIn("order_day 2 + lead_time 2", c_gap["evidence"])
                self.assertIn("Day 3", c_gap["consequence"])
                self.assertNotIn("Days 3-4", c_gap["consequence"])
            else:
                self.assertEqual(c_gap["affected_entity"], "Network Inventory (Days 3-4)")
                self.assertIn("order_day 1 + lead_time 4", c_gap["evidence"])
                self.assertIn("Days 3-4", c_gap["consequence"])

    def test_inbound_orders_resolve_transit_gap(self):
        """
        Verify that confirmed inbound receipts covering Days 3-4 transition
        TRANSIT_LEAD_TIME_DEPLETION_GAP to status 'RESOLVED' with severity 'LOW'.
        """
        sufficient_inbound = [
            {"product": "PROD-01", "quantity": 100, "arrival_day": 3, "order_day": 1, "supplier": "SUP-01"},
            {"product": "PROD-02", "quantity": 100, "arrival_day": 3, "order_day": 1, "supplier": "SUP-01"},
            {"product": "PROD-01", "quantity": 100, "arrival_day": 4, "order_day": 1, "supplier": "SUP-01"},
            {"product": "PROD-02", "quantity": 100, "arrival_day": 4, "order_day": 1, "supplier": "SUP-01"},
        ]
        res = coordinate_recovery(shutdown_days=7, inbound_orders=sufficient_inbound)
        conflicts = {c["conflict_id"]: c for c in res["conflicts"]}
        self.assertIn("TRANSIT_LEAD_TIME_DEPLETION_GAP", conflicts)
        c_gap = conflicts["TRANSIT_LEAD_TIME_DEPLETION_GAP"]
        self.assertEqual(c_gap["status"], "RESOLVED")
        self.assertEqual(c_gap["severity"], "LOW")
        self.assertEqual(c_gap["affected_entity"], "Network Inventory (Covered by Inbound Receipts)")
        self.assertIn("Confirmed inbound pipeline receipts", c_gap["evidence"])

    def test_candidate_c_benchmark_tracking_across_durations(self):
        """
        Verify Candidate C (reorder) proposed orders, shutdown violations,
        and simulation charging across shutdown durations 1, 7, and 14.
        """
        expected_violations = {1: 2, 7: 14, 14: 28}
        for d in [1, 7, 14]:
            res = coordinate_recovery(shutdown_days=d)
            c = next(x for x in res["candidates"] if x["strategy_id"] == "reorder")
            r = next(x for x in res["rankings"] if x["strategy_id"] == "reorder")

            # 37 total proposed orders
            self.assertEqual(len(c["orders"]), 37)

            # Shutdown orders match 2 * d
            outage_orders = [o for o in c["orders"] if o["supplier"] == "SUP-01" and o["order_day"] <= d]
            self.assertEqual(len(outage_orders), expected_violations[d])

            # Validation flags all outage orders
            self.assertFalse(c["validation"]["valid"])
            self.assertEqual(c["validation"]["violation_count"], expected_violations[d])

            # Candidate C is unselectable benchmark
            self.assertFalse(r["selectable"])
            self.assertIsNone(r["rank"])
            self.assertIsNone(r["score"])

            # Ground truth simulation charges INR 0 for rejected orders
            sim = simulate_order_plan(orders=c["orders"], shutdown_days=d, recovery_mode="reorder")
            self.assertEqual(sim["metrics"]["constraint_violations"], expected_violations[d])
            self.assertEqual(c["metrics"]["total_landed_cost"], sim["metrics"]["total_landed_cost"])

    def test_exact_landed_cost_reconciliation_all_candidates(self):
        """
        Verify exact mathematical reconciliation for all candidates across D in {1, 7, 14}:
        total_landed_cost = sum(accepted_quantity * unit_landed_rate) = sum(daily landed_cost)
        Where unit landed rate is:
          - SUP-01: INR 10.00 (proc) + INR 2.00 (freight) = INR 12.00/unit
          - SUP-02: INR 13.00 (proc) + INR 3.50 (freight) = INR 16.50/unit
        """
        expected_costs = {
            "agent": {1: 17280.0, 7: 16470.0, 14: 16680.0},
            "optimized": {1: 17280.0, 7: 16470.0, 14: 16680.0},
            "reorder": {1: 17820.0, 7: 12060.0, 14: 5340.0},
        }

        for d in [1, 7, 14]:
            res = coordinate_recovery(shutdown_days=d)
            for c in res["candidates"]:
                strat = c["strategy_id"]
                orders = c["orders"]
                metrics_cost = c["metrics"]["total_landed_cost"]

                # 1. Order-level accepted quantity and cost sum
                accepted_order_cost = 0.0
                accepted_by_sup = {"SUP-01": 0, "SUP-02": 0}
                for o in orders:
                    sid = o["supplier"]
                    qty = o["quantity"]
                    day = o["order_day"]
                    is_rejected = (sid == "SUP-01" and day <= d)
                    rate = 12.0 if sid == "SUP-01" else 16.5
                    if not is_rejected:
                        accepted_order_cost += qty * rate
                        accepted_by_sup[sid] += qty

                # 2. Daily simulation cost sum
                sim = simulate_order_plan(orders=orders, shutdown_days=d, recovery_mode=strat)
                daily_cost_sum = sum(day_r.get("landed_cost", 0.0) for day_r in sim["daily_results"])

                # 3. All three cost equations must reconcile exactly
                self.assertEqual(accepted_order_cost, metrics_cost)
                self.assertEqual(daily_cost_sum, metrics_cost)
                self.assertEqual(sim["metrics"]["total_landed_cost"], metrics_cost)
                self.assertEqual(metrics_cost, expected_costs[strat][d])

    def test_rejected_orders_produce_zero_receipts_and_zero_cost(self):
        """
        Verify that rejected orders during supplier shutdown add strictly 0 units
        to inventory and incur strictly INR 0.00 landed cost.
        """
        for d in [1, 7, 14]:
            res = coordinate_recovery(shutdown_days=d)
            c_reorder = next(c for c in res["candidates"] if c["strategy_id"] == "reorder")
            sim = simulate_order_plan(orders=c_reorder["orders"], shutdown_days=d, recovery_mode="reorder")

            # Check rejected order proposals in daily simulation results
            rejected_proposals = [
                prop for day_r in sim["daily_results"]
                for prop in day_r.get("orders", [])
                if prop.get("status") == "rejected_supplier_shutdown"
            ]
            self.assertEqual(len(rejected_proposals), 2 * d)
            for prop in rejected_proposals:
                self.assertEqual(prop.get("quantity", 0), 0)

            # Rejected orders are never placed in pipeline, resulting in 0 deliveries on arrival days
            # Total delivered quantity matches accepted orders sum exactly
            total_delivered = sum(
                arr.get("quantity", 0) for day_r in sim["daily_results"]
                for arr in day_r.get("arrivals", [])
            )
            total_accepted_qty = sum(
                o["quantity"] for o in c_reorder["orders"]
                if not (o["supplier"] == "SUP-01" and o["order_day"] <= d)
            )
            self.assertEqual(total_delivered, total_accepted_qty)

    def test_candidate_metric_provenance_and_plan_consistency(self):
        """
        Verify that candidate metrics are derived strictly from that specific candidate's
        order plan and not cross-contaminated between candidates.
        """
        for d in [1, 7, 14]:
            res = coordinate_recovery(shutdown_days=d)
            for c in res["candidates"]:
                strat = c["strategy_id"]
                orders = c["orders"]
                m = c["metrics"]

                # Independent direct simulation of this exact plan
                direct_sim = simulate_order_plan(orders=orders, shutdown_days=d, recovery_mode=strat)
                direct_m = direct_sim["metrics"]

                self.assertEqual(m["fill_rate"], direct_m["fill_rate"])
                self.assertEqual(m["total_landed_cost"], direct_m["total_landed_cost"])
                self.assertEqual(m["recovery_day"], direct_m["recovery_day"])
                self.assertEqual(
                    m["product_breakdown"]["PROD-01"]["fill_rate"],
                    direct_m["product_breakdown"]["PROD-01"]["fill_rate"],
                )
                self.assertEqual(
                    m["product_breakdown"]["PROD-02"]["fill_rate"],
                    direct_m["product_breakdown"]["PROD-02"]["fill_rate"],
                )

    def test_ranking_scores_match_actual_ranking_formula(self):
        """
        Verify that ranking scores published in candidate rankings exactly match
        the documented deterministic scoring formula derived from full-precision ratios:
          P1 fill percentage = P1 fulfilled / P1 demand * 100
          Aggregate fill percentage = total fulfilled / total demand * 100
          Recovery bonus = max(0, 22 - recovery_day) * 10.0 if recovery_day else 0.0
          Cost penalty = total landed cost * 0.01
          score = round((p1_pct * 100.0) + (agg_pct * 50.0) + recovery_bonus - cost_penalty, 2)
        """
        expected_agent_scores = {1: 14443.38, 7: 13379.57, 14: 12890.81}
        expected_opt_scores = {1: 14443.38, 7: 12744.65, 14: 10986.04}

        for d in [1, 3, 7, 10, 14]:
            res = coordinate_recovery(shutdown_days=d)
            cand_map = {c["candidate_id"]: c for c in res["candidates"]}
            for r in res["rankings"]:
                cid = r["candidate_id"]
                c = cand_map[cid]
                strat = r["strategy_id"]
                if r["selectable"]:
                    cm = c["metrics"]
                    p1_data = cm["product_breakdown"]["PROD-01"]
                    p1_demand = p1_data["demand"]
                    p1_fulfilled = p1_data["fulfilled"]
                    p1_pct = (p1_fulfilled / p1_demand * 100.0) if p1_demand else 100.0

                    total_demand = cm["total_demand"]
                    total_fulfilled = cm["total_fulfilled"]
                    agg_pct = (total_fulfilled / total_demand * 100.0) if total_demand else 100.0

                    rec = cm["recovery_day"]
                    cost = cm["total_landed_cost"]

                    rec_bonus = max(0, 22 - rec) * 10.0 if rec is not None else 0.0
                    cost_penalty = cost * 0.01
                    calc_score = round((p1_pct * 100.0) + (agg_pct * 50.0) + rec_bonus - cost_penalty, 2)
                    self.assertEqual(r["score"], calc_score)

                    if strat == "agent" and d in expected_agent_scores:
                        self.assertEqual(r["score"], expected_agent_scores[d])
                    elif strat == "optimized" and d in expected_opt_scores:
                        self.assertEqual(r["score"], expected_opt_scores[d])
                else:
                    self.assertIsNone(r["score"])
                    self.assertIsNone(r["rank"])

    def test_ranking_metric_integrity_and_selection_consistency(self):
        """
        Verify that candidate metrics, ranking records, and selection docket
        derived in the SAME coordinate_recovery response maintain strict mathematical
        and provenance integrity across all shutdown durations.
        """
        for d in [1, 3, 7, 10, 14]:
            res = coordinate_recovery(shutdown_days=d)
            cand_map = {c["candidate_id"]: c for c in res["candidates"]}

            # 1. Verify candidate metrics against ranking values
            for r in res["rankings"]:
                cid = r["candidate_id"]
                c = cand_map[cid]
                cm = c["metrics"]
                p1_cm = cm["product_breakdown"]["PROD-01"]
                p2_cm = cm["product_breakdown"]["PROD-02"]

                # Aggregate fill rate must match sum of fulfilled units / total demand
                calc_agg_fill = round((cm["total_fulfilled"] / cm["total_demand"]) * 100, 2)
                self.assertEqual(cm["fill_rate"], calc_agg_fill)
                self.assertEqual(cm["total_fulfilled"], p1_cm["fulfilled"] + p2_cm["fulfilled"])
                self.assertEqual(cm["total_demand"], p1_cm["demand"] + p2_cm["demand"])

                # Ranking record must mirror candidate metrics bit-for-bit
                self.assertEqual(r["aggregate_fill_rate"], cm["fill_rate"])
                self.assertEqual(r["p1_fill_rate"], p1_cm["fill_rate"])
                self.assertEqual(r["total_landed_cost"], cm["total_landed_cost"])
                self.assertEqual(r["recovery_day"], cm["recovery_day"])

                # Score recalculation strictly from full-precision unrounded candidate metrics ratios
                if r["selectable"]:
                    p1_demand = p1_cm["demand"]
                    p1_fulfilled = p1_cm["fulfilled"]
                    p1_pct = (p1_fulfilled / p1_demand * 100.0) if p1_demand else 100.0

                    total_demand = cm["total_demand"]
                    total_fulfilled = cm["total_fulfilled"]
                    agg_pct = (total_fulfilled / total_demand * 100.0) if total_demand else 100.0

                    rec_day = cm["recovery_day"]
                    cost = cm["total_landed_cost"]
                    rec_bonus = max(0, 22 - rec_day) * 10.0 if rec_day is not None else 0.0
                    cost_penalty = cost * 0.01
                    expected_score = round((p1_pct * 100.0) + (agg_pct * 50.0) + rec_bonus - cost_penalty, 2)
                    self.assertEqual(r["score"], expected_score)
                    self.assertIn(r["rank"], [1, 2])
                else:
                    self.assertIsNone(r["score"])
                    self.assertIsNone(r["rank"])

            # 2. Verify selection docket integrity
            sel = res["selection"]
            self.assertEqual(sel["selected_strategy_id"], "agent")
            self.assertEqual(sel["selection_status"], "SELECTED")

            rank_1 = next(r for r in res["rankings"] if r["rank"] == 1)
            self.assertEqual(sel["selected_candidate_id"], rank_1["candidate_id"])
            self.assertTrue(rank_1["selectable"])

            rejected_ids = {alt["candidate_id"] for alt in sel["rejected_alternatives"]}
            other_ids = {r["candidate_id"] for r in res["rankings"] if r["candidate_id"] != rank_1["candidate_id"]}
            self.assertEqual(rejected_ids, other_ids)


if __name__ == "__main__":
    unittest.main()
