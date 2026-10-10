"""
SupplyShield AI — Specialized Agents Test Suite (Phase B3)

Exhaustively verifies:
1. Demand Intelligence: Product priorities, demand exposures, horizon reconciliation,
   priority-aware guidance, zero-demand handling, and determinism.
2. Inventory Intelligence: Coverage calculations, depletion timing, inbound receipts before/after
   depletion, rejected order filtering, zero-demand resilience, and shortage windows.
3. Supplier Risk & Sourcing: Primary outage handling, post-outage recovery, alternate eligibility,
   landed costs, combined capacity deficits, and honest unconfirmed availability.
4. Logistics Optimization: D + L lead-time physics, horizon cutoffs, freight cost reconciliation,
   and Day 3-4 lead-time transit gap evidence.
5. Cross-Agent Consistency: Shared scenario signature, matching identifiers, distinct responsibilities,
   deterministic repeat execution, and Pydantic contract validation across durations 1, 3, 7, 10, 14.
"""

import unittest
from copy import deepcopy

from simulator import NETWORK, TRANSPORT_COST, HORIZON, simulate_order_plan
from optimizer import optimize_plan
from schemas import AgentProposal, AgentScenarioContext, RecoveryResponse
from coordinator import coordinate_recovery
from agents.common import build_scenario_context
from agents.demand_intelligence import demand_agent
from agents.inventory_intelligence import inventory_agent
from agents.supplier_risk import supplier_risk_agent
from agents.logistics_optimization import logistics_agent


class TestSpecialistAgents(unittest.TestCase):
    """Exhaustive test suite for the four Phase B3 specialist supply chain agents."""

    DURATIONS = [1, 3, 7, 10, 14]

    # ==========================================================================
    # 1. DEMAND INTELLIGENCE AGENT TESTS
    # ==========================================================================

    def test_demand_agent_all_products_accounted_and_prioritized(self):
        """Verify all configured products are evaluated with correct priority rankings."""
        props = demand_agent(NETWORK)
        self.assertEqual(len(props), len(NETWORK["products"]))

        p1 = next(p for p in props if p["product"] == "PROD-01")
        p2 = next(p for p in props if p["product"] == "PROD-02")

        self.assertEqual(p1["priority"], 1)
        self.assertEqual(p1["criticality"], "CRITICAL (Tier 1)")
        self.assertEqual(p2["priority"], 2)
        self.assertEqual(p2["criticality"], "STANDARD (Tier 2)")

    def test_demand_agent_quantities_reconcile_to_horizon(self):
        """Verify daily and 21-day horizon demand quantities reconcile precisely."""
        props = demand_agent(NETWORK, horizon_days=HORIZON)
        p1 = next(p for p in props if p["product"] == "PROD-01")
        p2 = next(p for p in props if p["product"] == "PROD-02")

        # PROD-01: 45 units/day * 21 days = 945 units
        self.assertEqual(p1["daily_demand"], 45)
        self.assertEqual(p1["evidence"]["total_demand_exposure"], 45 * 21)
        self.assertEqual(p1["handoff"]["horizon_demand"], 945)

        # PROD-02: 35 units/day * 21 days = 735 units
        self.assertEqual(p2["daily_demand"], 35)
        self.assertEqual(p2["evidence"]["total_demand_exposure"], 35 * 21)
        self.assertEqual(p2["handoff"]["horizon_demand"], 735)

        # Total network demand = 1680 units
        total_demand = p1["evidence"]["total_demand_exposure"] + p2["evidence"]["total_demand_exposure"]
        self.assertEqual(total_demand, 1680)

    def test_demand_agent_distinguishes_demand_exposure_from_fulfilled(self):
        """Verify agent explicitly labels demand as gross exposure rather than claimed fulfillment."""
        props = demand_agent(NETWORK)
        for p in props:
            self.assertIn("Demand exposure represents gross customer order requirements", p["limitations"][2])
            self.assertNotIn("fulfilled_units", p["evidence"])

    def test_demand_agent_capacity_deficit_and_tradeoff_guidance(self):
        """Verify priority allocation guidance under alternate supplier 60u/d cap."""
        props = demand_agent(NETWORK)
        p1 = next(p for p in props if p["product"] == "PROD-01")
        p2 = next(p for p in props if p["product"] == "PROD-02")

        # P1 recommended allocation = 45 u/d (fully protected from 60 u/d backup)
        self.assertEqual(p1["evidence"]["recommended_daily_allocation"], 45)
        self.assertEqual(p1["evidence"]["daily_shortfall_during_outage"], 0)

        # P2 recommended allocation = remaining 15 u/d (60 - 45), leaving 20 u/d deficit
        self.assertEqual(p2["evidence"]["recommended_daily_allocation"], 15)
        self.assertEqual(p2["evidence"]["daily_shortfall_during_outage"], 20)

    def test_demand_agent_handles_zero_demand(self):
        """Verify agent handles zero or negative demand gracefully with LIMITED status."""
        mod_net = deepcopy(NETWORK)
        mod_net["products"][0]["daily_demand"] = 0
        props = demand_agent(mod_net)
        p1 = next(p for p in props if p["product"] == "PROD-01")
        self.assertEqual(p1["status"], "LIMITED")
        self.assertEqual(p1["evidence"]["total_demand_exposure"], 0)

    def test_demand_agent_determinism(self):
        """Verify bit-for-bit determinism across repeated executions."""
        props1 = demand_agent(NETWORK)
        props2 = demand_agent(NETWORK)
        self.assertEqual(props1, props2)

    # ==========================================================================
    # 2. INVENTORY INTELLIGENCE AGENT TESTS
    # ==========================================================================

    def test_inventory_agent_initial_coverage_and_depletion_timing(self):
        """Verify stock runway (stock / burn) and unassisted depletion day (int(runway) + 1)."""
        props = inventory_agent(NETWORK)
        p1 = next(p for p in props if p["product"] == "PROD-01")
        p2 = next(p for p in props if p["product"] == "PROD-02")

        # PROD-01: 100 stock / 45 burn = 2.22 days -> Day 3 stockout
        self.assertEqual(p1["inventory"], 100)
        self.assertEqual(p1["daily_demand"], 45)
        self.assertAlmostEqual(p1["days_of_cover"], 2.22, places=2)
        self.assertEqual(p1["stockout_day"], 3)
        self.assertEqual(p1["risk"], "HIGH")

        # PROD-02: 75 stock / 35 burn = 2.14 days -> Day 3 stockout
        self.assertEqual(p2["inventory"], 75)
        self.assertEqual(p2["daily_demand"], 35)
        self.assertAlmostEqual(p2["days_of_cover"], 2.14, places=2)
        self.assertEqual(p2["stockout_day"], 3)
        self.assertEqual(p2["risk"], "HIGH")

    def test_inventory_agent_inbound_arrival_before_depletion(self):
        """Verify inbound order arriving on Day 2 extends inventory coverage beyond Day 3."""
        inbound = [
            {"product": "PROD-01", "quantity": 90, "arrival_day": 2, "status": "ordered"}
        ]
        props = inventory_agent(NETWORK, inbound_orders=inbound)
        p1 = next(p for p in props if p["product"] == "PROD-01")

        # Initial 100 - 45 = 55 end of D1.
        # D2 starts with 55 + 90 = 145. Demand 45 -> 100 left.
        # D3 starts with 100. Demand 45 -> 55 left.
        # D4 starts with 55. Demand 45 -> 10 left.
        # D5 starts with 10. Demand 45 -> stockout on Day 5!
        self.assertEqual(p1["evidence"]["effective_depletion_day"], 5)
        self.assertEqual(p1["evidence"]["confirmed_inbound_units"], 90)

    def test_inventory_agent_inbound_arrival_after_depletion(self):
        """Verify inbound order arriving after depletion detects the shortage exposure window."""
        inbound = [
            {"product": "PROD-01", "quantity": 50, "arrival_day": 5, "status": "ordered"}
        ]
        props = inventory_agent(NETWORK, inbound_orders=inbound)
        p1 = next(p for p in props if p["product"] == "PROD-01")

        # Depletion occurs on Day 3; order arrives on Day 5.
        # Shortage window is Days 3 to 4 (uncovered days = 5 - 3 = 2).
        shortage = p1["evidence"]["shortage_window"]
        self.assertEqual(shortage["shortage_start_day"], 3)
        self.assertEqual(shortage["replenishment_arrival_day"], 5)
        self.assertEqual(shortage["uncovered_days"], 2)

    def test_inventory_agent_filters_unaccepted_or_rejected_orders(self):
        """Verify rejected or invalid inbound orders are not counted as confirmed stock."""
        invalid_inbounds = [
            {"product": "PROD-01", "quantity": 50, "arrival_day": 2, "status": "rejected"},
            {"product": "PROD-01", "quantity": -20, "arrival_day": 2, "status": "ordered"},
            {"product": "PROD-01", "quantity": 0, "arrival_day": 2, "status": "ordered"},
            {"product": "PROD-01", "quantity": True, "arrival_day": 2, "status": "ordered"},
        ]
        props = inventory_agent(NETWORK, inbound_orders=invalid_inbounds)
        p1 = next(p for p in props if p["product"] == "PROD-01")
        self.assertEqual(p1["evidence"]["confirmed_inbound_units"], 0)
        self.assertEqual(p1["stockout_day"], 3)

    def test_inventory_agent_zero_demand_handling(self):
        """Verify inventory agent does not divide by zero when demand is 0."""
        mod_net = deepcopy(NETWORK)
        mod_net["products"][0]["daily_demand"] = 0
        props = inventory_agent(mod_net)
        p1 = next(p for p in props if p["product"] == "PROD-01")
        self.assertEqual(p1["status"], "LIMITED")
        self.assertIsNone(p1["stockout_day"])
        self.assertEqual(p1["risk"], "NO_DEMAND")

    # ==========================================================================
    # 3. SUPPLIER RISK & SOURCING AGENT TESTS
    # ==========================================================================

    def test_supplier_risk_agent_shutdown_handling_across_durations(self):
        """Verify SUP-01 outage status and SUP-02 availability across all shutdown durations."""
        for d in self.DURATIONS:
            props = supplier_risk_agent(NETWORK, shutdown_days=d)
            sup1 = next(p for p in props if p["supplier"] == "SUP-01")
            sup2 = next(p for p in props if p["supplier"] == "SUP-02")

            # SUP-01 offline during shutdown
            self.assertEqual(sup1["risk"], "CRITICAL")
            self.assertEqual(sup1["shutdown_days"], d)
            self.assertEqual(sup1["handoff"]["earliest_eligible_order_day"], d + 1)
            self.assertFalse(sup1["handoff"]["is_available_for_orders"])

            # SUP-02 active qualified backup
            self.assertEqual(sup2["risk"], "AVAILABLE")
            self.assertEqual(sup2["shutdown_days"], 0)
            self.assertEqual(sup2["handoff"]["earliest_eligible_order_day"], 1)
            self.assertTrue(sup2["handoff"]["is_available_for_orders"])

    def test_supplier_risk_agent_landed_cost_and_capacity_deficits(self):
        """Verify unit landed costs and aggregate shared daily capacity limits."""
        props = supplier_risk_agent(NETWORK, shutdown_days=7)
        sup1 = next(p for p in props if p["supplier"] == "SUP-01")
        sup2 = next(p for p in props if p["supplier"] == "SUP-02")

        # SUP-01: Base 10.0 + Freight 2.0 = Landed 12.0 INR/unit
        self.assertEqual(sup1["evidence"]["base_unit_cost_inr"], 10.0)
        self.assertEqual(sup1["evidence"]["freight_cost_inr"], 2.0)
        self.assertEqual(sup1["evidence"]["total_landed_cost_inr"], 12.0)
        self.assertEqual(sup1["capacity"], 100)

        # SUP-02: Base 13.0 + Freight 3.5 = Landed 16.5 INR/unit (+₹4.5 premium)
        self.assertEqual(sup2["evidence"]["base_unit_cost_inr"], 13.0)
        self.assertEqual(sup2["evidence"]["freight_cost_inr"], 3.5)
        self.assertEqual(sup2["evidence"]["total_landed_cost_inr"], 16.5)
        self.assertEqual(sup2["capacity"], 60)

        # SUP-02 capacity deficit vs network total demand (80 u/d) = 20 u/d
        self.assertEqual(sup2["evidence"]["shared_capacity_deficit"], 20)

    def test_supplier_risk_agent_unconfirmed_availability_disclaimer(self):
        """Verify supplier agent explicitly documents synthetic scenario vs unconfirmed real-world stock."""
        props = supplier_risk_agent(NETWORK, shutdown_days=7)
        for p in props:
            self.assertTrue(any("unconfirmed" in lim.lower() for lim in p["limitations"]))

    # ==========================================================================
    # 4. LOGISTICS OPTIMIZATION AGENT TESTS
    # ==========================================================================

    def test_logistics_agent_lead_time_arrival_day_physics(self):
        """Verify arrival_day = order_day + lead_time calculation across durations."""
        for d in self.DURATIONS:
            props = logistics_agent(NETWORK, shutdown_days=d)
            sup1 = next(p for p in props if p["supplier"] == "SUP-01")
            sup2 = next(p for p in props if p["supplier"] == "SUP-02")

            # SUP-02: lead_time 4d, order Day 1 -> arrives Day 5
            self.assertEqual(sup2["lead_time_days"], 4)
            self.assertEqual(sup2["earliest_possible_arrival_day"], 5)
            self.assertEqual(sup2["evidence"]["formula"], "arrival_day = order_day + lead_time")

            # SUP-01: lead_time 2d, order Day d+1 -> arrives Day d + 1 + 2 = d + 3
            self.assertEqual(sup1["lead_time_days"], 2)
            self.assertEqual(sup1["earliest_possible_arrival_day"], d + 3)

    def test_logistics_agent_horizon_boundary_cutoff(self):
        """Verify orders placed past Day (21 - lead_time) are flagged as arriving outside horizon."""
        props = logistics_agent(NETWORK, horizon_days=21)
        sup1 = next(p for p in props if p["supplier"] == "SUP-01")
        sup2 = next(p for p in props if p["supplier"] == "SUP-02")

        # SUP-01: lead time 2 -> cutoff day 19 (19 + 2 = 21)
        self.assertEqual(sup1["evidence"]["horizon_cutoff_order_day"], 19)

        # SUP-02: lead time 4 -> cutoff day 17 (17 + 4 = 21)
        self.assertEqual(sup2["evidence"]["horizon_cutoff_order_day"], 17)

    def test_logistics_agent_transit_gap_one_day_vs_extended(self):
        """
        Verify scenario-specific pre-replenishment transit gaps:
        1. 1-day shutdown: SUP-01 orders placed Day 2 arrive Day 4 (2 + 2 = 4).
           Day 3 stockout is unassisted, but Day 4 is replenished by SUP-01. Gap is strictly [3].
        2. Extended shutdown (>= 2 days): Neither SUP-01 (offline) nor SUP-02 (arriving Day 5)
           can deliver on Day 3 or Day 4. Gap spans [3, 4].
        """
        # 1-day shutdown
        props_1 = logistics_agent(NETWORK, shutdown_days=1)
        sup1_1 = next(p for p in props_1 if p["supplier"] == "SUP-01")
        sup2_1 = next(p for p in props_1 if p["supplier"] == "SUP-02")
        self.assertEqual(sup1_1["evidence"]["earliest_possible_arrival_day"], 4)
        self.assertEqual(sup2_1["evidence"]["earliest_possible_arrival_day"], 5)
        self.assertEqual(sup2_1["evidence"]["network_earliest_arrival_day"], 4)
        self.assertEqual(sup2_1["evidence"]["transit_gap_days"], [3])

        # Extended shutdowns (3, 7, 10, 14)
        for d in [3, 7, 10, 14]:
            props_ext = logistics_agent(NETWORK, shutdown_days=d)
            sup2_ext = next(p for p in props_ext if p["supplier"] == "SUP-02")
            self.assertEqual(sup2_ext["evidence"]["network_earliest_arrival_day"], 5)
            self.assertEqual(sup2_ext["evidence"]["transit_gap_days"], [3, 4])

    def test_logistics_agent_inbound_orders_eliminate_transit_gap(self):
        """Verify confirmed inbound order arriving on Day 2 eliminates pre-replenishment shortage gap."""
        inbound = [
            {"product": "PROD-01", "quantity": 100, "arrival_day": 2, "status": "ordered"},
            {"product": "PROD-02", "quantity": 100, "arrival_day": 2, "status": "ordered"},
        ]
        props = logistics_agent(NETWORK, shutdown_days=7, horizon_days=21)
        # Pass inbound orders in context
        ctx = build_scenario_context(NETWORK, shutdown_days=7, horizon_days=21, inbound_orders=inbound)
        props_with_inbound = logistics_agent(ctx)
        sup2 = next(p for p in props_with_inbound if p["supplier"] == "SUP-02")
        self.assertEqual(sup2["evidence"]["transit_gap_days"], [])

    def test_demand_agent_heuristic_target_explicitly_labeled(self):
        """Verify the 90% service target is explicitly labeled DEMONSTRATION_HEURISTIC, not a contractual SLA."""
        props = demand_agent(NETWORK)
        p1 = next(p for p in props if p["product"] == "PROD-01")

        # 1. Handoff contains DEMONSTRATION_HEURISTIC classification
        self.assertEqual(p1["handoff"]["service_target_type"], "DEMONSTRATION_HEURISTIC")
        self.assertEqual(p1["handoff"]["target_service_level"], 0.90)

        # 2. Evidence contains DEMONSTRATION_HEURISTIC classification
        self.assertEqual(p1["evidence"]["service_target_type"], "DEMONSTRATION_HEURISTIC")
        self.assertIn("heuristic", p1["evidence"]["service_target"].lower())

        # 3. Limitations explicitly states it is not a contractual SLA
        self.assertTrue(any("demonstration heuristic" in lim.lower() for lim in p1["limitations"]))
        self.assertTrue(any("not a contractual customer sla" in lim.lower() for lim in p1["limitations"]))

        # 4. Finding itemizes the heuristic target
        target_finding = next(f for f in p1["findings"] if f["observation"] == "Operational service target")
        self.assertEqual(target_finding["target_type"], "DEMONSTRATION_HEURISTIC")

    def test_demand_priority_guidance_consumed_by_optimizer(self):
        """
        Verify that Demand Agent priority handoff weights are consumed directly by optimize_plan
        and materially influence the CP-SAT objective.
        """
        # Baseline agent-assisted weights from demand agent: PROD-01 = 2, PROD-02 = 1
        opt_standard = optimize_plan(shutdown_days=7, priority_weighted=True, product_weights={"PROD-01": 2, "PROD-02": 1})
        p1_std = opt_standard["metrics"]["product_breakdown"]["PROD-01"]["fulfilled"]
        p2_std = opt_standard["metrics"]["product_breakdown"]["PROD-02"]["fulfilled"]

        # Inverted weights: PROD-01 = 1, PROD-02 = 10 (heavily penalize unmet PROD-02)
        opt_inverted = optimize_plan(shutdown_days=7, priority_weighted=True, product_weights={"PROD-01": 1, "PROD-02": 10})
        p1_inv = opt_inverted["metrics"]["product_breakdown"]["PROD-01"]["fulfilled"]
        p2_inv = opt_inverted["metrics"]["product_breakdown"]["PROD-02"]["fulfilled"]

        # Inverted weights must prioritize PROD-02 over PROD-01
        self.assertGreater(p2_inv, p2_std, "Inverting priority weight should increase PROD-02 fulfilled units")
        self.assertLess(p1_inv, p1_std, "Inverting priority weight should decrease PROD-01 fulfilled units")

        # Coordinator must pass demand weights into optimize_plan
        rec = coordinate_recovery(shutdown_days=7)
        self.assertEqual(
            rec["optimization"]["metrics"]["product_breakdown"]["PROD-01"]["fulfilled"],
            p1_std,
        )

    def test_agent_strategy_metric_reconciliation_across_simulate_and_recovery(self):
        """
        Verify exact fill-rate and fulfillment reconciliation for the Agent-Assisted strategy across:
        1. run_simulation(recovery_mode='agent')
        2. coordinate_recovery()
        3. optimize_plan(priority_weighted=True)
        for shutdown durations 1, 7, and 14.
        """
        from simulator import run_simulation

        for d in [1, 7, 14]:
            sim_full = run_simulation(shutdown_days=d, recovery_mode="agent")
            rec = coordinate_recovery(shutdown_days=d)
            opt_agent = optimize_plan(shutdown_days=d, priority_weighted=True)

            sim_m = sim_full["metrics"]
            rec_m = rec["optimization"]["metrics"]
            opt_m = opt_agent["metrics"]

            # Aggregate fill rate matches across all components executing the agent-assisted plan
            self.assertEqual(sim_m["fill_rate"], rec_m["fill_rate"])
            self.assertEqual(rec_m["fill_rate"], opt_m["fill_rate"])
            self.assertEqual(sim_m["total_fulfilled"], rec_m["total_fulfilled"])
            self.assertEqual(sim_m["total_backorders"], rec_m["total_backorders"])

            # Product-level breakdown matches across components
            for pid in ["PROD-01", "PROD-02"]:
                sim_pb = sim_m["product_breakdown"][pid]
                rec_pb = rec_m["product_breakdown"][pid]
                opt_pb = opt_m["product_breakdown"][pid]

                self.assertEqual(sim_pb["fill_rate"], rec_pb["fill_rate"])
                self.assertEqual(rec_pb["fill_rate"], opt_pb["fill_rate"])
                self.assertEqual(sim_pb["fulfilled"], rec_pb["fulfilled"])
                self.assertEqual(sim_pb["unmet"], rec_pb["unmet"])

            # Verified benchmark values
            if d == 1:
                self.assertAlmostEqual(sim_m["fill_rate"], 96.13, places=2)
                self.assertAlmostEqual(sim_m["product_breakdown"]["PROD-01"]["fill_rate"], 96.30, places=2)
                self.assertAlmostEqual(sim_m["product_breakdown"]["PROD-02"]["fill_rate"], 95.92, places=2)
            elif d == 7:
                self.assertAlmostEqual(sim_m["fill_rate"], 85.42, places=2)
                self.assertAlmostEqual(sim_m["product_breakdown"]["PROD-01"]["fill_rate"], 91.53, places=2)
                self.assertAlmostEqual(sim_m["product_breakdown"]["PROD-02"]["fill_rate"], 77.55, places=2)
            elif d == 14:
                self.assertAlmostEqual(sim_m["fill_rate"], 77.08, places=2)
                self.assertAlmostEqual(sim_m["product_breakdown"]["PROD-01"]["fill_rate"], 91.53, places=2)
                self.assertAlmostEqual(sim_m["product_breakdown"]["PROD-02"]["fill_rate"], 58.50, places=2)

    def test_optimization_only_strategy_metric_reconciliation(self):
        """
        Verify exact fill-rate and fulfillment reconciliation for the Optimization-Only strategy across:
        1. run_simulation(recovery_mode='optimized')
        2. optimize_plan(priority_weighted=False) (the direct solver endpoint GET /api/optimize)
        """
        from simulator import run_simulation

        for d in [1, 7, 14]:
            sim_opt = run_simulation(shutdown_days=d, recovery_mode="optimized")
            direct_opt = optimize_plan(shutdown_days=d, priority_weighted=False)

            sm = sim_opt["metrics"]
            dm = direct_opt["metrics"]

            self.assertEqual(sm["fill_rate"], dm["fill_rate"])
            self.assertEqual(sm["total_fulfilled"], dm["total_fulfilled"])
            self.assertEqual(sm["total_backorders"], dm["total_backorders"])

            for pid in ["PROD-01", "PROD-02"]:
                self.assertEqual(sm["product_breakdown"][pid]["fill_rate"], dm["product_breakdown"][pid]["fill_rate"])
                self.assertEqual(sm["product_breakdown"][pid]["fulfilled"], dm["product_breakdown"][pid]["fulfilled"])
                self.assertEqual(sm["product_breakdown"][pid]["unmet"], dm["product_breakdown"][pid]["unmet"])

    def test_distinct_strategy_identities_and_product_fulfillment(self):
        """
        Verify that Strategy 2 (Optimization-Only) and Strategy 3 (Agent-Assisted) preserve
        their distinct strategy identities:
        - At D=7 and D=14, they share aggregate volume (bounded by SUP-02 60u/d capacity)
        - But Agent-Assisted strategically protects Priority 1 (PROD-01) at 91.53%
          while Optimization-Only treats components uniformly (85.19% at D=7; 72.49% at D=14).
        """
        from simulator import run_simulation

        # 7-day shutdown
        opt_7 = run_simulation(shutdown_days=7, recovery_mode="optimized")["metrics"]
        agent_7 = run_simulation(shutdown_days=7, recovery_mode="agent")["metrics"]
        self.assertEqual(opt_7["fill_rate"], agent_7["fill_rate"], "Must share aggregate fill rate (85.42%)")
        self.assertEqual(opt_7["total_fulfilled"], agent_7["total_fulfilled"])
        self.assertGreater(
            agent_7["product_breakdown"]["PROD-01"]["fill_rate"],
            opt_7["product_breakdown"]["PROD-01"]["fill_rate"],
            "Agent mode must prioritize PROD-01 (91.53% vs 85.19%)",
        )

        # 14-day shutdown
        opt_14 = run_simulation(shutdown_days=14, recovery_mode="optimized")["metrics"]
        agent_14 = run_simulation(shutdown_days=14, recovery_mode="agent")["metrics"]
        self.assertEqual(opt_14["fill_rate"], agent_14["fill_rate"], "Must share aggregate fill rate (77.08%)")
        self.assertEqual(opt_14["total_fulfilled"], agent_14["total_fulfilled"])
        self.assertGreater(
            agent_14["product_breakdown"]["PROD-01"]["fill_rate"],
            opt_14["product_breakdown"]["PROD-01"]["fill_rate"],
            "Agent mode must prioritize PROD-01 (91.53% vs 72.49%)",
        )

    def test_landed_cost_order_level_reconciliation_all_durations(self):
        """
        Verify order-level landed cost accounting across shutdown durations 1, 7, and 14:
        - Total landed cost equals sum of accepted order costs and daily landed costs.
        - Landed unit rates: SUP-01 = ₹12.0/u (10.0 + 2.0), SUP-02 = ₹16.5/u (13.0 + 3.5).
        - Confirms exact values: D=1: ₹17,280; D=7: ₹16,470; D=14: ₹16,680.
        """
        from simulator import run_simulation

        for d in [1, 7, 14]:
            sim = run_simulation(shutdown_days=d, recovery_mode="agent")
            m = sim["metrics"]
            daily = sim["daily_results"]

            # Sum of daily landed costs matches total_landed_cost exactly
            daily_sum = sum(day.get("landed_cost", 0.0) for day in daily)
            self.assertAlmostEqual(m["total_landed_cost"], daily_sum, places=2)

            # Order plan cost reconciliation
            plan = optimize_plan(shutdown_days=d, priority_weighted=True)
            orders = plan["orders"]
            order_sum = sum(o["cost"] for o in orders)
            self.assertAlmostEqual(plan["metrics"]["total_landed_cost"], order_sum, places=2)

            sup1_qty = sum(o["quantity"] for o in orders if o["supplier"] == "SUP-01")
            sup2_qty = sum(o["quantity"] for o in orders if o["supplier"] == "SUP-02")
            expected_total = sup1_qty * 12.0 + sup2_qty * 16.5
            self.assertAlmostEqual(order_sum, expected_total, places=2)

            if d == 1:
                self.assertEqual(m["total_landed_cost"], 17280.0)
            elif d == 7:
                self.assertEqual(m["total_landed_cost"], 16470.0)
            elif d == 14:
                self.assertEqual(m["total_landed_cost"], 16680.0)

    # ==========================================================================
    # 5. CROSS-AGENT CONSISTENCY & INTEGRATION TESTS
    # ==========================================================================

    def test_cross_agent_shared_scenario_context(self):
        """Verify all four agents receive consistent scenario signature and parameters."""
        context = build_scenario_context(NETWORK, shutdown_days=7, horizon_days=21)
        d_props = demand_agent(context)
        i_props = inventory_agent(context)
        s_props = supplier_risk_agent(context)
        l_props = logistics_agent(context)

        # Verify scenario signature consistency
        self.assertEqual(context.scenario_id, "SCEN-SD7-H21-S42")
        self.assertEqual(d_props[0]["evidence"]["scenario_signature"], "SCEN-SD7-H21-S42")

        # Verify product IDs match
        d_pids = {p["product"] for p in d_props}
        i_pids = {p["product"] for p in i_props}
        self.assertEqual(d_pids, {"PROD-01", "PROD-02"})
        self.assertEqual(i_pids, {"PROD-01", "PROD-02"})

        # Verify supplier IDs match
        s_sids = {p["supplier"] for p in s_props}
        l_sids = {p["supplier"] for p in l_props}
        self.assertEqual(s_sids, {"SUP-01", "SUP-02"})
        self.assertEqual(l_sids, {"SUP-01", "SUP-02"})

    def test_cross_agent_distinct_responsibilities(self):
        """Verify each agent addresses distinct operational questions without redundant narrative."""
        context = build_scenario_context(NETWORK, shutdown_days=7)
        d_props = demand_agent(context)
        i_props = inventory_agent(context)
        s_props = supplier_risk_agent(context)
        l_props = logistics_agent(context)

        # Demand: focuses on criticality tiers, daily demand, and priority allocation
        self.assertIn("priority", d_props[0])
        self.assertIn("criticality", d_props[0])

        # Inventory: focuses on runway days, depletion timing, and stock burn rate
        self.assertIn("days_of_cover", i_props[0])
        self.assertIn("stockout_day", i_props[0])

        # Supplier Risk: focuses on outage window, supplier risk, and facility shutdown
        self.assertIn("shutdown_days", s_props[0])
        self.assertIn("risk", s_props[0])

        # Logistics: focuses on transit lead times, freight costs, and arrival days
        self.assertIn("lead_time_days", l_props[0])
        self.assertIn("transport_cost_per_unit", l_props[0])
        self.assertIn("earliest_possible_arrival_day", l_props[0])

    def test_pydantic_contract_validation_across_all_proposals(self):
        """Verify every proposal from all 4 agents validates cleanly against specialized Pydantic models."""
        from schemas import (
            DemandAgentProposal,
            InventoryAgentProposal,
            SupplierRiskAgentProposal,
            LogisticsAgentProposal,
            AgentFinding,
        )

        for d in self.DURATIONS:
            context = build_scenario_context(NETWORK, shutdown_days=d)
            # Demand
            for prop in demand_agent(context):
                val = DemandAgentProposal.model_validate(prop)
                self.assertEqual(val.status, "SUCCESS")
                self.assertIsNotNone(val.handoff)
                self.assertEqual(val.handoff.service_target_type, "DEMONSTRATION_HEURISTIC")
                for f in val.findings:
                    AgentFinding.model_validate(f)

            # Inventory
            for prop in inventory_agent(context):
                val = InventoryAgentProposal.model_validate(prop)
                self.assertEqual(val.status, "SUCCESS")
                self.assertIsNotNone(val.handoff)
                for f in val.findings:
                    AgentFinding.model_validate(f)

            # Supplier Risk
            for prop in supplier_risk_agent(context):
                val = SupplierRiskAgentProposal.model_validate(prop)
                self.assertEqual(val.status, "SUCCESS")
                self.assertIsNotNone(val.handoff)
                for f in val.findings:
                    AgentFinding.model_validate(f)

            # Logistics
            for prop in logistics_agent(context):
                val = LogisticsAgentProposal.model_validate(prop)
                self.assertEqual(val.status, "SUCCESS")
                self.assertIsNotNone(val.handoff)
                for f in val.findings:
                    AgentFinding.model_validate(f)

    def test_full_recovery_coordination_integration(self):
        """Verify coordinate_recovery seamlessly incorporates the modular specialist outputs."""
        for d in self.DURATIONS:
            rec = coordinate_recovery(shutdown_days=d)
            self.assertEqual(rec["status"], "awaiting_planner_approval")
            validated = RecoveryResponse.model_validate(rec)

            # Check all 4 agent reports are populated
            self.assertEqual(len(validated.agents.demand), 2)
            self.assertEqual(len(validated.agents.inventory), 2)
            self.assertEqual(len(validated.agents.supplier_risk), 2)
            self.assertEqual(len(validated.agents.logistics), 2)

    def test_demand_agent_priority_weight_influence_on_allocation(self):
        """
        Prove that Demand Intelligence priority weights meaningfully influence solver allocation:
        - Default agent prioritization (PROD-01 weight 2, PROD-02 weight 1) allocates scarce
          alternate capacity (60u/d) to protect critical Component A (865 u fulfilled, 91.53% fill rate)
          over Component B (570 u fulfilled, 77.55% fill rate).
        - Explicitly reversing priority weights (PROD-01 weight 1, PROD-02 weight 2) causes the solver
          to shift capacity to PROD-02 (670 u fulfilled vs 570) while reducing PROD-01 (765 u vs 865).
        - Confirms agent handoffs are operationally influential and not merely advisory commentary.
        """
        # 1. Default agent prioritization (P1 critical)
        res_default = optimize_plan(shutdown_days=7, priority_weighted=True)
        p1_default = res_default["metrics"]["product_breakdown"]["PROD-01"]["fulfilled"]
        p2_default = res_default["metrics"]["product_breakdown"]["PROD-02"]["fulfilled"]
        self.assertEqual(p1_default, 865)
        self.assertEqual(p2_default, 570)

        # 2. Reversed priority weights favoring PROD-02
        res_reversed = optimize_plan(shutdown_days=7, product_weights={"PROD-01": 1, "PROD-02": 2})
        p1_reversed = res_reversed["metrics"]["product_breakdown"]["PROD-01"]["fulfilled"]
        p2_reversed = res_reversed["metrics"]["product_breakdown"]["PROD-02"]["fulfilled"]
        self.assertEqual(p1_reversed, 765)
        self.assertEqual(p2_reversed, 670)

        # 3. Allocation shift proof
        self.assertGreater(p2_reversed, p2_default, "Reversed priority weight must increase PROD-02 fulfillment")
        self.assertLess(p1_reversed, p1_default, "Reversed priority weight must decrease PROD-01 fulfillment")
        # Total fulfilled volume remains identical due to binding 60u/d alternate supplier capacity
        self.assertEqual(
            p1_default + p2_default,
            p1_reversed + p2_reversed,
            "Aggregate fulfillment must be conserved under binding capacity",
        )


if __name__ == "__main__":
    unittest.main()

