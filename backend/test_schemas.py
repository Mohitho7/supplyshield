"""
SupplyShield AI — Contract Validation Test Suite (Phase B0)

Verifies that all domain entities, scenario inputs, operational metrics, orders,
specialist agent outputs, constraint validations, and API response structures
strictly satisfy the Phase B0 schemas.
"""

import unittest
from pydantic import ValidationError

from simulator import run_simulation, NETWORK, HORIZON
from optimizer import optimize_plan
from coordinator import coordinate_recovery
from schemas import (
    ScenarioConfig,
    NetworkTopology,
    SimulationResponse,
    OptimizationResponse,
    RecoveryResponse,
    ComparisonResponse,
    SimulationMetrics,
    DailyResult,
    AgentProposal,
    ValidationResult,
)


class TestContractSchemas(unittest.TestCase):
    """Contract and schema boundary tests for SupplyShield AI."""

    # ==========================================================================
    # 1. SCENARIO INPUT VALIDATION
    # ==========================================================================

    def test_scenario_valid_inputs(self):
        """Valid 1-day, 7-day, and 14-day scenarios must validate cleanly."""
        for days in [1, 7, 14]:
            sc = ScenarioConfig(shutdown_days=days)
            self.assertEqual(sc.shutdown_days, days)
            self.assertEqual(sc.horizon_days, 21)

    def test_scenario_boundary_rejections(self):
        """Zero-day, negative, and >14-day shutdowns must be rejected by the schema."""
        with self.assertRaises(ValidationError):
            ScenarioConfig(shutdown_days=0)

        with self.assertRaises(ValidationError):
            ScenarioConfig(shutdown_days=-5)

        with self.assertRaises(ValidationError):
            ScenarioConfig(shutdown_days=15)

    def test_scenario_strategy_mode_validation(self):
        """Only 'reorder', 'optimized', and 'agent' policy modes are permitted."""
        for mode in ["reorder", "optimized", "agent"]:
            sc = ScenarioConfig(shutdown_days=7, recovery_mode=mode)
            self.assertEqual(sc.recovery_mode, mode)

        with self.assertRaises(ValidationError):
            ScenarioConfig(shutdown_days=7, recovery_mode="unsupported_strategy")

    # ==========================================================================
    # 2. NETWORK ENTITY VALIDATION
    # ==========================================================================

    def test_network_schema_validation(self):
        """The synthetic network topology must validate against NetworkTopology."""
        net = NetworkTopology.model_validate(NETWORK)
        self.assertEqual(len(net.suppliers), 2)
        self.assertEqual(len(net.factories), 2)
        self.assertEqual(len(net.distribution_centers), 2)
        self.assertEqual(len(net.products), 2)

        # Check explicit attributes
        sup1 = next(s for s in net.suppliers if s.id == "SUP-01")
        self.assertEqual(sup1.capacity, 100)
        self.assertEqual(sup1.lead_time, 2)
        self.assertEqual(sup1.unit_cost, 10.0)

        prod1 = next(p for p in net.products if p.id == "PROD-01")
        self.assertEqual(prod1.daily_demand, 45)
        self.assertEqual(prod1.initial_inventory, 100)
        self.assertEqual(prod1.priority, 1)

    # ==========================================================================
    # 3. SIMULATION RESPONSE VALIDATION (ALL 3 STRATEGIES)
    # ==========================================================================

    def test_simulation_responses_validate(self):
        """All three planning strategies must produce valid SimulationResponse payloads."""
        for mode in ["reorder", "optimized", "agent"]:
            raw_result = run_simulation(shutdown_days=7, recovery_mode=mode)
            validated = SimulationResponse.model_validate(raw_result)

            # Assert top-level keys
            self.assertEqual(validated.scenario.shutdown_days, 7)
            self.assertEqual(validated.scenario.horizon_days, 21)
            self.assertEqual(len(validated.daily_results), 21)

            # Assert metric integrity
            m = validated.metrics
            self.assertEqual(m.total_demand, 1680)
            self.assertEqual(m.total_fulfilled + m.total_backorders, 1680)
            self.assertTrue(0.0 <= m.fill_rate <= 100.0)
            self.assertGreater(m.total_landed_cost, 0.0)
            if mode in ["optimized", "agent"]:
                self.assertEqual(m.constraint_violations, 0)
            else:
                self.assertEqual(m.constraint_violations, 14)
            self.assertIsNotNone(m.product_breakdown)
            self.assertIn("PROD-01", m.product_breakdown)
            self.assertIn("PROD-02", m.product_breakdown)

            # Strategy metadata must exist
            self.assertIsNotNone(validated.strategy_info)
            self.assertEqual(validated.strategy_info.id, mode)

    # ==========================================================================
    # 4. OPTIMIZATION RESPONSE VALIDATION
    # ==========================================================================

    def test_optimization_response_validates(self):
        """Direct optimizer output must validate against OptimizationResponse."""
        raw_opt = optimize_plan(shutdown_days=7, priority_weighted=False)
        validated = OptimizationResponse.model_validate(raw_opt)

        self.assertIn(validated.status, {"OPTIMAL", "FEASIBLE"})
        self.assertEqual(validated.scenario.shutdown_days, 7)
        self.assertGreater(len(validated.orders), 0)
        self.assertEqual(len(validated.daily_results), 21)
        self.assertEqual(validated.metrics.total_demand, 1680)
        self.assertGreater(validated.metrics.total_landed_cost, 0.0)
        self.assertGreater(len(validated.limitations), 0)

    # ==========================================================================
    # 5. RECOVERY ORCHESTRATION & AGENTS VALIDATION
    # ==========================================================================

    def test_recovery_response_validates(self):
        """Recovery coordination must preserve all 4 agent reports, validation, and recommendation."""
        raw_rec = coordinate_recovery(shutdown_days=7)
        validated = RecoveryResponse.model_validate(raw_rec)

        # Status
        self.assertEqual(validated.status, "awaiting_planner_approval")

        # Agents
        agents = validated.agents
        self.assertGreater(len(agents.demand), 0)
        self.assertGreater(len(agents.inventory), 0)
        self.assertGreater(len(agents.supplier_risk), 0)
        self.assertGreater(len(agents.logistics), 0)

        for proposal in agents.demand + agents.inventory + agents.supplier_risk + agents.logistics:
            self.assertIsInstance(proposal, AgentProposal)
            self.assertTrue(0.0 <= proposal.confidence <= 1.0)
            self.assertTrue(len(proposal.recommendation) > 0)
            self.assertTrue(len(proposal.reason) > 0)

        # Deterministic validation
        self.assertTrue(validated.validation.valid)
        self.assertEqual(validated.validation.violation_count, 0)
        self.assertEqual(len(validated.validation.violations), 0)

        # Recommendation and human governance
        rec = validated.recommendation
        self.assertIsNotNone(rec)
        self.assertTrue(rec.planner_approval_required)
        self.assertFalse(rec.approved)
        self.assertIn("SUP-02", rec.summary)
        self.assertTrue(len(rec.generated_at) > 0)

    # ==========================================================================
    # 6. COMPARISON BENCHMARK VALIDATION
    # ==========================================================================

    def test_comparison_response_validates(self):
        """Comparison benchmark payload must validate and contain all 3 strategy schemas."""
        comp_data = {
            "scenario": {
                "shutdown_days": 7,
                "horizon_days": 21,
            },
            "strategies": {
                "reorder": run_simulation(shutdown_days=7, recovery_mode="reorder"),
                "optimized": run_simulation(shutdown_days=7, recovery_mode="optimized"),
                "agent": run_simulation(shutdown_days=7, recovery_mode="agent"),
            },
        }
        validated = ComparisonResponse.model_validate(comp_data)
        self.assertEqual(validated.scenario.shutdown_days, 7)
        self.assertEqual(validated.strategies.reorder.scenario.recovery_mode, "reorder")
        self.assertEqual(validated.strategies.optimized.scenario.recovery_mode, "optimized")
        self.assertEqual(validated.strategies.agent.scenario.recovery_mode, "agent")

    # ==========================================================================
    # 7. METRIC INTEGRITY AT THE CONTRACT BOUNDARY
    # ==========================================================================

    def test_metric_missing_mandatory_fields_rejected(self):
        """Missing mandatory metric fields must raise ValidationError rather than defaulting silently."""
        incomplete_metrics = {
            "total_demand": 1680,
            # 'total_fulfilled' omitted
            "total_backorders": 245,
            "fill_rate": 85.42,
            "total_landed_cost": 16470.0,
            "ending_inventory": {"PROD-01": 0, "PROD-02": 0},
            "outstanding_orders_at_horizon": 0,
        }
        with self.assertRaises(ValidationError):
            SimulationMetrics.model_validate(incomplete_metrics)

    def test_metric_nullable_recovery_day(self):
        """Recovery day can be None if target is not achieved within horizon."""
        valid_with_none = {
            "total_demand": 1680,
            "total_fulfilled": 1000,
            "total_backorders": 680,
            "fill_rate": 59.52,
            "total_landed_cost": 12000.0,
            "recovery_day": None,
            "ending_inventory": {"PROD-01": 0, "PROD-02": 0},
            "outstanding_orders_at_horizon": 0,
            "constraint_violations": 0,
        }
        m = SimulationMetrics.model_validate(valid_with_none)
        self.assertIsNone(m.recovery_day)


if __name__ == "__main__":
    unittest.main()
