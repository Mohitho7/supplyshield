import unittest
from simulator import run_simulation, simulate_order_plan, NETWORK, HORIZON, TARGET_FILL_RATE
from optimizer import optimize_plan
from coordinator import coordinate_recovery
from baselines import reorder_rules_plan, optimization_only_plan, agent_assisted_plan


class TestSupplyShieldModel(unittest.TestCase):
    def test_network_structure(self):
        """Verify the synthetic 2-supplier, 2-factory, 2-DC, 2-product network topology."""
        self.assertEqual(len(NETWORK["suppliers"]), 2)
        self.assertEqual(len(NETWORK["factories"]), 2)
        self.assertEqual(len(NETWORK["distribution_centers"]), 2)
        self.assertEqual(len(NETWORK["products"]), 2)

        # Primary and alternate supplier parameters
        sup_dict = {s["id"]: s for s in NETWORK["suppliers"]}
        self.assertEqual(sup_dict["SUP-01"]["capacity"], 100)
        self.assertEqual(sup_dict["SUP-01"]["lead_time"], 2)
        self.assertEqual(sup_dict["SUP-02"]["capacity"], 60)
        self.assertEqual(sup_dict["SUP-02"]["lead_time"], 4)

    def test_reproducibility_and_accounting_reconcile(self):
        """Verify exact mathematical reconciliation: fulfilled + backorders == total_demand."""
        for mode in ["reorder", "optimized", "agent"]:
            sim = run_simulation(shutdown_days=7, recovery_mode=mode)
            m = sim["metrics"]
            total_d = m["total_demand"]
            total_f = m["total_fulfilled"]
            total_b = m["total_backorders"]

            self.assertEqual(total_d, 1680, f"Expected 1680 units of demand over 21 days for mode {mode}")
            self.assertEqual(total_f + total_b, total_d, f"Fulfilled + backorders must equal demand for {mode}")
            expected_fill = round(total_f / total_d * 100, 2)
            self.assertAlmostEqual(m["fill_rate"], expected_fill, places=2)
            self.assertGreater(m["total_landed_cost"], 0)
            if mode in ["optimized", "agent"]:
                self.assertEqual(m["constraint_violations"], 0)
            else:
                self.assertEqual(m["constraint_violations"], 14)

    def test_strategy_distinctness_under_identical_conditions(self):
        """Verify each strategy uses a distinct planning method with reproducible differences."""
        reorder_sim = run_simulation(shutdown_days=7, recovery_mode="reorder")
        opt_sim = run_simulation(shutdown_days=7, recovery_mode="optimized")
        agent_sim = run_simulation(shutdown_days=7, recovery_mode="agent")

        r_metrics = reorder_sim["metrics"]
        o_metrics = opt_sim["metrics"]
        a_metrics = agent_sim["metrics"]

        # 1. Reorder baseline fails significantly during shutdown (no alternate vendor)
        self.assertLess(r_metrics["fill_rate"], o_metrics["fill_rate"])
        self.assertGreater(r_metrics["total_backorders"], o_metrics["total_backorders"])

        # 2. Optimization and Agent achieve equal total volume (bounded by SUP-02 60-unit capacity)
        self.assertEqual(o_metrics["total_fulfilled"], a_metrics["total_fulfilled"])

        # 3. Agent-Assisted explicitly protects critical Priority 1 component (PROD-01)
        o_prod1 = o_metrics["product_breakdown"]["PROD-01"]["fulfilled"]
        a_prod1 = a_metrics["product_breakdown"]["PROD-01"]["fulfilled"]
        self.assertGreater(a_prod1, o_prod1, "Agent mode must prioritize critical Priority 1 product")

    def test_shutdown_scenarios_sensitivity(self):
        """Verify model sensitivity across 3-day, 7-day, and 14-day shutdown scenarios."""
        sim_3 = run_simulation(shutdown_days=3, recovery_mode="agent")
        sim_7 = run_simulation(shutdown_days=7, recovery_mode="agent")
        sim_14 = run_simulation(shutdown_days=14, recovery_mode="agent")

        fr_3 = sim_3["metrics"]["fill_rate"]
        fr_7 = sim_7["metrics"]["fill_rate"]
        fr_14 = sim_14["metrics"]["fill_rate"]

        # Longer shutdown should result in lower or equal fill rate
        self.assertGreaterEqual(fr_3, fr_7)
        self.assertGreaterEqual(fr_7, fr_14)

        # Longer shutdown increases landed procurement cost (more volume routed to expensive SUP-02)
        cost_3 = sim_3["metrics"]["total_landed_cost"]
        cost_7 = sim_7["metrics"]["total_landed_cost"]
        cost_14 = sim_14["metrics"]["total_landed_cost"]
        self.assertLessEqual(cost_3, cost_7)
        self.assertLessEqual(cost_7, cost_14)

    def test_recovery_day_definition(self):
        """Verify recovery day requires 3 consecutive days at >= 95% service after the disruption dip."""
        for mode in ["optimized", "agent"]:
            sim = run_simulation(shutdown_days=7, recovery_mode=mode)
            r_day = sim["metrics"]["recovery_day"]
            self.assertIsNotNone(r_day)
            self.assertGreaterEqual(r_day, 5, "Recovery cannot occur before Day 5 due to lead times")

            # Check that the 3-day window is indeed at or above 95%
            daily = sim["daily_results"]
            window = [d for d in daily if r_day <= d["day"] <= r_day + 2]
            self.assertEqual(len(window), 3)
            for d in window:
                self.assertGreaterEqual(d["fill_rate"], TARGET_FILL_RATE)

    def test_coordinator_agent_hierarchy(self):
        """Verify multi-agent schema: specialized agents -> coordinator -> optimizer -> validation."""
        recovery_data = coordinate_recovery(shutdown_days=7)

        # 1. Structure
        self.assertIn("status", recovery_data)
        self.assertIn("agents", recovery_data)
        self.assertIn("optimization", recovery_data)
        self.assertIn("validation", recovery_data)
        self.assertIn("recommendation", recovery_data)

        # 2. Agents is an object containing 4 arrays
        agents = recovery_data["agents"]
        self.assertIsInstance(agents, dict)
        self.assertIn("demand", agents)
        self.assertIn("inventory", agents)
        self.assertIn("supplier_risk", agents)
        self.assertIn("logistics", agents)
        self.assertIsInstance(agents["demand"], list)
        self.assertIsInstance(agents["inventory"], list)
        self.assertIsInstance(agents["supplier_risk"], list)
        self.assertIsInstance(agents["logistics"], list)

        # 3. Validation passed
        self.assertTrue(recovery_data["validation"]["valid"])
        self.assertEqual(recovery_data["validation"]["violation_count"], 0)

        # 4. Human planner authority
        self.assertTrue(recovery_data["recommendation"]["planner_approval_required"])
        self.assertFalse(recovery_data["recommendation"]["approved"])

    def test_day_3_lead_time_shortfall_evidence(self):
        """
        Syncause Evidence-Based Debugging:
        Verifies that Day 3 fulfillment drops to 18.75% as an immutable physical consequence
        of initial inventory runway (2.18 days) and alternate supplier lead time (4 days).
        """
        sim = run_simulation(shutdown_days=7, recovery_mode="agent")
        daily = sim["daily_results"]

        # Day 1: 100% fulfilled; closing stock: PROD-01 = 55, PROD-02 = 40
        d1 = daily[0]
        self.assertEqual(d1["fulfilled"], 80)
        self.assertEqual(d1["inventory"]["PROD-01"], 55)
        self.assertEqual(d1["inventory"]["PROD-02"], 40)

        # Day 2: 100% fulfilled; closing stock: PROD-01 = 10, PROD-02 = 5
        d2 = daily[1]
        self.assertEqual(d2["fulfilled"], 80)
        self.assertEqual(d2["inventory"]["PROD-01"], 10)
        self.assertEqual(d2["inventory"]["PROD-02"], 5)

        # Day 3: Opening stock is 10 + 5 = 15. Zero pipeline arrivals can occur because
        # SUP-01 is shut down and SUP-02 order placed on Day 1 has lead time 4 (arrives Day 5).
        d3 = daily[2]
        self.assertEqual(d3["demand"], 80)
        self.assertEqual(d3["fulfilled"], 15)
        self.assertEqual(d3["backorders"], 65)
        self.assertEqual(d3["fill_rate"], 18.75)
        self.assertEqual(d3["arrivals"], [])
        self.assertEqual(d3["inventory"]["PROD-01"], 0)
        self.assertEqual(d3["inventory"]["PROD-02"], 0)

        # Day 4: Zero inventory remaining; zero arrivals; 80 units unmet
        d4 = daily[3]
        self.assertEqual(d4["fulfilled"], 0)
        self.assertEqual(d4["backorders"], 80)
        self.assertEqual(d4["arrivals"], [])

        # Day 5: First pipeline arrival from Day 1 order (45 PROD-01 + 15 PROD-02)
        d5 = daily[4]
        self.assertEqual(len(d5["arrivals"]), 2)
        total_arrived = sum(a["quantity"] for a in d5["arrivals"])
        self.assertEqual(total_arrived, 60)
        self.assertEqual(d5["fulfilled"], 60)
        self.assertEqual(d5["fill_rate"], 75.0)


if __name__ == "__main__":
    unittest.main()
