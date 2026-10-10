"""
SupplyShield AI — Versioned Canonical Data Layer & Validation Repository

Provides:
1. Typed Pydantic models for supply chain master data, topology, inventory, demand, and provenance.
2. Robust relationship and business-rule validation pipeline.
3. Deterministic canonical dataset fingerprinting (SHA-256).
4. In-memory snapshot caching ('load once, use one snapshot').
5. Conversion methods for seamless, 100% backward-compatible engine integration.
6. Future data source adapter interfaces (ERP, CSV) declared safely as NOT_CONFIGURED.
7. Offline CLI validation tool (python -m data_repository validate <path>).
"""

import hashlib
import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger("supplyshield.data_repository")

# Base directory for versioned datasets
DEFAULT_DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
ACTIVE_DATASET_ID = "demo_v1"


# ==============================================================================
# 1. TYPED CANONICAL DATA MODELS
# ==============================================================================

class BaseDataModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class SupplierRecord(BaseDataModel):
    """Supplier master data specification."""
    id: str = Field(description="Unique supplier node identifier")
    name: str = Field(description="Supplier display name")
    lead_time: int = Field(ge=1, description="Transit lead time in days")
    capacity: int = Field(ge=1, description="Maximum shared daily dispatch capacity")
    unit_cost: float = Field(ge=0.0, description="Base procurement unit cost in INR")
    freight_cost: float = Field(ge=0.0, description="Freight shipping unit cost in INR")
    landed_cost: float = Field(ge=0.0, description="Total landed unit cost in INR")
    currency: str = Field(default="INR", description="Operational currency code")
    is_primary: bool = Field(default=False, description="Whether this is the primary supplier")
    disruption_subject: bool = Field(default=False, description="Subject to simulated outage blackout")
    operational_notes: Optional[str] = Field(default=None, description="Operational notes")


class ProductRecord(BaseDataModel):
    """Product component SKU catalog record."""
    id: str = Field(description="Unique product SKU identifier")
    name: str = Field(description="Product descriptive name")
    unit_of_measure: str = Field(default="units", description="Unit of measure")
    daily_demand: int = Field(ge=0, description="Deterministic daily consumption rate")
    initial_inventory: int = Field(ge=0, description="Opening stock balance on Day 1")
    priority: int = Field(ge=1, le=5, description="Business criticality tier (1 = Critical)")
    criticality: Optional[str] = Field(default=None, description="Criticality classification label")
    description: Optional[str] = Field(default=None, description="Product description")


class FactoryRecord(BaseDataModel):
    """Manufacturing facility topology node specification."""
    id: str = Field(description="Unique factory identifier")
    name: str = Field(description="Factory plant name")
    capacity: int = Field(ge=0, description="Assembly capacity (structural metadata; unconstrained in simulation)")


class DistributionCenterRecord(BaseDataModel):
    """Distribution center fulfillment node specification."""
    id: str = Field(description="Unique DC identifier")
    name: str = Field(description="Facility name")


class NetworkEdgeRecord(BaseDataModel):
    """Multi-echelon network directed route."""
    source: str = Field(description="Origin node identifier")
    target: str = Field(description="Destination node identifier")
    type: str = Field(description="Route classification")
    lead_time_days: int = Field(ge=0, description="Route transit lead time in days")


class InventoryRecord(BaseDataModel):
    """Opening inventory record."""
    product_id: str = Field(description="Product SKU identifier")
    initial_inventory: int = Field(ge=0, description="Opening on-hand stock quantity")
    unit_of_measure: str = Field(default="units", description="Unit of measure")
    days_of_cover_initial: Optional[float] = Field(default=None, description="Initial days of coverage")
    storage_facility_id: Optional[str] = Field(default=None, description="Facility location")


class DemandProfileRecord(BaseDataModel):
    """Deterministic daily demand profile record."""
    product_id: str = Field(description="Product SKU identifier")
    daily_demand: int = Field(ge=0, description="Daily customer demand volume")
    horizon_demand: int = Field(ge=0, description="Total demand across the 21-day horizon")
    priority: int = Field(ge=1, le=5, description="Priority rank")
    criticality: Optional[str] = Field(default=None, description="Criticality tier label")


class CostConfigRecord(BaseDataModel):
    """Cost accounting configuration."""
    currency: str = Field(default="INR", description="Currency identifier")
    procurement_unit_costs: Dict[str, float] = Field(description="Procurement cost per unit by supplier")
    freight_unit_costs: Dict[str, float] = Field(description="Freight cost per unit by supplier")
    landed_unit_costs: Dict[str, float] = Field(description="Total landed cost per unit by supplier")
    reconciliation_formula: str = Field(default="landed_unit_cost = procurement_unit_cost + freight_unit_cost")


class ScenarioConfigRecord(BaseDataModel):
    """Supported scenario configuration bounds."""
    planning_horizon_days: int = Field(default=21, ge=1)
    default_seed: int = Field(default=42)
    target_fill_rate_percentage: float = Field(default=95.0, ge=0.0, le=100.0)
    recovery_criteria: str = Field(default="3 consecutive days at or above 95.0% fill rate after disruption dip")
    supported_shutdown_days_range: List[int] = Field(default=[1, 14])
    supported_strategies: List[str] = Field(default=["reorder", "optimized", "agent"])
    scenario_id_template: str = Field(default="SCEN-SD{shutdown_days}-H{horizon_days}-S{seed}")
    disrupted_primary_supplier: str = Field(default="SUP-01")
    contingency_supplier: str = Field(default="SUP-02")


class DatasetManifest(BaseDataModel):
    """Canonical dataset manifest describing version, source files, and provenance."""
    dataset_id: str = Field(description="Unique dataset identifier")
    dataset_version: str = Field(description="Semantic version string")
    schema_version: str = Field(default="1.0.0", description="Data contract schema version")
    source_type: str = Field(default="synthetic_demo", description="Source classification")
    is_synthetic: bool = Field(default=True, description="Whether dataset is synthetic")
    created_at_iso: str = Field(description="ISO-8601 creation timestamp")
    description: str = Field(description="High-level dataset summary")
    files: Dict[str, str] = Field(description="Mapping of logical dataset entities to JSON files")
    limitations: List[str] = Field(default_factory=list, description="Declared operational and model boundaries")


class DataQualityCheck(BaseDataModel):
    """Individual data quality rule validation result."""
    check_id: str = Field(description="Machine-readable rule identifier")
    label: str = Field(description="Human-readable rule label")
    status: str = Field(description="PASS, FAIL, or NOT_MODELED")
    severity: str = Field(description="INFO, WARNING, or CRITICAL")
    details: str = Field(description="Diagnostic message")
    entity_reference: Optional[str] = Field(default=None, description="Affected entity ID")


class DataQualityReport(BaseDataModel):
    """Comprehensive data quality and validation outcome."""
    dataset_id: str = Field(description="Dataset identifier")
    dataset_version: str = Field(description="Dataset version")
    dataset_fingerprint: str = Field(description="Cryptographic SHA-256 content fingerprint")
    status: str = Field(description="VALID or INVALID")
    supplier_count: int = Field(ge=0)
    product_count: int = Field(ge=0)
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    checks: List[DataQualityCheck] = Field(default_factory=list)
    source_classification: str = Field(default="synthetic_demo")
    model_limitations: List[str] = Field(default_factory=list)


class DataStatusResponse(BaseDataModel):
    """Public read-only dataset health and provenance response for API and diagnostics."""
    dataset_id: str
    dataset_version: str
    dataset_fingerprint: str
    source_type: str
    is_synthetic: bool
    load_status: str
    validation_status: str
    supplier_count: int
    product_count: int
    node_count: int
    error_count: int
    warning_count: int
    summary: str
    model_limitations: List[str]


# ==============================================================================
# 2. CANONICAL DATASET CONTAINER & FINGERPRINTING
# ==============================================================================

def compute_dataset_fingerprint(
    manifest: Dict[str, Any],
    suppliers: List[Dict[str, Any]],
    products: List[Dict[str, Any]],
    inventory: List[Dict[str, Any]],
    demand: Dict[str, Any],
    cost_config: Dict[str, Any],
    scenarios: Dict[str, Any],
    network: Dict[str, Any],
) -> str:
    """
    Computes a deterministic, canonical SHA-256 fingerprint for a dataset snapshot.
    Sorts dictionary keys and list elements by primary keys to guarantee that
    harmless whitespace or JSON property ordering does not alter the hash.
    """
    canonical_payload = {
        "dataset_id": manifest.get("dataset_id"),
        "dataset_version": manifest.get("dataset_version"),
        "suppliers": sorted(suppliers, key=lambda s: str(s.get("id"))),
        "products": sorted(products, key=lambda p: str(p.get("id"))),
        "inventory": sorted(inventory, key=lambda i: str(i.get("product_id"))),
        "demand_profiles": sorted(demand.get("profiles", []), key=lambda d: str(d.get("product_id"))),
        "cost_config": {
            "procurement": sorted(cost_config.get("procurement_unit_costs", {}).items()),
            "freight": sorted(cost_config.get("freight_unit_costs", {}).items()),
            "landed": sorted(cost_config.get("landed_unit_costs", {}).items()),
        },
        "scenarios": {
            "horizon": scenarios.get("planning_horizon_days"),
            "seed": scenarios.get("default_seed"),
            "strategies": sorted(scenarios.get("supported_strategies", [])),
            "shutdown_range": scenarios.get("supported_shutdown_days_range"),
        },
        "network": {
            "suppliers": sorted([s.get("id") for s in network.get("suppliers", [])]),
            "factories": sorted([f.get("id") for f in network.get("factories", [])]),
            "dcs": sorted([d.get("id") for d in network.get("distribution_centers", [])]),
        },
    }
    raw_bytes = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw_bytes).hexdigest()


class SupplyChainDataset:
    """
    Coherent, validated, immutable in-memory dataset snapshot.
    Provides typed entity access and conversion adapters for the simulation engine.
    """

    def __init__(
        self,
        manifest: DatasetManifest,
        suppliers: Dict[str, SupplierRecord],
        products: Dict[str, ProductRecord],
        factories: Dict[str, FactoryRecord],
        distribution_centers: Dict[str, DistributionCenterRecord],
        edges: List[NetworkEdgeRecord],
        inventory: Dict[str, InventoryRecord],
        demand_profiles: Dict[str, DemandProfileRecord],
        cost_config: CostConfigRecord,
        scenario_config: ScenarioConfigRecord,
        fingerprint: str,
        quality_report: DataQualityReport,
    ):
        self.manifest = manifest
        self.suppliers = suppliers
        self.products = products
        self.factories = factories
        self.distribution_centers = distribution_centers
        self.edges = edges
        self.inventory = inventory
        self.demand_profiles = demand_profiles
        self.cost_config = cost_config
        self.scenario_config = scenario_config
        self.fingerprint = fingerprint
        self.quality_report = quality_report

    @property
    def dataset_id(self) -> str:
        return self.manifest.dataset_id

    @property
    def dataset_version(self) -> str:
        return self.manifest.dataset_version

    @property
    def horizon(self) -> int:
        return self.scenario_config.planning_horizon_days

    @property
    def seed(self) -> int:
        return self.scenario_config.default_seed

    @property
    def target_fill_rate(self) -> float:
        return self.scenario_config.target_fill_rate_percentage

    def to_network_dict(self) -> Dict[str, Any]:
        """
        Produces the exact multi-echelon network topology dictionary
        expected by simulator.py and /api/network.
        """
        return {
            "suppliers": [
                {
                    "id": s.id,
                    "name": s.name,
                    "capacity": s.capacity,
                    "lead_time": s.lead_time,
                    "unit_cost": s.unit_cost,
                }
                for s in self.suppliers.values()
            ],
            "factories": [
                {
                    "id": f.id,
                    "name": f.name,
                    "capacity": f.capacity,
                }
                for f in self.factories.values()
            ],
            "distribution_centers": [
                {
                    "id": dc.id,
                    "name": dc.name,
                }
                for dc in self.distribution_centers.values()
            ],
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "daily_demand": p.daily_demand,
                    "initial_inventory": p.initial_inventory,
                    "priority": p.priority,
                }
                for p in self.products.values()
            ],
        }

    def to_transport_cost_dict(self) -> Dict[str, float]:
        """Produces freight cost dictionary for simulator.py (TRANSPORT_COST)."""
        return {s.id: s.freight_cost for s in self.suppliers.values()}

    def to_data_status(self) -> DataStatusResponse:
        """Produces public status response for /api/data/status."""
        return DataStatusResponse(
            dataset_id=self.dataset_id,
            dataset_version=self.dataset_version,
            dataset_fingerprint=self.fingerprint,
            source_type=self.manifest.source_type,
            is_synthetic=self.manifest.is_synthetic,
            load_status="LOADED",
            validation_status=self.quality_report.status,
            supplier_count=len(self.suppliers),
            product_count=len(self.products),
            node_count=len(self.suppliers) + len(self.factories) + len(self.distribution_centers),
            error_count=self.quality_report.error_count,
            warning_count=self.quality_report.warning_count,
            summary=(
                f"Active dataset '{self.dataset_id}' v{self.dataset_version} is valid and operational "
                f"({len(self.suppliers)} suppliers, {len(self.products)} products, 21-day horizon)."
            ),
            model_limitations=self.manifest.limitations,
        )


# ==============================================================================
# 3. DATASET LOADER & VALIDATION PIPELINE
# ==============================================================================

class DataQualityError(Exception):
    """Raised when canonical dataset violates mandatory schema or business validation rules."""
    def __init__(self, message: str, report: Optional[DataQualityReport] = None):
        super().__init__(message)
        self.report = report


def validate_and_load_dataset(dataset_dir: Union[str, Path]) -> Tuple[SupplyChainDataset, DataQualityReport]:
    """
    Parses and exhaustively validates all dataset files in dataset_dir.
    Checks relational consistency, non-negativity, cost reconciliation, and boundaries.
    Returns (SupplyChainDataset, DataQualityReport) if valid.
    Raises DataQualityError if validation fails.
    """
    path = Path(dataset_dir).resolve()
    if not path.is_dir():
        raise DataQualityError(f"Dataset directory not found: {path}")

    manifest_file = path / "dataset_manifest.json"
    if not manifest_file.exists():
        raise DataQualityError(f"Missing dataset_manifest.json in {path}")

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            raw_manifest = json.load(f)
        manifest = DatasetManifest.model_validate(raw_manifest)
    except Exception as e:
        raise DataQualityError(f"Failed to parse dataset_manifest.json: {e}")

    checks: List[DataQualityCheck] = []
    errors: List[str] = []
    warnings: List[str] = []

    # Helper to load JSON file referenced in manifest
    def load_subfile(key: str, filename: str) -> Any:
        sub_path = path / filename
        if not sub_path.exists():
            errors.append(f"Missing required dataset file: {filename}")
            return None
        try:
            with open(sub_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            errors.append(f"Failed to parse JSON file {filename}: {e}")
            return None

    raw_suppliers = load_subfile("suppliers", manifest.files.get("suppliers", "suppliers.json"))
    raw_products = load_subfile("products", manifest.files.get("products", "products.json"))
    raw_network = load_subfile("network", manifest.files.get("network", "network.json"))
    raw_inventory = load_subfile("inventory", manifest.files.get("inventory", "inventory.json"))
    raw_demand = load_subfile("demand_profiles", manifest.files.get("demand_profiles", "demand_profiles.json"))
    raw_scenarios = load_subfile("scenarios", manifest.files.get("scenarios", "scenarios.json"))
    raw_cost = load_subfile("cost_config", manifest.files.get("cost_config", "cost_config.json"))

    if errors:
        report = DataQualityReport(
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.dataset_version,
            dataset_fingerprint="unknown",
            status="INVALID",
            supplier_count=0,
            product_count=0,
            node_count=0,
            edge_count=0,
            error_count=len(errors),
            warning_count=0,
            checks=[DataQualityCheck(
                check_id="CHK-FILE-PRESENCE",
                label="Dataset Files Presence",
                status="FAIL",
                severity="CRITICAL",
                details="; ".join(errors),
            )],
            source_classification=manifest.source_type,
            model_limitations=manifest.limitations,
        )
        raise DataQualityError(f"Dataset files missing or corrupt: {'; '.join(errors)}", report)

    # 1. Parse and validate suppliers
    suppliers: Dict[str, SupplierRecord] = {}
    for s_raw in (raw_suppliers or []):
        try:
            s_rec = SupplierRecord.model_validate(s_raw)
            if s_rec.id in suppliers:
                errors.append(f"Duplicate supplier ID '{s_rec.id}' detected.")
            suppliers[s_rec.id] = s_rec
        except ValidationError as ve:
            errors.append(f"Supplier validation error on {s_raw.get('id', 'unknown')}: {ve}")

    checks.append(DataQualityCheck(
        check_id="CHK-SUPPLIER-MASTER",
        label="Supplier Master Data Integrity",
        status="PASS" if len(suppliers) > 0 and not any("supplier" in e.lower() for e in errors) else "FAIL",
        severity="CRITICAL" if any("supplier" in e.lower() for e in errors) else "INFO",
        details=f"Loaded {len(suppliers)} supplier record(s).",
    ))

    # 2. Parse and validate products
    products: Dict[str, ProductRecord] = {}
    for p_raw in (raw_products or []):
        try:
            p_rec = ProductRecord.model_validate(p_raw)
            if p_rec.id in products:
                errors.append(f"Duplicate product ID '{p_rec.id}' detected.")
            products[p_rec.id] = p_rec
        except ValidationError as ve:
            errors.append(f"Product validation error on {p_raw.get('id', 'unknown')}: {ve}")

    checks.append(DataQualityCheck(
        check_id="CHK-PRODUCT-CATALOG",
        label="Product Catalog Integrity",
        status="PASS" if len(products) > 0 and not any("product" in e.lower() for e in errors) else "FAIL",
        severity="CRITICAL" if any("product" in e.lower() for e in errors) else "INFO",
        details=f"Loaded {len(products)} product SKU(s).",
    ))

    # 3. Parse network topology
    factories: Dict[str, FactoryRecord] = {}
    dcs: Dict[str, DistributionCenterRecord] = {}
    edges: List[NetworkEdgeRecord] = []

    for f_raw in (raw_network.get("factories", []) if raw_network else []):
        f_rec = FactoryRecord.model_validate(f_raw)
        factories[f_rec.id] = f_rec

    for dc_raw in (raw_network.get("distribution_centers", []) if raw_network else []):
        dc_rec = DistributionCenterRecord.model_validate(dc_raw)
        dcs[dc_rec.id] = dc_rec

    for e_raw in (raw_network.get("edges", []) if raw_network else []):
        e_rec = NetworkEdgeRecord.model_validate(e_raw)
        edges.append(e_rec)

    # Validate edge relationships
    all_node_ids = set(suppliers.keys()) | set(factories.keys()) | set(dcs.keys())
    for edge in edges:
        if edge.source not in all_node_ids:
            errors.append(f"Network edge references unknown source node: '{edge.source}'")
        if edge.target not in all_node_ids:
            errors.append(f"Network edge references unknown target node: '{edge.target}'")

    checks.append(DataQualityCheck(
        check_id="CHK-NETWORK-TOPOLOGY",
        label="Network Node and Edge Integrity",
        status="PASS" if not any("edge" in e.lower() for e in errors) else "FAIL",
        severity="CRITICAL" if any("edge" in e.lower() for e in errors) else "INFO",
        details=f"Verified {len(all_node_ids)} nodes and {len(edges)} directed edges.",
    ))

    # 4. Parse inventory and demand, verifying product references
    inventory: Dict[str, InventoryRecord] = {}
    for inv_raw in (raw_inventory or []):
        try:
            inv_rec = InventoryRecord.model_validate(inv_raw)
            if inv_rec.product_id not in products:
                errors.append(f"Inventory record references unknown product SKU: '{inv_rec.product_id}'")
            inventory[inv_rec.product_id] = inv_rec
        except ValidationError as ve:
            errors.append(f"Inventory schema validation error on {inv_raw.get('product_id', 'unknown')}: {ve}")

    demand_profiles: Dict[str, DemandProfileRecord] = {}
    for d_raw in (raw_demand.get("profiles", []) if raw_demand else []):
        try:
            d_rec = DemandProfileRecord.model_validate(d_raw)
            if d_rec.product_id not in products:
                errors.append(f"Demand profile references unknown product SKU: '{d_rec.product_id}'")
            demand_profiles[d_rec.product_id] = d_rec
        except ValidationError as ve:
            errors.append(f"Demand profile schema validation error on {d_raw.get('product_id', 'unknown')}: {ve}")

    # Every product in products catalog must have inventory and demand
    for pid in products:
        if pid not in inventory:
            errors.append(f"Product '{pid}' lacks an initial inventory record.")
        if pid not in demand_profiles:
            errors.append(f"Product '{pid}' lacks a demand profile.")

    checks.append(DataQualityCheck(
        check_id="CHK-INVENTORY-DEMAND-PARITY",
        label="Inventory and Demand Catalog Parity",
        status="PASS" if not any("lacks" in e.lower() for e in errors) else "FAIL",
        severity="CRITICAL" if any("lacks" in e.lower() for e in errors) else "INFO",
        details=f"Verified opening stock and demand profiles for all {len(products)} products.",
    ))

    # 5. Cost reconciliation check: procurement + freight == landed
    cost_config = CostConfigRecord.model_validate(raw_cost)
    for sid, sup in suppliers.items():
        proc = cost_config.procurement_unit_costs.get(sid, sup.unit_cost)
        freight = cost_config.freight_unit_costs.get(sid, sup.freight_cost)
        expected_landed = round(proc + freight, 2)
        declared_landed = round(cost_config.landed_unit_costs.get(sid, sup.landed_cost), 2)
        if expected_landed != declared_landed:
            errors.append(
                f"Cost mismatch for supplier '{sid}': procurement ({proc}) + freight ({freight}) = "
                f"{expected_landed}, but declared landed cost is {declared_landed}."
            )

    checks.append(DataQualityCheck(
        check_id="CHK-COST-ACCOUNTING-RECONCILIATION",
        label="Procurement and Freight Cost Reconciliation",
        status="PASS" if not any("cost mismatch" in e.lower() for e in errors) else "FAIL",
        severity="CRITICAL" if any("cost mismatch" in e.lower() for e in errors) else "INFO",
        details=f"Verified unit landed cost reconciliation across all {len(suppliers)} suppliers.",
    ))

    # 6. Scenario configuration
    scenario_config = ScenarioConfigRecord.model_validate(raw_scenarios)
    if scenario_config.planning_horizon_days != 21:
        warnings.append(f"Horizon is set to {scenario_config.planning_horizon_days} (standard demo is 21).")

    checks.append(DataQualityCheck(
        check_id="CHK-SCENARIO-PARAMETERS",
        label="Scenario Planning Parameters",
        status="PASS",
        severity="INFO",
        details=f"Planning horizon: {scenario_config.planning_horizon_days}d, Seed: {scenario_config.default_seed}.",
    ))

    # 7. Unmodeled boundaries documentation
    checks.append(DataQualityCheck(
        check_id="CHK-DOWNSTREAM-BOUNDARIES",
        label="Downstream Factory and DC Operational Boundaries",
        status="NOT_MODELED",
        severity="INFO",
        details="Factory throughput and DC storage capacities are topological metadata (unconstrained in current model).",
    ))

    fingerprint = compute_dataset_fingerprint(
        manifest=raw_manifest,
        suppliers=raw_suppliers,
        products=raw_products,
        inventory=raw_inventory,
        demand=raw_demand,
        cost_config=raw_cost,
        scenarios=raw_scenarios,
        network=raw_network,
    )

    is_valid = len(errors) == 0
    report = DataQualityReport(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.dataset_version,
        dataset_fingerprint=fingerprint,
        status="VALID" if is_valid else "INVALID",
        supplier_count=len(suppliers),
        product_count=len(products),
        node_count=len(all_node_ids),
        edge_count=len(edges),
        error_count=len(errors),
        warning_count=len(warnings),
        checks=checks,
        source_classification=manifest.source_type,
        model_limitations=manifest.limitations,
    )

    if not is_valid:
        raise DataQualityError(f"Dataset '{manifest.dataset_id}' failed validation: {'; '.join(errors)}", report)

    dataset = SupplyChainDataset(
        manifest=manifest,
        suppliers=suppliers,
        products=products,
        factories=factories,
        distribution_centers=dcs,
        edges=edges,
        inventory=inventory,
        demand_profiles=demand_profiles,
        cost_config=cost_config,
        scenario_config=scenario_config,
        fingerprint=fingerprint,
        quality_report=report,
    )

    return dataset, report


# ==============================================================================
# 4. SINGLETON REPOSITORY & IN-MEMORY CACHE
# ==============================================================================

_ACTIVE_DATASET: Optional[SupplyChainDataset] = None


def get_active_dataset(dataset_dir: Optional[Union[str, Path]] = None) -> SupplyChainDataset:
    """
    Returns the active in-memory dataset snapshot.
    Loads once at startup; returns cached immutable snapshot thereafter.
    """
    global _ACTIVE_DATASET
    if _ACTIVE_DATASET is None:
        target_dir = Path(dataset_dir) if dataset_dir else (DEFAULT_DATASETS_DIR / ACTIVE_DATASET_ID)
        dataset, _ = validate_and_load_dataset(target_dir)
        _ACTIVE_DATASET = dataset
        logger.info(
            f"Activated canonical supply chain dataset: {dataset.dataset_id} v{dataset.dataset_version} "
            f"(fingerprint: {dataset.fingerprint[:12]}...)"
        )
    return _ACTIVE_DATASET


def set_active_dataset(dataset: SupplyChainDataset) -> None:
    """Explicitly assigns the active dataset snapshot (e.g. during test setup)."""
    global _ACTIVE_DATASET
    _ACTIVE_DATASET = dataset


def reset_active_dataset() -> None:
    """Resets the cached dataset snapshot to force reloading."""
    global _ACTIVE_DATASET
    _ACTIVE_DATASET = None


# ==============================================================================
# 5. FUTURE DATA SOURCE ADAPTER INTERFACES (SAFE EXTENSIBILITY)
# ==============================================================================

class DataSourceAdapter(ABC):
    """Abstract interface for supply chain data source providers."""

    @abstractmethod
    def get_adapter_name(self) -> str:
        pass

    @abstractmethod
    def check_availability(self) -> bool:
        pass

    @abstractmethod
    def load(self) -> SupplyChainDataset:
        pass


class DemoV1FileAdapter(DataSourceAdapter):
    """Active file-backed canonical demo dataset adapter."""

    def __init__(self, dataset_dir: Optional[Union[str, Path]] = None):
        self.dataset_dir = Path(dataset_dir) if dataset_dir else (DEFAULT_DATASETS_DIR / ACTIVE_DATASET_ID)

    def get_adapter_name(self) -> str:
        return "DemoV1FileAdapter"

    def check_availability(self) -> bool:
        return self.dataset_dir.is_dir()

    def load(self) -> SupplyChainDataset:
        return get_active_dataset(self.dataset_dir)


class ErpSnapshotAdapter(DataSourceAdapter):
    """Stubbed future connector for live ERP inventory and purchase order exports."""

    def get_adapter_name(self) -> str:
        return "ErpSnapshotAdapter"

    def check_availability(self) -> bool:
        return False  # NOT_CONFIGURED

    def load(self) -> SupplyChainDataset:
        raise NotImplementedError("Live ERP ingestion is NOT_CONFIGURED in current decision-support simulation boundary.")


class CsvBatchImportAdapter(DataSourceAdapter):
    """Stubbed future connector for batch CSV file ingestion."""

    def get_adapter_name(self) -> str:
        return "CsvBatchImportAdapter"

    def check_availability(self) -> bool:
        return False  # NOT_CONFIGURED

    def load(self) -> SupplyChainDataset:
        raise NotImplementedError("Batch CSV ingestion adapter is NOT_CONFIGURED in current demo phase.")


# ==============================================================================
# 6. OFFLINE CLI VALIDATION UTILITY
# ==============================================================================

def validate_dataset_cli(target_path_str: str) -> int:
    """
    Offline validation CLI tool.
    Validates a dataset directory, prints human-readable findings, and returns exit code 0 or 1.
    """
    print(f"=== SUPPLYSHIELD AI DATASET VALIDATION PIPELINE ===")
    print(f"Target: {target_path_str}\n")
    try:
        dataset, report = validate_and_load_dataset(target_path_str)
        print(f"STATUS: \033[92m{report.status}\033[0m")
        print(f"Dataset ID:          {report.dataset_id} (v{report.dataset_version})")
        print(f"Source Type:         {report.source_classification}")
        print(f"Dataset Fingerprint: {report.dataset_fingerprint}")
        print(f"Suppliers Validated: {report.supplier_count}")
        print(f"Products Validated:  {report.product_count}")
        print(f"Network Nodes:       {report.node_count}")
        print(f"Directed Edges:      {report.edge_count}")
        print(f"Errors:              {report.error_count}")
        print(f"Warnings:            {report.warning_count}\n")
        print("Detailed Validation Checks:")
        for chk in report.checks:
            badge = "PASS" if chk.status == "PASS" else ("NOT_MODELED" if chk.status == "NOT_MODELED" else "FAIL")
            print(f"  [{badge}] {chk.check_id} — {chk.label}: {chk.details}")
        print("\nDeclared Model Boundaries:")
        for lim in report.model_limitations:
            print(f"  - {lim}")
        print("\nResult: VALIDATION PASSED")
        return 0
    except DataQualityError as dqe:
        print(f"STATUS: \033[91mINVALID\033[0m")
        print(f"Error: {dqe}\n")
        if dqe.report:
            for chk in dqe.report.checks:
                if chk.status == "FAIL":
                    print(f"  [FAIL] {chk.check_id}: {chk.details}")
        print("\nResult: VALIDATION FAILED")
        return 1
    except Exception as e:
        print(f"STATUS: \033[91mCRASH\033[0m")
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1].lower() == "validate":
        target = sys.argv[2]
        sys.exit(validate_dataset_cli(target))
    elif len(sys.argv) == 2 and sys.argv[1].lower() != "validate":
        sys.exit(validate_dataset_cli(sys.argv[1]))
    else:
        # Default: validate canonical demo_v1 dataset
        default_path = str(DEFAULT_DATASETS_DIR / ACTIVE_DATASET_ID)
        sys.exit(validate_dataset_cli(default_path))
