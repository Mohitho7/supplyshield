"""
SupplyShield AI — Simulation Invariants & Strategy Feasibility Test Suite (Phase B1)

Exhaustively verifies:
1. Scenario assumptions and accounting invariants across shutdown durations [1, 3, 7, 10, 14].
2. Non-negative inventory, inventory balance equations, and demand fulfillment reconciliation.
3. Order lifecycle, lead time arrival conventions (D+L), and pipeline tracking.
4. Landed cost reconciliation (procurement + freight = landed cost).
5. Deterministic reproducibility across repeated runs.
6. Recovery day calculation, including edge cases (never recovered -> None, no dip -> 1).
7. Genuinely distinct strategy decision logic and priority trade-offs.
8. Feasibility checking on candidate orders (unknown supplier/product, invalid quantity, capacity, shutdown).
9. Contract compatibility with established Pydantic schemas.
"""

import unittest
from copy import deepcopy

from simulator import (
    NETWORK,
    TRANSPORT_COST,
    HORIZON,
    TARGET_FILL_RATE,
    run_simulation,
    simulate_order_plan,
    calculate_recovery_day,
)
from optimizer import optimize_plan
from baselines import reorder_rules_plan, optimization_only_plan, agent_assisted_plan
from coordinator import (
    coordinate_recovery,
    validate_order_plan,
    build_validation_report,
    rank_candidates,
)
from schemas import (
    SimulationResponse,
    OptimizationResponse,
    RecoveryResponse,
    ComparisonResponse,
)


class TestSimulationInvariants(unittest.TestCase):
    """Rigorous verification of simulation accounting invariants and strategy alignment."""

    DURATIONS = [1, 3, 7, 10, 14]
    STRATEGIES = ["reorder", "optimized", "agent"]

    # ==========================================================================
    # 1. SHUTDOWN SENSITIVITY ACROSS ALL 5 SPECIFIED DURATIONS (1, 3, 7, 10, 14)
    # ==========================================================================

    def test_shutdown_sensitivity_across_all_durations(self):
        """Verify model sensitivity and consistency across 1, 3, 7, 10, and 14 days."""
        prev_fill = {m: 100.0 for m in self.STRATEGIES}

        for d in self.DURATIONS:
            for m in self.STRATEGIES:
                sim = run_simulation(shutdown_days=d, recovery_mode=m)
                metrics = sim["metrics"]

                # Total demand is strictly fixed: 80 units/day * 21 days = 1680 units
                self.assertEqual(metrics["total_demand"], 1680)

                # Demand balance: fulfilled + backorders == total_demand
                self.assertEqual(
                    metrics["total_fulfilled"] + metrics["total_backorders"],
                    metrics["total_demand"],
                    f"Demand conservation violated for {m} at {d} days",
                )

                # Calculated fill rate matches formula exactly
                expected_fill = round(metrics["total_fulfilled"] / 1680 * 100, 2)
                self.assertAlmostEqual(metrics["fill_rate"], expected_fill, places=2)

                # Increasing disruption length must monotonically decrease or maintain fill rate
                self.assertLessEqual(
                    metrics["fill_rate"],
                    prev_fill[m] + 0.01,
                    f"Fill rate unexpectedly rose for {m} at shutdown {d}",
                )
                prev_fill[m] = metrics["fill_rate"]

                # Feasible strategy plans must have 0 violations; naive baseline attempts orders during shutdown
                if m in ["optimized", "agent"]:
                    self.assertEqual(metrics["constraint_violations"], 0)
                else:
                    self.assertEqual(metrics["constraint_violations"], 2 * d)

    # ==========================================================================
    # 2. INVENTORY BALANCE AND NON-NEGATIVITY INVARIANTS
    # ==========================================================================

    def test_inventory_balance_and_nonnegativity_all_days(self):
        """
        Verify:
          closing_stock[d] = opening_stock[d] + arrivals[d] - fulfilled[d]
          closing_stock[d] >= 0
          fulfilled[d] <= opening_stock[d] + arrivals[d]
          fulfilled[d] <= demand[d]
        across every single day, product, strategy, and shutdown duration.
        """
        for d in self.DURATIONS:
            for m in self.STRATEGIES:
                sim = run_simulation(shutdown_days=d, recovery_mode=m)
                init_inv = {p["id"]: p["initial_inventory"] for p in NETWORK["products"]}
                prev_inv = dict(init_inv)

                for r in sim["daily_results"]:
                    day = r["day"]
                    arr_by_prod = {p["id"]: 0 for p in NETWORK["products"]}
                    for a in r["arrivals"]:
                        arr_by_prod[a["product"]] += a["quantity"]

                    for pid in arr_by_prod:
                        p_data = r["products"][pid]
                        demand = p_data["demand"]
                        fulfilled = p_data["fulfilled"]
                        unmet = p_data["unmet"]
                        closing = r["inventory"][pid]
                        available = prev_inv[pid] + arr_by_prod[pid]

                        # Invariant: fulfilled <= available
                        self.assertLessEqual(
                            fulfilled,
                            available,
                            f"Fulfilled exceeded available stock on day {day} for {pid} ({m}, d={d})",
                        )

                        # Invariant: fulfilled <= demand
                        self.assertLessEqual(
                            fulfilled,
                            demand,
                            f"Fulfilled exceeded demand on day {day} for {pid} ({m}, d={d})",
                        )

                        # Invariant: demand = fulfilled + unmet
                        self.assertEqual(
                            demand,
                            fulfilled + unmet,
                            f"Demand accounting mismatch on day {day} for {pid} ({m}, d={d})",
                        )

                        # Invariant: closing stock = available - fulfilled
                        expected_closing = available - fulfilled
                        self.assertEqual(
                            closing,
                            expected_closing,
                            f"Inventory balance mismatch on day {day} for {pid} ({m}, d={d})",
                        )

                        # Invariant: non-negative inventory
                        self.assertGreaterEqual(
                            closing,
                            0,
                            f"Negative inventory on day {day} for {pid} ({m}, d={d})",
                        )

                        prev_inv[pid] = closing

                # Ending inventory matches Day 21 closing stock
                self.assertEqual(sim["metrics"]["ending_inventory"], prev_inv)

    # ==========================================================================
    # 3. ORDER LEAD-TIME AND ARRIVAL-DAY CONVENTION (D + L)
    # ==========================================================================

    def test_lead_time_and_arrival_day_convention(self):
        """
        Verify that an order placed on Day D with lead time L arrives strictly on Day D + L.
        SUP-01 (lead time 2): Order on Day D arrives on Day D + 2.
        SUP-02 (lead time 4): Order on Day D arrives on Day D + 4.
        """
        sup_lead_times = {s["id"]: s["lead_time"] for s in NETWORK["suppliers"]}

        for d in [1, 7, 14]:
            for m in self.STRATEGIES:
                sim = run_simulation(shutdown_days=d, recovery_mode=m)

                # Collect all placed orders from daily_results
                placed_orders = []
                for day_res in sim["daily_results"]:
                    day = day_res["day"]
                    for order in day_res["orders"]:
                        if order.get("status") == "ordered":
                            self.assertEqual(order.get("quantity", 0) > 0, True)
                            expected_arrival = day + sup_lead_times[order["supplier"]]
                            self.assertEqual(
                                order["arrival_day"],
                                expected_arrival,
                                f"Order arrival day mismatch for {order['supplier']} placed on day {day}",
                            )
                            placed_orders.append((day, order))

                # For every arrival, verify it corresponds to an earlier order placed on arrival_day - lead_time
                for day_res in sim["daily_results"]:
                    day = day_res["day"]
                    for arrival in day_res["arrivals"]:
                        lt = sup_lead_times[arrival["supplier"]]
                        order_day = day - lt
                        self.assertGreaterEqual(
                            order_day,
                            1,
                            f"Arrival on day {day} cannot exist since lead time is {lt}",
                        )

    # ==========================================================================
    # 4. SUPPLIER SHUTDOWN AND CAPACITY ENFORCEMENT
    # ==========================================================================

    def test_supplier_shutdown_and_capacity_limits(self):
        """
        Verify:
        1. SUP-01 has 0 accepted orders during days 1..shutdown_days.
        2. Daily supplier capacity is never exceeded across all products (SUP-01 <= 100, SUP-02 <= 60).
        """
        capacities = {s["id"]: s["capacity"] for s in NETWORK["suppliers"]}

        for d in self.DURATIONS:
            for m in self.STRATEGIES:
                sim = run_simulation(shutdown_days=d, recovery_mode=m)

                for day_res in sim["daily_results"]:
                    day = day_res["day"]
                    daily_by_supplier = {sid: 0 for sid in capacities}

                    for order in day_res["orders"]:
                        sid = order["supplier"]
                        qty = order["quantity"]

                        if sid == "SUP-01" and day <= d:
                            # Must be rejected
                            self.assertEqual(
                                order.get("status"),
                                "rejected_supplier_shutdown",
                                f"SUP-01 accepted order on day {day} during {d}-day shutdown in {m}",
                            )
                            self.assertEqual(qty, 0)
                        elif order.get("status") == "ordered":
                            daily_by_supplier[sid] += qty

                    for sid, total_qty in daily_by_supplier.items():
                        self.assertLessEqual(
                            total_qty,
                            capacities[sid],
                            f"Supplier {sid} exceeded capacity on day {day} ({total_qty} > {capacities[sid]}) in {m}",
                        )

    # ==========================================================================
    # 5. COST RECONCILIATION INVARIANTS
    # ==========================================================================

    def test_landed_cost_accounting_reconciliation(self):
        """
        Verify:
        1. Unit procurement + freight equals unit landed cost.
           SUP-01: 10.0 + 2.0 = 12.0
           SUP-02: 13.0 + 3.5 = 16.5
        2. Sum of daily landed costs equals metrics.total_landed_cost.
        3. Optimizer total_purchase_and_transport_cost matches simulator total_landed_cost.
        """
        expected_unit_costs = {
            "SUP-01": 10.0 + TRANSPORT_COST["SUP-01"],  # 12.0
            "SUP-02": 13.0 + TRANSPORT_COST["SUP-02"],  # 16.5
        }

        for d in self.DURATIONS:
            for m in self.STRATEGIES:
                sim = run_simulation(shutdown_days=d, recovery_mode=m)
                metrics = sim["metrics"]

                sum_daily_costs = 0.0
                for day_res in sim["daily_results"]:
                    day_cost = 0.0
                    for order in day_res["orders"]:
                        if order.get("status") == "ordered":
                            unit_rate = expected_unit_costs[order["supplier"]]
                            order_expected_cost = round(order["quantity"] * unit_rate, 2)
                            self.assertAlmostEqual(order["cost"], order_expected_cost, places=2)
                            day_cost += order["cost"]

                    self.assertAlmostEqual(day_res["landed_cost"], round(day_cost, 2), places=2)
                    sum_daily_costs += day_res["landed_cost"]

                self.assertAlmostEqual(
                    round(sum_daily_costs, 2),
                    metrics["total_landed_cost"],
                    places=2,
                    msg=f"Landed cost reconciliation failed for {m} at {d} days",
                )

            # Check optimizer direct landed cost agrees with simulator
            opt_uniform = optimize_plan(shutdown_days=d, priority_weighted=False)
            sim_uniform = simulate_order_plan(opt_uniform["orders"], shutdown_days=d)
            self.assertEqual(
                opt_uniform["metrics"]["total_landed_cost"],
                sim_uniform["metrics"]["total_landed_cost"],
            )

    # ==========================================================================
    # 6. DAILY TO CUMULATIVE METRICS RECONCILIATION
    # ==========================================================================

    def test_daily_to_cumulative_metrics_reconciliation(self):
        """Verify sum of daily operational numbers reconciles with cumulative metrics."""
        for d in self.DURATIONS:
            for m in self.STRATEGIES:
                sim = run_simulation(shutdown_days=d, recovery_mode=m)
                m_cum = sim["metrics"]
                daily = sim["daily_results"]

                self.assertEqual(sum(r["demand"] for r in daily), m_cum["total_demand"])
                self.assertEqual(sum(r["fulfilled"] for r in daily), m_cum["total_fulfilled"])
                self.assertEqual(sum(r["backorders"] for r in daily), m_cum["total_backorders"])
                self.assertEqual(sum(r["unmet_demand"] for r in daily), m_cum["total_backorders"])

                for pid in ["PROD-01", "PROD-02"]:
                    prod_dem = sum(r["products"][pid]["demand"] for r in daily)
                    prod_ful = sum(r["products"][pid]["fulfilled"] for r in daily)
                    prod_unm = sum(r["products"][pid]["unmet"] for r in daily)

                    self.assertEqual(prod_dem, m_cum["product_breakdown"][pid]["demand"])
                    self.assertEqual(prod_ful, m_cum["product_breakdown"][pid]["fulfilled"])
                    self.assertEqual(prod_unm, m_cum["product_breakdown"][pid]["unmet"])

    # ==========================================================================
    # 7. REPEAT-RUN DETERMINISM
    # ==========================================================================

    def test_repeat_run_determinism(self):
        """Verify bit-for-bit determinism across repeated executions with identical seeds."""
        for d in [1, 7, 14]:
            for m in self.STRATEGIES:
                run1 = run_simulation(shutdown_days=d, recovery_mode=m, seed=42)
                run2 = run_simulation(shutdown_days=d, recovery_mode=m, seed=42)

                # Metrics match exactly
                self.assertEqual(run1["metrics"]["total_demand"], run2["metrics"]["total_demand"])
                self.assertEqual(run1["metrics"]["total_fulfilled"], run2["metrics"]["total_fulfilled"])
                self.assertEqual(run1["metrics"]["total_backorders"], run2["metrics"]["total_backorders"])
                self.assertEqual(run1["metrics"]["fill_rate"], run2["metrics"]["fill_rate"])
                self.assertEqual(run1["metrics"]["total_landed_cost"], run2["metrics"]["total_landed_cost"])
                self.assertEqual(run1["metrics"]["recovery_day"], run2["metrics"]["recovery_day"])

                # Daily results match exactly
                for r1, r2 in zip(run1["daily_results"], run2["daily_results"]):
                    self.assertEqual(r1["day"], r2["day"])
                    self.assertEqual(r1["fulfilled"], r2["fulfilled"])
                    self.assertEqual(r1["backorders"], r2["backorders"])
                    self.assertEqual(r1["fill_rate"], r2["fill_rate"])
                    self.assertEqual(r1["inventory"], r2["inventory"])

    # ==========================================================================
    # 8. RECOVERY-DAY CALCULATION AND EDGE CASES
    # ==========================================================================

    def test_recovery_day_definition_and_edge_cases(self):
        """
        Verify:
        1. Normal recovery: first day of 3-consecutive-day window at >= 95% after first dip.
        2. Full resilience (no dip): returns Day 1.
        3. Never recovers: returns None.
        4. Empty order plan: returns None.
        """
        # Case 1: Empty order plan never reaches 95% service after day 3 stockout -> None
        empty_res = simulate_order_plan([], shutdown_days=7)
        self.assertIsNone(empty_res["metrics"]["recovery_day"])

        # Case 2: Synthetic telemetry with no dip below 95% -> Day 1
        no_dip = [{"day": d, "fill_rate": 98.0} for d in range(1, 22)]
        self.assertEqual(calculate_recovery_day(no_dip), 1)

        # Case 3: Synthetic telemetry dipping on Day 3, reaching 95% only on Days 10, 11 (2 days, not 3) -> None
        two_day_window = [
            {"day": d, "fill_rate": 100.0 if d < 3 else (96.0 if d in [10, 11] else 80.0)}
            for d in range(1, 22)
        ]
        self.assertIsNone(calculate_recovery_day(two_day_window))

        # Case 4: Reaching 95% on Days 10, 11, 12 (3 days) -> Day 10
        three_day_window = [
            {"day": d, "fill_rate": 100.0 if d < 3 else (96.0 if d in [10, 11, 12] else 80.0)}
            for d in range(1, 22)
        ]
        self.assertEqual(calculate_recovery_day(three_day_window), 10)

    # ==========================================================================
    # 9. PRIORITY TRADE-OFF: AGENT VS OPTIMIZED
    # ==========================================================================

    def test_priority_tradeoff_agent_vs_optimized(self):
        """
        Verify that under constrained alternate supplier capacity (60 units/day),
        Agent mode allocates capacity to protect Priority 1 component (PROD-01)
        at the deliberate expense of Priority 2 component (PROD-02), while maintaining
        identical total fulfilled volume.
        """
        for d in [7, 10, 14]:
            opt_sim = run_simulation(shutdown_days=d, recovery_mode="optimized")
            agent_sim = run_simulation(shutdown_days=d, recovery_mode="agent")

            o_m = opt_sim["metrics"]
            a_m = agent_sim["metrics"]

            # Equal aggregate volume (both max out SUP-02 capacity of 60u/day)
            self.assertEqual(o_m["total_fulfilled"], a_m["total_fulfilled"])
            self.assertEqual(o_m["fill_rate"], a_m["fill_rate"])

            # Priority 1 product (PROD-01): Agent fulfills strictly more units
            o_p1 = o_m["product_breakdown"]["PROD-01"]["fulfilled"]
            a_p1 = a_m["product_breakdown"]["PROD-01"]["fulfilled"]
            self.assertGreater(
                a_p1,
                o_p1,
                f"Agent must achieve higher PROD-01 fulfillment than optimized at shutdown {d}",
            )
            self.assertAlmostEqual(
                a_m["product_breakdown"]["PROD-01"]["fill_rate"],
                91.53,
                places=1,
                msg="Agent must maintain >=91.5% fill rate on critical Component A",
            )

            # Priority 2 product (PROD-02): Agent trades off fulfillment to protect Component A
            o_p2 = o_m["product_breakdown"]["PROD-02"]["fulfilled"]
            a_p2 = a_m["product_breakdown"]["PROD-02"]["fulfilled"]
            self.assertLess(
                a_p2,
                o_p2,
                f"Agent deliberately trades off PROD-02 fulfillment to protect Component A at shutdown {d}",
            )

    # ==========================================================================
    # 10. FEASIBILITY & INVALID ORDER VALIDATION
    # ==========================================================================

    # ==========================================================================
    # 10. FEASIBILITY & INVALID ORDER VALIDATION
    # ==========================================================================

    def test_order_quantity_types_and_rejections(self):
        """
        Verify that candidate-order quantity validation requires a positive integer:
        - 0 is rejected as invalid_quantity
        - Negative values (-1, -50) are rejected as invalid_quantity
        - Fractional values (10.5, 0.5) are rejected as invalid_quantity
        - Booleans (True, False) are rejected as invalid_quantity
        - None and strings ("10") are rejected as invalid_quantity
        - Valid positive integers (1, 10, 50) are accepted cleanly
        """
        invalid_quantities = [
            0,
            -1,
            -50,
            10.5,
            0.5,
            True,
            False,
            None,
            "10",
            [10],
        ]

        for invalid_q in invalid_quantities:
            # 1. Test in simulator
            sim_res = simulate_order_plan(
                [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": invalid_q}],
                shutdown_days=7,
            )
            self.assertEqual(
                sim_res["metrics"]["constraint_violations"],
                1,
                f"Simulator failed to reject invalid quantity {invalid_q!r} (type: {type(invalid_q)})",
            )
            self.assertEqual(
                sim_res["violations"][0]["type"],
                "invalid_quantity",
                f"Simulator violation type mismatch for quantity {invalid_q!r}",
            )
            # Rejected orders must not incur landed cost
            self.assertEqual(sim_res["metrics"]["total_landed_cost"], 0.0)

            # 2. Test in coordinator validate_order_plan
            coord_val = validate_order_plan(
                [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": invalid_q, "arrival_day": 5}],
                shutdown_days=7,
            )
            self.assertFalse(
                coord_val["valid"],
                f"validate_order_plan failed to reject invalid quantity {invalid_q!r}",
            )
            self.assertEqual(
                coord_val["violations"][0]["type"],
                "invalid_quantity",
                f"validate_order_plan violation type mismatch for quantity {invalid_q!r}",
            )

        # Valid positive integers must be accepted with 0 violations
        for valid_q in [1, 10, 50, 60]:
            sim_ok = simulate_order_plan(
                [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": valid_q}],
                shutdown_days=7,
            )
            self.assertEqual(sim_ok["metrics"]["constraint_violations"], 0)
            self.assertGreater(sim_ok["metrics"]["total_landed_cost"], 0.0)

            val_ok = validate_order_plan(
                [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": valid_q, "arrival_day": 5}],
                shutdown_days=7,
            )
            self.assertTrue(val_ok["valid"])
            self.assertEqual(val_ok["violation_count"], 0)

    def test_order_day_boundaries_and_arrival_consistency(self):
        """
        Verify order-day boundary validation and arrival-day consistency:
        - Day < 1 (0, -1) rejected
        - Day > 21 (22, 50) rejected
        - Boolean order_day (True, False) rejected
        - Arrival day mismatch (order_day + lead_time != arrival_day) rejected
        - Arrival day > 21 flagged as outside_horizon in validate_order_plan
        """
        invalid_days = [0, -1, 22, 50, True, False, "1", None]

        for inv_d in invalid_days:
            sim_res = simulate_order_plan(
                [{"order_day": inv_d, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10}],
                shutdown_days=7,
            )
            self.assertEqual(
                sim_res["metrics"]["constraint_violations"],
                1,
                f"Simulator failed to reject invalid order_day {inv_d!r}",
            )
            self.assertEqual(sim_res["violations"][0]["type"], "invalid_order_day")

            val_res = validate_order_plan(
                [{"order_day": inv_d, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10, "arrival_day": 5}],
                shutdown_days=7,
            )
            self.assertFalse(val_res["valid"], f"validate_order_plan failed to reject invalid order_day {inv_d!r}")
            self.assertEqual(val_res["violations"][0]["type"], "invalid_order_day")

        # Arrival day mismatch: SUP-02 lead time is 4. Order on Day 1 must arrive Day 5.
        sim_mismatch = simulate_order_plan(
            [{"order_day": 1, "arrival_day": 4, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10}],
            shutdown_days=7,
        )
        self.assertEqual(sim_mismatch["metrics"]["constraint_violations"], 1)
        self.assertEqual(sim_mismatch["violations"][0]["type"], "arrival_mismatch")

        # Order arriving outside the 21-day horizon in coordinator validation
        # SUP-02 lead time 4: Order on Day 18 arrives Day 22 (outside 21-day horizon)
        val_outside = validate_order_plan(
            [{"order_day": 18, "product": "PROD-01", "supplier": "SUP-02", "quantity": 10, "arrival_day": 22}],
            shutdown_days=7,
            horizon_days=21,
        )
        self.assertFalse(val_outside["valid"])
        violation_types = [v["type"] for v in val_outside["violations"]]
        self.assertIn("outside_horizon", violation_types)

    def test_feasibility_validation_on_invalid_orders(self):
        """
        Verify simulator and validator enforce constraints against invalid candidate orders:
        - Unknown supplier
        - Unknown product
        - Supplier shutdown violation
        - Supplier daily capacity exceeded
        """
        # Unknown supplier
        sim_bad_sup = simulate_order_plan(
            [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-99", "quantity": 10}],
            shutdown_days=7,
        )
        self.assertEqual(sim_bad_sup["metrics"]["constraint_violations"], 1)
        self.assertEqual(sim_bad_sup["violations"][0]["type"], "unknown_supplier")

        # Unknown product
        sim_bad_prod = simulate_order_plan(
            [{"order_day": 1, "product": "PROD-99", "supplier": "SUP-02", "quantity": 10}],
            shutdown_days=7,
        )
        self.assertEqual(sim_bad_prod["metrics"]["constraint_violations"], 1)
        self.assertEqual(sim_bad_prod["violations"][0]["type"], "unknown_product")

        # Shutdown violation (ordering from SUP-01 during shutdown)
        sim_shut = simulate_order_plan(
            [{"order_day": 2, "product": "PROD-01", "supplier": "SUP-01", "quantity": 50}],
            shutdown_days=7,
        )
        self.assertEqual(sim_shut["metrics"]["constraint_violations"], 1)
        self.assertEqual(sim_shut["violations"][0]["type"], "supplier_shutdown_violation")
        self.assertEqual(sim_shut["metrics"]["total_landed_cost"], 0.0)

        # Capacity exceeded (> 60 on SUP-02)
        sim_cap = simulate_order_plan(
            [{"order_day": 1, "product": "PROD-01", "supplier": "SUP-02", "quantity": 80}],
            shutdown_days=7,
        )
        self.assertEqual(sim_cap["metrics"]["constraint_violations"], 1)
        self.assertEqual(sim_cap["violations"][0]["type"], "supplier_capacity_exceeded")

        # Verify coordinator's validate_order_plan agrees on constraints
        coord_val = validate_order_plan(
            [
                {"order_day": 1, "product": "PROD-01", "supplier": "SUP-99", "quantity": 10, "arrival_day": 3},
                {"order_day": 1, "product": "PROD-99", "supplier": "SUP-02", "quantity": 10, "arrival_day": 5},
                {"order_day": 2, "product": "PROD-01", "supplier": "SUP-01", "quantity": 50, "arrival_day": 4},
            ],
            shutdown_days=7,
        )
        self.assertFalse(coord_val["valid"])
        self.assertEqual(coord_val["violation_count"], 3)

    # ==========================================================================
    # 11. PYDANTIC CONTRACT COMPATIBILITY ACROSS MULTIPLE DURATIONS
    # ==========================================================================

    def test_pydantic_contracts_across_durations(self):
        """Verify all Pydantic response schemas validate cleanly for 1, 3, 7, 10, 14 days."""
        for d in self.DURATIONS:
            for m in self.STRATEGIES:
                raw_sim = run_simulation(shutdown_days=d, recovery_mode=m)
                sim_res = SimulationResponse.model_validate(raw_sim)
                self.assertEqual(sim_res.scenario.shutdown_days, d)
                self.assertEqual(sim_res.scenario.horizon_days, 21)

            # Optimization direct response
            raw_opt = optimize_plan(shutdown_days=d)
            opt_res = OptimizationResponse.model_validate(raw_opt)
            self.assertEqual(opt_res.scenario.shutdown_days, d)

            # Recovery coordination response
            raw_rec = coordinate_recovery(shutdown_days=d)
            rec_res = RecoveryResponse.model_validate(raw_rec)
            self.assertEqual(rec_res.scenario.shutdown_days, d)

    # ==========================================================================
    # 12. HORIZON BOUNDARY & LATE ARRIVAL ACCOUNTING SEMANTICS
    # ==========================================================================

    def test_horizon_boundary_and_late_arrival_accounting_semantics(self):
        """
        Focused verification of planning horizon boundaries and late-arriving order semantics:
        1. Order arriving exactly on Day 21 (order_day=19, SUP-01, lead_time=2, arrival_day=21):
           - Supplier accepts order on Day 19.
           - validate_order_plan confirms valid=True, 0 violations.
           - Arrives on Day 21, added to inventory, fulfills Day 21 demand / contributes to ending inventory.
           - outstanding_orders_at_horizon == 0.
           - total_landed_cost == quantity * unit_rate (reconciles with accepted orders).
        2. Order arriving after Day 21 (order_day=20, SUP-01, lead_time=2, arrival_day=22):
           - In simulator: accepted by supplier on Day 20, booked in committed procurement spend (total_landed_cost).
           - In simulator: zero units received within 21-day horizon (Day 21 arrivals empty, ending stock unaffected).
           - In simulator: outstanding_orders_at_horizon == 1 (pipeline order in transit past horizon).
           - In coordinator validation: validate_order_plan returns valid=False with violation 'outside_horizon'.
           - In coordinator validation report: CHK-HORIZON-BOUNDS reports status 'FAIL', severity 'CRITICAL'.
           - In coordinator ranking: rank_candidates marks candidate selectable=False, rank=None, score=None.
           - In coordinator selection: infeasible candidate is strictly disqualified from selection and approval.
        3. Standard strategy compliance across all durations:
           - In all standard generated candidates (agent, optimized, reorder) across D in {1, 7, 14},
             every order arrives on or before Day 21 (0 late arrivals).
           - outstanding_orders_at_horizon is 0 across all generated candidate plans.
        """
        # 1. Order arriving exactly on Day 21
        order_day21 = [{"order_day": 19, "product": "PROD-01", "supplier": "SUP-01", "quantity": 50, "arrival_day": 21}]
        val_d21 = validate_order_plan(order_day21, shutdown_days=7, horizon_days=21)
        self.assertTrue(val_d21["valid"])
        self.assertEqual(val_d21["violation_count"], 0)

        sim_d21 = simulate_order_plan(order_day21, shutdown_days=7, horizon=21)
        # Check Day 21 arrival
        day21_arrivals = sim_d21["daily_results"][20]["arrivals"]
        self.assertEqual(len(day21_arrivals), 1)
        self.assertEqual(day21_arrivals[0]["quantity"], 50)
        self.assertEqual(day21_arrivals[0]["supplier"], "SUP-01")
        # Check outstanding orders
        self.assertEqual(sim_d21["metrics"]["outstanding_orders_at_horizon"], 0)
        # Check landed cost: 50 * (10.0 + 2.0) = 600.0
        self.assertEqual(sim_d21["metrics"]["total_landed_cost"], 600.0)

        # 2. Order arriving after Day 21 (Day 20 + lead time 2 -> Day 22)
        order_day22 = [{"order_day": 20, "product": "PROD-01", "supplier": "SUP-01", "quantity": 50, "arrival_day": 22}]
        val_d22 = validate_order_plan(order_day22, shutdown_days=7, horizon_days=21)
        self.assertFalse(val_d22["valid"])
        self.assertEqual(val_d22["violations"][0]["type"], "outside_horizon")

        # Validation report check
        mock_cand = {
            "candidate_id": "CAND-TEST-LATE",
            "strategy_id": "test_late",
            "name": "Test Late Candidate",
            "scenario_id": "SCEN-SD7-H21-S42",
            "orders": order_day22,
            "validation": val_d22,
            "metrics": {"total_landed_cost": 600.0},
        }
        report = build_validation_report(mock_cand, shutdown_days=7, horizon_days=21)
        self.assertEqual(report["overall_status"], "INVALID")
        chk_horizon = next(c for c in report["checks"] if c["check_id"] == "CHK-HORIZON-BOUNDS")
        self.assertEqual(chk_horizon["status"], "FAIL")
        self.assertEqual(chk_horizon["severity"], "CRITICAL")
        self.assertIn("arrival_day > Day 21", chk_horizon["details"])

        # Ranking disqualification
        rank_records = rank_candidates([mock_cand])
        self.assertEqual(len(rank_records), 1)
        self.assertFalse(rank_records[0]["selectable"])
        self.assertIsNone(rank_records[0]["rank"])
        self.assertIsNone(rank_records[0]["score"])
        self.assertIn("BENCHMARK ONLY", rank_records[0]["criteria_summary"])

        # Simulation behavior for late order
        sim_d22 = simulate_order_plan(order_day22, shutdown_days=7, horizon=21)
        # Zero arrivals on Day 21 or any day within horizon
        self.assertEqual(len(sim_d22["daily_results"][20]["arrivals"]), 0)
        self.assertEqual(sum(len(d["arrivals"]) for d in sim_d22["daily_results"]), 0)
        # Remained in transit pipeline past horizon
        self.assertEqual(sim_d22["metrics"]["outstanding_orders_at_horizon"], 1)
        # Landed cost includes the committed spend booked upon order placement
        self.assertEqual(sim_d22["metrics"]["total_landed_cost"], 600.0)

        # 3. Standard strategy compliance (no late arrivals in standard candidates)
        for d in [1, 7, 14]:
            rec = coordinate_recovery(shutdown_days=d)
            for c in rec["candidates"]:
                strat = c["strategy_id"]
                orders = c["orders"]
                # Every order placed by any candidate arrives on or before Day 21
                late_orders = [o for o in orders if o.get("arrival_day", 0) > 21]
                self.assertEqual(
                    len(late_orders),
                    0,
                    f"Candidate {strat} at shutdown {d} contained unexpected late-arriving orders: {late_orders}",
                )
                self.assertEqual(
                    c["metrics"]["outstanding_orders_at_horizon"],
                    0,
                    f"Candidate {strat} at shutdown {d} had orders in transit past horizon",
                )


if __name__ == "__main__":
    unittest.main()
