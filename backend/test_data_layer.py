"""
SupplyShield AI — Data Layer Unit & Regression Test Suite (Phase D7)

Tests:
1. Canonical dataset loading and structural integrity.
2. Deterministic SHA-256 fingerprint reproducibility and order-invariance.
3. Sensitivity to material data modifications.
4. Relational & business rule validation (duplicate IDs, dangling references, cost reconciliation).
5. Non-negativity constraints (capacity, lead time, costs, inventory).
6. Missing files and malformed JSON fail-safe behavior.
7. Singleton snapshot caching ('load once, use one snapshot').
8. Conversion adapters to simulator dictionary topology.
9. Offline CLI validation tool execution and exit codes.
10. End-to-end benchmark parity verification for D=1, D=7, and D=14.
"""

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from data_repository import (
    DEFAULT_DATASETS_DIR,
    ACTIVE_DATASET_ID,
    compute_dataset_fingerprint,
    validate_and_load_dataset,
    get_active_dataset,
    set_active_dataset,
    reset_active_dataset,
    DataQualityError,
    validate_dataset_cli,
    SupplyChainDataset,
    DataStatusResponse,
)
from simulator import run_simulation, simulate_order_plan, NETWORK, TRANSPORT_COST, HORIZON
from coordinator import coordinate_recovery


class TestDataRepository(unittest.TestCase):
    """Unit tests for the canonical dataset loading, fingerprinting, and validation pipeline."""

    def setUp(self):
        self.canonical_dir = DEFAULT_DATASETS_DIR / ACTIVE_DATASET_ID
        self.assertTrue(self.canonical_dir.is_dir(), f"Canonical dataset directory not found at {self.canonical_dir}")

    def test_canonical_dataset_loads_successfully(self):
        """The canonical demo_v1 dataset must load cleanly without errors or schema violations."""
        dataset, report = validate_and_load_dataset(self.canonical_dir)
        self.assertEqual(report.status, "VALID")
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.supplier_count, 2)
        self.assertEqual(report.product_count, 2)
        self.assertEqual(report.node_count, 6)
        self.assertEqual(report.edge_count, 6)
        self.assertEqual(dataset.dataset_id, "demo_v1")
        self.assertEqual(dataset.dataset_version, "1.0.0")
        self.assertEqual(dataset.manifest.source_type, "synthetic_demo")
        self.assertTrue(dataset.manifest.is_synthetic)
        self.assertIn("Primary supplier SUP-01 is subject to deterministic shutdown outage", dataset.manifest.limitations[1])

    def test_fingerprint_determinism_and_repeatability(self):
        """Repeated loading of identical data produces the exact same cryptographic fingerprint."""
        ds1, rep1 = validate_and_load_dataset(self.canonical_dir)
        ds2, rep2 = validate_and_load_dataset(self.canonical_dir)
        self.assertEqual(ds1.fingerprint, ds2.fingerprint)
        self.assertEqual(rep1.dataset_fingerprint, rep2.dataset_fingerprint)
        self.assertEqual(len(ds1.fingerprint), 64)

    def test_fingerprint_invariance_to_json_key_order(self):
        """Harmless dictionary key reordering must not change the semantic content fingerprint."""
        with open(self.canonical_dir / "dataset_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(self.canonical_dir / "suppliers.json", "r", encoding="utf-8") as f:
            suppliers = json.load(f)
        with open(self.canonical_dir / "products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        with open(self.canonical_dir / "inventory.json", "r", encoding="utf-8") as f:
            inventory = json.load(f)
        with open(self.canonical_dir / "demand_profiles.json", "r", encoding="utf-8") as f:
            demand = json.load(f)
        with open(self.canonical_dir / "cost_config.json", "r", encoding="utf-8") as f:
            cost_config = json.load(f)
        with open(self.canonical_dir / "scenarios.json", "r", encoding="utf-8") as f:
            scenarios = json.load(f)
        with open(self.canonical_dir / "network.json", "r", encoding="utf-8") as f:
            network = json.load(f)

        fp_original = compute_dataset_fingerprint(
            manifest, suppliers, products, inventory, demand, cost_config, scenarios, network
        )

        # Invert key ordering in manifest and cost_config
        reversed_manifest = {k: manifest[k] for k in reversed(list(manifest.keys()))}
        reversed_cost = {k: cost_config[k] for k in reversed(list(cost_config.keys()))}

        fp_reordered = compute_dataset_fingerprint(
            reversed_manifest, suppliers, products, inventory, demand, reversed_cost, scenarios, network
        )
        self.assertEqual(fp_original, fp_reordered, "Fingerprint changed upon harmless JSON key reordering!")

    def test_fingerprint_changes_on_material_data_modification(self):
        """Material change to supplier cost or inventory must alter the fingerprint."""
        with open(self.canonical_dir / "dataset_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(self.canonical_dir / "suppliers.json", "r", encoding="utf-8") as f:
            suppliers = json.load(f)
        with open(self.canonical_dir / "products.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        with open(self.canonical_dir / "inventory.json", "r", encoding="utf-8") as f:
            inventory = json.load(f)
        with open(self.canonical_dir / "demand_profiles.json", "r", encoding="utf-8") as f:
            demand = json.load(f)
        with open(self.canonical_dir / "cost_config.json", "r", encoding="utf-8") as f:
            cost_config = json.load(f)
        with open(self.canonical_dir / "scenarios.json", "r", encoding="utf-8") as f:
            scenarios = json.load(f)
        with open(self.canonical_dir / "network.json", "r", encoding="utf-8") as f:
            network = json.load(f)

        fp_base = compute_dataset_fingerprint(
            manifest, suppliers, products, inventory, demand, cost_config, scenarios, network
        )

        mod_suppliers = copy.deepcopy(suppliers)
        mod_suppliers[0]["unit_cost"] = 11.50
        fp_mod = compute_dataset_fingerprint(
            manifest, mod_suppliers, products, inventory, demand, cost_config, scenarios, network
        )
        self.assertNotEqual(fp_base, fp_mod, "Fingerprint failed to detect unit_cost change!")

    def test_rejection_of_duplicate_supplier_ids(self):
        """Duplicate supplier IDs must fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree(self.canonical_dir, tmppath / "dataset", dirs_exist_ok=True)
            supp_file = tmppath / "dataset" / "suppliers.json"
            with open(supp_file, "r") as f:
                data = json.load(f)
            data.append(copy.deepcopy(data[0]))
            with open(supp_file, "w") as f:
                json.dump(data, f)

            with self.assertRaises(DataQualityError) as ctx:
                validate_and_load_dataset(tmppath / "dataset")
            self.assertIn("Duplicate supplier ID", str(ctx.exception))

    def test_rejection_of_duplicate_product_ids(self):
        """Duplicate product IDs must fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree(self.canonical_dir, tmppath / "dataset", dirs_exist_ok=True)
            prod_file = tmppath / "dataset" / "products.json"
            with open(prod_file, "r") as f:
                data = json.load(f)
            data.append(copy.deepcopy(data[0]))
            with open(prod_file, "w") as f:
                json.dump(data, f)

            with self.assertRaises(DataQualityError) as ctx:
                validate_and_load_dataset(tmppath / "dataset")
            self.assertIn("Duplicate product ID", str(ctx.exception))

    def test_rejection_of_missing_product_inventory_reference(self):
        """Inventory referring to unknown product SKU must fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree(self.canonical_dir, tmppath / "dataset", dirs_exist_ok=True)
            inv_file = tmppath / "dataset" / "inventory.json"
            with open(inv_file, "r") as f:
                data = json.load(f)
            data.append({
                "product_id": "PROD-999-GHOST",
                "initial_inventory": 50,
                "unit_of_measure": "units",
            })
            with open(inv_file, "w") as f:
                json.dump(data, f)

            with self.assertRaises(DataQualityError) as ctx:
                validate_and_load_dataset(tmppath / "dataset")
            self.assertIn("PROD-999-GHOST", str(ctx.exception))

    def test_rejection_of_dangling_network_edge(self):
        """Network directed edge referencing nonexistent node must fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree(self.canonical_dir, tmppath / "dataset", dirs_exist_ok=True)
            net_file = tmppath / "dataset" / "network.json"
            with open(net_file, "r") as f:
                data = json.load(f)
            data["edges"].append({
                "source": "SUP-01",
                "target": "FAC-999-NONEXISTENT",
                "type": "raw_material_inbound",
                "lead_time_days": 2,
            })
            with open(net_file, "w") as f:
                json.dump(data, f)

            with self.assertRaises(DataQualityError) as ctx:
                validate_and_load_dataset(tmppath / "dataset")
            self.assertIn("FAC-999-NONEXISTENT", str(ctx.exception))

    def test_rejection_of_cost_reconciliation_mismatch(self):
        """Landed cost mismatching procurement + freight must fail validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree(self.canonical_dir, tmppath / "dataset", dirs_exist_ok=True)
            cost_file = tmppath / "dataset" / "cost_config.json"
            with open(cost_file, "r") as f:
                data = json.load(f)
            # Make SUP-01 landed cost inconsistent (10 + 2 != 15)
            data["landed_unit_costs"]["SUP-01"] = 15.00
            with open(cost_file, "w") as f:
                json.dump(data, f)

            with self.assertRaises(DataQualityError) as ctx:
                validate_and_load_dataset(tmppath / "dataset")
            self.assertIn("Cost mismatch for supplier 'SUP-01'", str(ctx.exception))

    def test_rejection_of_negative_values(self):
        """Negative inventory, capacity, or cost must fail Pydantic validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            shutil.copytree(self.canonical_dir, tmppath / "dataset", dirs_exist_ok=True)
            inv_file = tmppath / "dataset" / "inventory.json"
            with open(inv_file, "r") as f:
                data = json.load(f)
            data[0]["initial_inventory"] = -50
            with open(inv_file, "w") as f:
                json.dump(data, f)

            with self.assertRaises(DataQualityError) as ctx:
                validate_and_load_dataset(tmppath / "dataset")
            self.assertIn("Inventory schema validation error", str(ctx.exception))

    def test_missing_dataset_directory_fails_safely(self):
        """Nonexistent dataset directory must raise DataQualityError safely."""
        fake_path = self.canonical_dir.parent / "nonexistent_v99"
        with self.assertRaises(DataQualityError):
            validate_and_load_dataset(fake_path)

    def test_offline_cli_validation(self):
        """validate_dataset_cli must return code 0 on valid dataset and code 1 on invalid."""
        code_valid = validate_dataset_cli(str(self.canonical_dir))
        self.assertEqual(code_valid, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            code_invalid = validate_dataset_cli(str(tmpdir))
            self.assertEqual(code_invalid, 1)

    def test_singleton_snapshot_caching(self):
        """get_active_dataset loads once and returns the cached snapshot thereafter."""
        reset_active_dataset()
        ds1 = get_active_dataset()
        ds2 = get_active_dataset()
        self.assertIs(ds1, ds2, "get_active_dataset did not return cached singleton instance")

    def test_to_network_dict_and_transport_cost(self):
        """Dataset conversion methods must produce valid structures matching simulator.NETWORK."""
        dataset = get_active_dataset()
        net = dataset.to_network_dict()
        transport = dataset.to_transport_cost_dict()

        self.assertEqual(len(net["suppliers"]), 2)
        self.assertEqual(len(net["factories"]), 2)
        self.assertEqual(len(net["distribution_centers"]), 2)
        self.assertEqual(len(net["products"]), 2)
        self.assertEqual(transport["SUP-01"], 2.0)
        self.assertEqual(transport["SUP-02"], 3.5)

        # Check exact field names and types
        sup1 = next(s for s in net["suppliers"] if s["id"] == "SUP-01")
        self.assertEqual(sup1["capacity"], 100)
        self.assertEqual(sup1["lead_time"], 2)
        self.assertEqual(sup1["unit_cost"], 10.0)

    def test_to_data_status(self):
        """to_data_status returns strongly-typed status object without secrets or local paths."""
        dataset = get_active_dataset()
        status = dataset.to_data_status()
        self.assertIsInstance(status, DataStatusResponse)
        self.assertEqual(status.dataset_id, "demo_v1")
        self.assertEqual(status.validation_status, "VALID")
        self.assertEqual(status.error_count, 0)
        self.assertNotIn("Users", status.summary)
        self.assertNotIn("OneDrive", status.summary)


class TestBenchmarkParityWithDataLayer(unittest.TestCase):
    """
    Exact mathematical, product-level, and operational parity check across D=1, D=7, and D=14.
    Ensures that migrating configuration to the canonical data layer preserved 100%
    of validated engine behavior across all three strategies (Agent, Optimized, Reorder).
    """

    def test_d1_complete_benchmark_parity(self):
        """Verify D=1 complete product-level and strategy benchmark metrics with active data layer."""
        res = coordinate_recovery(shutdown_days=1)
        cand_map = {c["strategy_id"]: c for c in res["candidates"]}
        rank_map = {r["strategy_id"]: r for r in res["rankings"]}

        # 1. Agent Candidate (Selected)
        agent_c = cand_map["agent"]
        agent_m = agent_c["metrics"]
        agent_pb = agent_m["product_breakdown"]
        self.assertEqual(agent_pb["PROD-01"]["fulfilled"], 910)
        self.assertEqual(agent_pb["PROD-01"]["demand"], 945)
        self.assertEqual(agent_pb["PROD-01"]["fill_rate"], 96.30)
        self.assertEqual(agent_pb["PROD-02"]["fulfilled"], 705)
        self.assertEqual(agent_pb["PROD-02"]["demand"], 735)
        self.assertEqual(agent_pb["PROD-02"]["fill_rate"], 95.92)
        self.assertEqual(agent_m["total_fulfilled"], 1615)
        self.assertEqual(agent_m["total_demand"], 1680)
        self.assertEqual(agent_m["fill_rate"], 96.13)
        self.assertEqual(agent_m["total_backorders"], 65)
        self.assertEqual(agent_m["total_landed_cost"], 17280.0)
        self.assertEqual(agent_m["recovery_day"], 4)
        self.assertTrue(agent_c["validation"]["valid"])
        self.assertEqual(rank_map["agent"]["rank"], 1)
        self.assertEqual(rank_map["agent"]["score"], 14443.38)
        self.assertEqual(res["selection"]["selected_strategy_id"], "agent")

        # 2. Optimized Candidate
        opt_c = cand_map["optimized"]
        opt_m = opt_c["metrics"]
        opt_pb = opt_m["product_breakdown"]
        self.assertEqual(opt_pb["PROD-01"]["fulfilled"], 910)
        self.assertEqual(opt_pb["PROD-01"]["demand"], 945)
        self.assertEqual(opt_pb["PROD-02"]["fulfilled"], 705)
        self.assertEqual(opt_pb["PROD-02"]["demand"], 735)
        self.assertEqual(opt_m["total_fulfilled"], 1615)
        self.assertEqual(opt_m["total_demand"], 1680)
        self.assertEqual(opt_m["fill_rate"], 96.13)
        self.assertEqual(opt_m["total_backorders"], 65)
        self.assertEqual(opt_m["total_landed_cost"], 17280.0)
        self.assertEqual(opt_m["recovery_day"], 4)
        self.assertTrue(opt_c["validation"]["valid"])
        self.assertEqual(rank_map["optimized"]["rank"], 2)
        self.assertEqual(rank_map["optimized"]["score"], 14443.38)

        # 3. Reorder Candidate (Infeasible)
        reorder_c = cand_map["reorder"]
        reorder_m = reorder_c["metrics"]
        reorder_pb = reorder_m["product_breakdown"]
        self.assertEqual(reorder_pb["PROD-01"]["fulfilled"], 910)
        self.assertEqual(reorder_pb["PROD-01"]["demand"], 945)
        self.assertEqual(reorder_pb["PROD-02"]["fulfilled"], 670)
        self.assertEqual(reorder_pb["PROD-02"]["demand"], 735)
        self.assertEqual(reorder_m["total_fulfilled"], 1580)
        self.assertEqual(reorder_m["total_demand"], 1680)
        self.assertEqual(reorder_m["total_backorders"], 100)
        self.assertEqual(reorder_m["total_landed_cost"], 17820.0)
        self.assertEqual(reorder_m["recovery_day"], 5)
        self.assertFalse(reorder_c["validation"]["valid"])
        self.assertFalse(rank_map["reorder"]["selectable"])
        self.assertIsNone(rank_map["reorder"]["score"])
        self.assertIsNone(rank_map["reorder"]["rank"])

    def test_d7_complete_benchmark_parity(self):
        """Verify D=7 complete product-level and strategy benchmark metrics with active data layer."""
        res = coordinate_recovery(shutdown_days=7)
        cand_map = {c["strategy_id"]: c for c in res["candidates"]}
        rank_map = {r["strategy_id"]: r for r in res["rankings"]}

        # 1. Agent Candidate (Selected)
        agent_c = cand_map["agent"]
        agent_m = agent_c["metrics"]
        agent_pb = agent_m["product_breakdown"]
        self.assertEqual(agent_pb["PROD-01"]["fulfilled"], 865)
        self.assertEqual(agent_pb["PROD-01"]["demand"], 945)
        self.assertEqual(agent_pb["PROD-01"]["fill_rate"], 91.53)
        self.assertEqual(agent_pb["PROD-02"]["fulfilled"], 570)
        self.assertEqual(agent_pb["PROD-02"]["demand"], 735)
        self.assertEqual(agent_pb["PROD-02"]["fill_rate"], 77.55)
        self.assertEqual(agent_m["total_fulfilled"], 1435)
        self.assertEqual(agent_m["total_demand"], 1680)
        self.assertEqual(agent_m["fill_rate"], 85.42)
        self.assertEqual(agent_m["total_backorders"], 245)
        self.assertEqual(agent_m["total_landed_cost"], 16470.0)
        self.assertEqual(agent_m["recovery_day"], 10)
        self.assertTrue(agent_c["validation"]["valid"])
        self.assertEqual(rank_map["agent"]["rank"], 1)
        self.assertEqual(rank_map["agent"]["score"], 13379.57)
        self.assertEqual(res["selection"]["selected_strategy_id"], "agent")

        # 2. Optimized Candidate
        opt_c = cand_map["optimized"]
        opt_m = opt_c["metrics"]
        opt_pb = opt_m["product_breakdown"]
        self.assertEqual(opt_pb["PROD-01"]["fulfilled"], 805)
        self.assertEqual(opt_pb["PROD-01"]["demand"], 945)
        self.assertEqual(opt_pb["PROD-01"]["fill_rate"], 85.19)
        self.assertEqual(opt_pb["PROD-02"]["fulfilled"], 630)
        self.assertEqual(opt_pb["PROD-02"]["demand"], 735)
        self.assertEqual(opt_pb["PROD-02"]["fill_rate"], 85.71)
        self.assertEqual(opt_m["total_fulfilled"], 1435)
        self.assertEqual(opt_m["total_demand"], 1680)
        self.assertEqual(opt_m["fill_rate"], 85.42)
        self.assertEqual(opt_m["total_backorders"], 245)
        self.assertEqual(opt_m["total_landed_cost"], 16470.0)
        self.assertEqual(opt_m["recovery_day"], 10)
        self.assertTrue(opt_c["validation"]["valid"])
        self.assertEqual(rank_map["optimized"]["rank"], 2)
        self.assertEqual(rank_map["optimized"]["score"], 12744.65)

        # 3. Reorder Candidate (Infeasible)
        reorder_c = cand_map["reorder"]
        reorder_m = reorder_c["metrics"]
        reorder_pb = reorder_m["product_breakdown"]
        self.assertEqual(reorder_pb["PROD-01"]["fulfilled"], 640)
        self.assertEqual(reorder_pb["PROD-01"]["demand"], 945)
        self.assertEqual(reorder_pb["PROD-02"]["fulfilled"], 460)
        self.assertEqual(reorder_pb["PROD-02"]["demand"], 735)
        self.assertEqual(reorder_m["total_fulfilled"], 1100)
        self.assertEqual(reorder_m["total_demand"], 1680)
        self.assertEqual(reorder_m["total_backorders"], 580)
        self.assertEqual(reorder_m["total_landed_cost"], 12060.0)
        self.assertEqual(reorder_m["recovery_day"], 11)
        self.assertFalse(reorder_c["validation"]["valid"])
        self.assertFalse(rank_map["reorder"]["selectable"])
        self.assertIsNone(rank_map["reorder"]["score"])

    def test_d14_complete_benchmark_parity(self):
        """Verify D=14 complete product-level and strategy benchmark metrics with active data layer."""
        res = coordinate_recovery(shutdown_days=14)
        cand_map = {c["strategy_id"]: c for c in res["candidates"]}
        rank_map = {r["strategy_id"]: r for r in res["rankings"]}

        # 1. Agent Candidate (Selected)
        agent_c = cand_map["agent"]
        agent_m = agent_c["metrics"]
        agent_pb = agent_m["product_breakdown"]
        self.assertEqual(agent_pb["PROD-01"]["fulfilled"], 865)
        self.assertEqual(agent_pb["PROD-01"]["demand"], 945)
        self.assertEqual(agent_pb["PROD-01"]["fill_rate"], 91.53)
        self.assertEqual(agent_pb["PROD-02"]["fulfilled"], 430)
        self.assertEqual(agent_pb["PROD-02"]["demand"], 735)
        self.assertEqual(agent_pb["PROD-02"]["fill_rate"], 58.50)
        self.assertEqual(agent_m["total_fulfilled"], 1295)
        self.assertEqual(agent_m["total_demand"], 1680)
        self.assertEqual(agent_m["fill_rate"], 77.08)
        self.assertEqual(agent_m["total_backorders"], 385)
        self.assertEqual(agent_m["total_landed_cost"], 16680.0)
        self.assertEqual(agent_m["recovery_day"], 17)
        self.assertTrue(agent_c["validation"]["valid"])
        self.assertEqual(rank_map["agent"]["rank"], 1)
        self.assertEqual(rank_map["agent"]["score"], 12890.81)
        self.assertEqual(res["selection"]["selected_strategy_id"], "agent")

        # 2. Optimized Candidate
        opt_c = cand_map["optimized"]
        opt_m = opt_c["metrics"]
        opt_pb = opt_m["product_breakdown"]
        self.assertEqual(opt_pb["PROD-01"]["fulfilled"], 685)
        self.assertEqual(opt_pb["PROD-01"]["demand"], 945)
        self.assertEqual(opt_pb["PROD-01"]["fill_rate"], 72.49)
        self.assertEqual(opt_pb["PROD-02"]["fulfilled"], 610)
        self.assertEqual(opt_pb["PROD-02"]["demand"], 735)
        self.assertEqual(opt_pb["PROD-02"]["fill_rate"], 82.99)
        self.assertEqual(opt_m["total_fulfilled"], 1295)
        self.assertEqual(opt_m["total_demand"], 1680)
        self.assertEqual(opt_m["fill_rate"], 77.08)
        self.assertEqual(opt_m["total_backorders"], 385)
        self.assertEqual(opt_m["total_landed_cost"], 16680.0)
        self.assertEqual(opt_m["recovery_day"], 17)
        self.assertTrue(opt_c["validation"]["valid"])
        self.assertEqual(rank_map["optimized"]["rank"], 2)
        self.assertEqual(rank_map["optimized"]["score"], 10986.04)

        # 3. Reorder Candidate (Infeasible)
        reorder_c = cand_map["reorder"]
        reorder_m = reorder_c["metrics"]
        reorder_pb = reorder_m["product_breakdown"]
        self.assertEqual(reorder_pb["PROD-01"]["fulfilled"], 325)
        self.assertEqual(reorder_pb["PROD-01"]["demand"], 945)
        self.assertEqual(reorder_pb["PROD-02"]["fulfilled"], 215)
        self.assertEqual(reorder_pb["PROD-02"]["demand"], 735)
        self.assertEqual(reorder_m["total_fulfilled"], 540)
        self.assertEqual(reorder_m["total_demand"], 1680)
        self.assertEqual(reorder_m["total_backorders"], 1140)
        self.assertEqual(reorder_m["total_landed_cost"], 5340.0)
        self.assertEqual(reorder_m["recovery_day"], 18)
        self.assertFalse(reorder_c["validation"]["valid"])
        self.assertFalse(rank_map["reorder"]["selectable"])
        self.assertIsNone(rank_map["reorder"]["score"])

    def test_independent_score_formula_reconciliation(self):
        """
        Independently recompute scores from raw integer counts and unrounded ratios:
          P1_pct = P1_fulfilled / P1_demand * 100
          Agg_pct = Total_fulfilled / Total_demand * 100
          Bonus = max(0, 22 - Recovery_day) * 10
          Penalty = Landed_cost * 0.01
          Score = round(P1_pct * 100 + Agg_pct * 50 + Bonus - Penalty, 2)
        """
        for d in [1, 7, 14]:
            res = coordinate_recovery(shutdown_days=d)
            cand_map = {c["strategy_id"]: c for c in res["candidates"]}
            for r in res["rankings"]:
                if r["selectable"]:
                    strat = r["strategy_id"]
                    c = cand_map[strat]
                    m = c["metrics"]
                    p1_data = m["product_breakdown"]["PROD-01"]

                    p1_pct = (p1_data["fulfilled"] / p1_data["demand"] * 100.0)
                    agg_pct = (m["total_fulfilled"] / m["total_demand"] * 100.0)
                    rec = m["recovery_day"]
                    rec_bonus = max(0, 22 - rec) * 10.0 if rec is not None else 0.0
                    cost_penalty = m["total_landed_cost"] * 0.01

                    expected = round((p1_pct * 100.0) + (agg_pct * 50.0) + rec_bonus - cost_penalty, 2)
                    self.assertEqual(
                        r["score"],
                        expected,
                        f"D={d} {strat} published score {r['score']} != recomputed {expected}"
                    )

    def test_product_allocation_sensitivity_detects_skew(self):
        """
        Regression test: Proves that a product-allocation skew (e.g. erroneously claiming
        P1=945, P2=490 instead of actual P1=865, P2=570 for D=7) drastically alters the
        resulting P1 fill rate and ranking score even when aggregate fulfillment (1435) is identical.
        """
        # True D=7 Agent metrics:
        actual_p1 = 865
        actual_total = 1435
        actual_p1_pct = (actual_p1 / 945 * 100.0)
        actual_agg_pct = (actual_total / 1680 * 100.0)
        bonus = (22 - 10) * 10.0
        penalty = 16470.0 * 0.01
        actual_score = round(actual_p1_pct * 100.0 + actual_agg_pct * 50.0 + bonus - penalty, 2)
        self.assertEqual(actual_score, 13379.57)

        # Skewed allocation (where P1 is artificially 945 and P2 is 490):
        skewed_p1 = 945
        skewed_p1_pct = (skewed_p1 / 945 * 100.0)  # 100%
        skewed_score = round(skewed_p1_pct * 100.0 + actual_agg_pct * 50.0 + bonus - penalty, 2)
        self.assertEqual(skewed_score, 14226.13)
        self.assertNotEqual(actual_score, skewed_score)
        self.assertAlmostEqual(skewed_score - actual_score, 846.56, places=1)


if __name__ == "__main__":
    unittest.main()
