"""
SupplyShield AI — Shared Contract Schemas (Phase B0)

Defines strongly-typed Pydantic models for scenario configurations, network nodes,
operational metrics, order schedules, agent assessments, constraint validation,
and API responses.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class BaseContractModel(BaseModel):
    """Base model enabling extra fields preservation for non-breaking API evolution."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ==============================================================================
# 1. SCENARIO CONFIGURATION
# ==============================================================================

class ScenarioConfig(BaseContractModel):
    """Operational scenario parameters governing the simulation horizon and disruption."""
    shutdown_days: int = Field(
        default=7,
        ge=1,
        le=14,
        description="Duration in days of the primary supplier facility outage (1 to 14 days)."
    )
    horizon_days: int = Field(
        default=21,
        ge=7,
        le=60,
        description="Total deterministic simulation planning horizon in days (default: 21)."
    )
    recovery_mode: Optional[str] = Field(
        default="agent",
        pattern="^(reorder|optimized|agent)$",
        description="Planning policy mode: 'reorder', 'optimized', or 'agent'."
    )
    priority_weighted: Optional[bool] = Field(
        default=None,
        description="Whether Priority 1 components carry double shortage penalty in optimization."
    )
    disrupted_supplier_id: Optional[str] = Field(
        default="SUP-01",
        description="Identifier of the primary disrupted supplier node."
    )
    seed: Optional[int] = Field(
        default=42,
        description="Simulation seed for reproducible evaluation."
    )
    scenario_id: Optional[str] = Field(
        default=None,
        description="Deterministic scenario signature (e.g. SCEN-SD7-H21-S42)."
    )
    dataset_id: Optional[str] = Field(
        default=None,
        description="Dataset identifier (e.g. demo_v1)."
    )
    dataset_version: Optional[str] = Field(
        default=None,
        description="Dataset version identifier (e.g. 1.0.0)."
    )
    dataset_fingerprint: Optional[str] = Field(
        default=None,
        description="Deterministic content fingerprint of the canonical dataset snapshot."
    )


# ==============================================================================
# 2. NETWORK TOPOLOGY ENTITIES
# ==============================================================================

class SupplierNode(BaseContractModel):
    """Supplier node specification with daily capacity, lead time, and unit pricing."""
    id: str = Field(description="Unique supplier identifier (e.g. SUP-01, SUP-02)")
    name: str = Field(description="Descriptive supplier name")
    capacity: int = Field(ge=0, description="Maximum shared daily dispatch capacity across all products")
    lead_time: int = Field(ge=1, description="Transit lead time in days from supplier to assembly facilities")
    unit_cost: float = Field(ge=0.0, description="Base procurement unit cost in INR")


class FactoryNode(BaseContractModel):
    """Manufacturing assembly node specification."""
    id: str = Field(description="Unique factory identifier (e.g. FAC-01, FAC-02)")
    name: str = Field(description="Descriptive factory plant name")
    capacity: int = Field(ge=0, description="Maximum daily assembly throughput capacity (structural topology metadata; downstream multi-echelon transfer is unconstrained in current model)")


class DistributionCenterNode(BaseContractModel):
    """Distribution center fulfillment node specification (structural topology metadata; storage capacity unconstrained in current model)."""
    id: str = Field(description="Unique distribution center identifier (e.g. DC-01, DC-02)")
    name: str = Field(description="Descriptive facility name")


class ProductNode(BaseContractModel):
    """Product SKU specification with daily demand, initial inventory, and priority tier."""
    id: str = Field(description="Unique product identifier (e.g. PROD-01, PROD-02)")
    name: str = Field(description="Descriptive product component name")
    daily_demand: int = Field(ge=0, description="Deterministic daily customer demand volume")
    initial_inventory: int = Field(ge=0, description="Opening on-hand stock on Day 1")
    priority: int = Field(ge=1, le=5, description="Business criticality tier (1 = Critical / Mission-critical)")


class NetworkTopology(BaseContractModel):
    """Multi-echelon supply network structure."""
    suppliers: List[SupplierNode]
    factories: List[FactoryNode]
    distribution_centers: List[DistributionCenterNode]
    products: List[ProductNode]


# ==============================================================================
# 3. OPERATIONAL METRICS & BREAKDOWNS
# ==============================================================================

class ProductMetricBreakdown(BaseContractModel):
    """Product-level cumulative demand fulfillment metrics."""
    demand: int = Field(ge=0, description="Cumulative demand volume over horizon")
    fulfilled: int = Field(ge=0, description="Cumulative units fulfilled")
    unmet: int = Field(ge=0, description="Cumulative unfulfilled backorders")
    fill_rate: float = Field(ge=0.0, le=100.0, description="Percentage service fill rate (0.0% to 100.0%)")


class SimulationMetrics(BaseContractModel):
    """Comprehensive performance metrics produced by the deterministic simulator."""
    total_demand: int = Field(ge=0, description="Total aggregate customer demand across all products")
    total_fulfilled: int = Field(ge=0, description="Total demand units successfully fulfilled from stock")
    total_backorders: int = Field(ge=0, description="Total period-specific unmet customer demand across all horizon days (not carried forward)")
    fill_rate: float = Field(ge=0.0, le=100.0, description="Aggregate service fill rate percentage (0.0 to 100.0)")
    total_landed_cost: float = Field(ge=0.0, description="Total landed procurement and freight expenditure in INR")
    recovery_day: Optional[int] = Field(
        default=None,
        description="Day index where sustained >=95% service is restored for 3 consecutive days, or None"
    )
    ending_inventory: Dict[str, int] = Field(description="Remaining on-hand inventory by product at Day 21")
    outstanding_orders_at_horizon: int = Field(ge=0, description="Count of orders remaining in transit past Day 21")
    constraint_violations: int = Field(default=0, ge=0, description="Count of model constraint violations detected")
    product_breakdown: Optional[Dict[str, ProductMetricBreakdown]] = Field(
        default=None,
        description="Product-level demand fulfillment breakdown"
    )
    runtime_seconds: Optional[float] = Field(
        default=None,
        description="Planning execution wall-clock time in seconds"
    )


class OptimizationMetrics(BaseContractModel):
    """Solver metrics produced directly by Google OR-Tools CP-SAT."""
    total_demand: int = Field(ge=0, description="Total aggregate customer demand")
    total_fulfilled: int = Field(ge=0, description="Total demand fulfilled")
    total_backorders: int = Field(ge=0, description="Total period-specific unmet customer demand across all horizon days (not carried forward)")
    fill_rate: float = Field(ge=0.0, le=100.0, description="Service fill rate percentage")
    total_purchase_and_transport_cost: float = Field(ge=0.0, description="Total purchase and freight cost in INR")
    total_landed_cost: float = Field(ge=0.0, description="Landed cost (equivalent to purchase + freight)")
    recovery_day: Optional[int] = Field(default=None, description="Day index of sustained >=95% recovery")
    ending_inventory: Optional[Dict[str, int]] = Field(default=None, description="Remaining on-hand inventory by product at Day 21")
    outstanding_orders_at_horizon: Optional[int] = Field(default=None, ge=0, description="Count of orders remaining in transit past Day 21")
    product_breakdown: Optional[Dict[str, ProductMetricBreakdown]] = Field(default=None, description="Product-level demand fulfillment breakdown")
    objective_value_scaled: Optional[float] = Field(default=None, description="Internal integer objective value")
    solver_time_seconds: Optional[float] = Field(default=None, description="CP-SAT solver solve time in seconds")


# ==============================================================================
# 4. ORDER & DAILY SCHEDULE SCHEMAS
# ==============================================================================

class OrderRecord(BaseContractModel):
    """Replenishment order placed with a supplier."""
    order_day: int = Field(ge=1, description="Day on which the purchase order is issued")
    arrival_day: int = Field(ge=1, description="Day on which delivery arrives at assembly plants")
    product: str = Field(description="Product SKU identifier")
    supplier: str = Field(description="Supplier node identifier")
    quantity: int = Field(ge=0, description="Order quantity in units")
    cost: float = Field(ge=0.0, description="Total landed cost (procurement + freight) in INR")
    status: Optional[str] = Field(default="ordered", description="Order execution status")
    strategy: Optional[str] = Field(default=None, description="Policy generating the order")


class OrderArrival(BaseContractModel):
    """Daily delivery arrival event from transit pipeline."""
    supplier: str = Field(description="Delivering supplier identifier")
    product: str = Field(description="Delivered product SKU")
    quantity: int = Field(ge=0, description="Delivered quantity in units")


class DailyProductFulfillment(BaseContractModel):
    """Product-level daily operational accounting."""
    demand: int = Field(ge=0, description="Daily demand for this product")
    fulfilled: int = Field(ge=0, description="Units fulfilled from stock today")
    unmet: int = Field(ge=0, description="Unmet units for this product today")


class DailyResult(BaseContractModel):
    """Daily operational telemetry snapshot across the 21-day planning horizon."""
    day: int = Field(ge=1, le=60, description="Operational day number (1 to 21)")
    demand: int = Field(ge=0, description="Total demand on this day across all products")
    fulfilled: int = Field(ge=0, description="Total units fulfilled today")
    backorders: Optional[int] = Field(default=0, ge=0, description="Period-specific unmet customer demand for this day (not carried forward)")
    unmet_demand: Optional[int] = Field(default=None, ge=0, description="Alias for period-specific backorders on this day")
    fill_rate: float = Field(ge=0.0, le=100.0, description="Daily service fill rate percentage")
    landed_cost: Optional[float] = Field(default=0.0, description="Landed cost of orders placed on this day")
    arrivals: List[OrderArrival] = Field(default_factory=list, description="Deliveries arriving today")
    orders: List[Dict[str, Any]] = Field(default_factory=list, description="Replenishment orders issued today")
    inventory: Dict[str, int] = Field(description="Closing on-hand stock by product at end of day")
    outstanding_orders: Optional[int] = Field(default=0, description="Orders remaining in transit at end of day")
    products: Dict[str, DailyProductFulfillment] = Field(description="Product-level breakdown for this day")


# ==============================================================================
# 5. AGENT TELEMETRY CONTRACTS
# ==============================================================================

class AgentFinding(BaseContractModel):
    """Structured observation produced by a specialist agent with physical units and context."""
    observation: str = Field(description="Operational finding description")
    value: Any = Field(description="Observed or calculated metric value")
    units: Optional[str] = Field(default=None, description="Physical units or scale")
    tier: Optional[str] = Field(default=None, description="Criticality tier if applicable")
    outage_window: Optional[str] = Field(default=None, description="Outage duration if applicable")
    target_type: Optional[str] = Field(default=None, description="Target classification (e.g. DEMONSTRATION_HEURISTIC)")
    target_description: Optional[str] = Field(default=None, description="Detailed target description")


class DemandHandoff(BaseContractModel):
    """Structured handoff from Demand Intelligence Agent to the planner."""
    product_id: str = Field(description="Product SKU identifier")
    priority_tier: int = Field(ge=1, le=5, description="Business criticality tier")
    is_critical: bool = Field(description="True if product is Priority 1")
    daily_demand: int = Field(ge=0, description="Daily demand burn rate")
    horizon_demand: int = Field(ge=0, description="Gross demand exposure over horizon")
    recommended_solver_weight: float = Field(ge=1.0, description="Shortage penalty multiplier for CP-SAT")
    target_service_level: float = Field(ge=0.0, le=1.0, description="Heuristic service level target")
    service_target_type: str = Field(default="DEMONSTRATION_HEURISTIC", description="Target classification: DEMONSTRATION_HEURISTIC")
    min_recommended_daily_allocation: int = Field(ge=0, description="Recommended daily units from backup capacity")


class InventoryHandoff(BaseContractModel):
    """Structured handoff from Inventory Analyst Agent to the planner."""
    product_id: str = Field(description="Product SKU identifier")
    on_hand_inventory: int = Field(ge=0, description="Current usable on-hand stock")
    days_of_cover: Optional[float] = Field(default=None, description="Inventory runway days")
    unassisted_stockout_day: Optional[int] = Field(default=None, description="Day of stock exhaustion without receipts")
    effective_depletion_day: Optional[int] = Field(default=None, description="Depletion day accounting for verified pipeline receipts")
    shortage_window: Optional[Dict[str, Any]] = Field(default=None, description="Shortage window parameters")
    replenishment_urgency: str = Field(description="Urgency tier: CRITICAL, HIGH, ROUTINE, NONE")
    latest_acceptable_arrival_day: Optional[int] = Field(default=None, description="Target replenishment deadline")


class SupplierRiskHandoff(BaseContractModel):
    """Structured handoff from Supplier Risk Agent to the planner."""
    supplier_id: str = Field(description="Supplier identifier")
    is_available_for_orders: bool = Field(description="True if supplier can accept orders on Day 1")
    earliest_eligible_order_day: int = Field(ge=1, description="First day purchase orders may be issued")
    shared_daily_capacity: int = Field(ge=0, description="Maximum daily throughput capacity")
    lead_time_days: int = Field(ge=1, description="Transit lead time")
    landed_cost_per_unit: float = Field(ge=0.0, description="Total procurement plus freight unit cost")
    capacity_is_constrained: bool = Field(description="True if supplier capacity is less than total daily demand")


class LogisticsHandoff(BaseContractModel):
    """Structured handoff from Logistics Planner Agent to the planner."""
    supplier_id: str = Field(description="Supplier identifier")
    lead_time_days: int = Field(ge=1, description="Transit lead time")
    freight_cost_per_unit: float = Field(ge=0.0, description="Unit freight cost")
    total_landed_cost_per_unit: float = Field(ge=0.0, description="Procurement plus freight landed cost")
    earliest_possible_arrival_day: int = Field(ge=1, description="Earliest day shipments can reach assembly plants")
    order_cutoff_day_for_horizon: int = Field(ge=1, description="Latest day to order and arrive within horizon")
    transit_gap_days: List[int] = Field(default_factory=list, description="Scenario-specific days with pre-replenishment shortage")


class AgentProposal(BaseContractModel):
    """Structured assessment, proposal, or risk advisory generated by a specialist agent."""
    agent: str = Field(description="Specialist agent identifier (demand, inventory, supplier_risk, logistics)")
    action: str = Field(description="Action or proposal category identifier")
    product: Optional[str] = Field(default=None, description="Target product SKU identifier")
    product_name: Optional[str] = Field(default=None, description="Descriptive product component name")
    supplier: Optional[str] = Field(default=None, description="Target supplier node identifier")
    supplier_name: Optional[str] = Field(default=None, description="Descriptive supplier name")
    daily_demand: Optional[int] = Field(default=None, description="Daily demand volume evaluated")
    priority: Optional[int] = Field(default=None, description="Criticality priority tier evaluated")
    criticality: Optional[str] = Field(default=None, description="Descriptive criticality classification")
    inventory: Optional[int] = Field(default=None, description="Stock volume analyzed")
    days_of_cover: Optional[float] = Field(default=None, description="Calculated days of inventory runway")
    stockout_day: Optional[int] = Field(default=None, description="Projected day of stock exhaustion")
    risk: Optional[str] = Field(default=None, description="Risk level (CRITICAL, HIGH, MODERATE, AVAILABLE)")
    shutdown_days: Optional[int] = Field(default=None, description="Supplier shutdown window analyzed")
    capacity: Optional[int] = Field(default=None, description="Supplier daily throughput capacity")
    lead_time_days: Optional[int] = Field(default=None, description="Transit lead time evaluated")
    transport_cost_per_unit: Optional[float] = Field(default=None, description="Freight cost per unit")
    earliest_possible_arrival_day: Optional[int] = Field(default=None, description="Earliest feasible delivery day")
    recommendation: str = Field(description="Actionable contingency guidance")
    reason: str = Field(description="Analytical evidence and justification")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Assessment confidence score (0.0 to 1.0)")
    status: Optional[str] = Field(default="SUCCESS", description="Agent analysis execution status: SUCCESS, LIMITED, BLOCKED")
    findings: Optional[List[AgentFinding]] = Field(default=None, description="Structured factual observations with units")
    evidence: Optional[Dict[str, Any]] = Field(default=None, description="Mathematical calculations and source data")
    limitations: Optional[List[str]] = Field(default=None, description="Explicit uncertainty boundaries and non-modeled factors")
    handoff: Optional[Dict[str, Any]] = Field(default=None, description="Structured payload for downstream planning consumption")


class DemandAgentProposal(AgentProposal):
    """Specialized proposal contract for Demand Intelligence Agent."""
    handoff: Optional[DemandHandoff] = None


class InventoryAgentProposal(AgentProposal):
    """Specialized proposal contract for Inventory Analyst Agent."""
    handoff: Optional[InventoryHandoff] = None


class SupplierRiskAgentProposal(AgentProposal):
    """Specialized proposal contract for Supplier Risk Agent."""
    handoff: Optional[SupplierRiskHandoff] = None


class LogisticsAgentProposal(AgentProposal):
    """Specialized proposal contract for Logistics Planner Agent."""
    handoff: Optional[LogisticsHandoff] = None


class AgentScenarioContext(BaseContractModel):
    """Scenario context supplied to specialist agents for deterministic analysis."""
    scenario_id: str = Field(description="Deterministic scenario context signature")
    shutdown_days: int = Field(default=7, ge=1, le=14, description="Outage duration in days")
    horizon_days: int = Field(default=21, ge=7, le=60, description="Planning horizon in days")
    current_day: int = Field(default=1, ge=1, description="Planning evaluation day")
    disrupted_supplier_id: str = Field(default="SUP-01", description="Disrupted supplier identifier")
    products: List[Dict[str, Any]] = Field(description="Product node parameters")
    suppliers: List[Dict[str, Any]] = Field(description="Supplier node parameters")
    transport_costs: Dict[str, float] = Field(description="Freight costs per supplier")
    inbound_orders: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Confirmed inbound orders")
    seed: int = Field(default=42, description="Simulation random seed")


class AgentReports(BaseContractModel):
    """Composite telemetry report grouping all four specialized agent modules."""
    demand: List[AgentProposal] = Field(description="Demand Intelligence Agent assessments")
    inventory: List[AgentProposal] = Field(description="Inventory Analyst Agent assessments")
    supplier_risk: List[AgentProposal] = Field(description="Supplier Risk Agent assessments")
    logistics: List[AgentProposal] = Field(description="Logistics Planner Agent assessments")


# ==============================================================================
# 6. CONSTRAINT VALIDATION & GOVERNANCE
# ==============================================================================

class ValidationViolation(BaseContractModel):
    """Detailed record of an operational constraint violation detected in an order plan."""
    type: str = Field(description="Violation category (e.g. supplier_shutdown, supplier_capacity_exceeded)")
    day: Optional[int] = Field(default=None, description="Operational day where violation occurred")
    supplier: Optional[str] = Field(default=None, description="Supplier node involved in violation")
    quantity: Optional[int] = Field(default=None, description="Rejected order quantity")
    capacity: Optional[int] = Field(default=None, description="Permitted capacity threshold")
    used: Optional[int] = Field(default=None, description="Actual capacity attempted")
    order: Optional[Dict[str, Any]] = Field(default=None, description="Infeasible order payload")
    expected_arrival_day: Optional[int] = Field(default=None, description="Permitted arrival day")


class ValidationResult(BaseContractModel):
    """Deterministic constraint validation findings returned by the verification engine."""
    valid: bool = Field(description="True if candidate plan satisfies all enforced model constraints")
    violation_count: int = Field(ge=0, description="Total count of constraint violations identified")
    violations: List[ValidationViolation] = Field(default_factory=list, description="Itemized violation records")


class RecoveryRecommendation(BaseContractModel):
    """Synthesized contingency action plan presented for human planner review."""
    title: str = Field(description="Headline strategy recommendation title")
    summary: str = Field(description="Executive narrative explaining contingency rationale")
    action_plan: str = Field(description="Concrete operational order directives")
    planner_approval_required: bool = Field(default=True, description="Human decision authority gate flag")
    approved: bool = Field(default=False, description="Session authorization status")
    generated_at: str = Field(description="ISO-8601 UTC timestamp of recommendation generation")


# ==============================================================================
# 7. TOP-LEVEL API RESPONSE SCHEMAS
# ==============================================================================

class HealthResponse(BaseContractModel):
    """Service liveness probe response."""
    status: str = Field(default="ok", description="Service operational status")


class StrategyInfo(BaseContractModel):
    """Metadata describing a strategy's algorithm and execution profile."""
    id: str = Field(description="Strategy identifier: reorder, optimized, agent")
    name: str = Field(description="Human-readable strategy name")
    description: str = Field(description="Technical summary of policy mechanics")
    planning_time_ms: float = Field(ge=0.0, description="Planning runtime in milliseconds")


class SimulationResponse(BaseContractModel):
    """Response payload for GET /api/simulate."""
    scenario: ScenarioConfig
    metrics: SimulationMetrics
    violations: List[ValidationViolation] = Field(default_factory=list)
    daily_results: List[DailyResult]
    network: NetworkTopology
    assumptions: List[str]
    strategy_info: Optional[StrategyInfo] = None


class OptimizationResponse(BaseContractModel):
    """Response payload for GET /api/optimize."""
    status: str = Field(description="Solver termination status: OPTIMAL, FEASIBLE, INFEASIBLE")
    scenario: ScenarioConfig
    metrics: Optional[OptimizationMetrics] = Field(default=None, description="Optimization metrics, or None if solver found no feasible solution")
    orders: List[OrderRecord] = Field(default_factory=list)
    daily_results: List[DailyResult] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    message: Optional[str] = Field(default=None, description="Diagnostic solver message")


# ==============================================================================
# 6B. RECOVERY COORDINATION & AUDITABLE PLAN SELECTION (Phase B4)
# ==============================================================================

class RecoveryConflict(BaseContractModel):
    """Structured record of an operational conflict identified across specialist agent findings."""
    conflict_id: str = Field(description="Unique conflict code, e.g. CAPACITY_VS_DEMAND_ALLOCATION")
    conflict_type: str = Field(description="Conflict category: capacity_constraint, lead_time_gap, outage_restriction")
    severity: str = Field(description="Severity: HIGH, MEDIUM, LOW")
    affected_entity: str = Field(description="Entity affected (product, supplier, time window)")
    agents_involved: List[str] = Field(description="Agent names involved in conflict")
    evidence: str = Field(description="Supporting empirical facts from agent findings")
    consequence: str = Field(description="Operational impact of the conflict")
    status: str = Field(description="Resolution state: RESOLVED, ACCEPTED_TRADEOFF, UNRESOLVED")
    rationale: str = Field(description="Coordinator reasoning and resolution approach")


class ValidationCheck(BaseContractModel):
    """Detailed result of a single invariant or model constraint check."""
    check_id: str = Field(description="Unique check identifier")
    label: str = Field(description="Human-readable check label")
    status: str = Field(description="Status: PASS, FAIL, NOT_MODELED")
    severity: str = Field(default="INFO", description="Severity: INFO, WARNING, CRITICAL")
    details: str = Field(description="Evaluation explanation")
    target_entity: Optional[str] = Field(default=None, description="Affected supplier, candidate, or echelon")


class ValidationReport(BaseContractModel):
    """Structured audit report across implemented model constraints and unmodeled boundaries."""
    candidate_id: str = Field(description="Target recovery candidate")
    overall_status: str = Field(description="VALID or INVALID")
    checks: List[ValidationCheck] = Field(default_factory=list)
    model_scope_notice: str = Field(
        default=(
            "Model enforces supplier outage blackout, throughput caps, lead-time arrival, and positive integer orders. "
            "Downstream factory assembly throughput and DC storage capacities are topological structural metadata and remain unconstrained (NOT_MODELED)."
        ),
        description="Explicit scope boundary notice",
    )


class DecisionTraceEvent(BaseContractModel):
    """Ordered event record in the end-to-end decision-making workflow."""
    step: int = Field(ge=1, description="Sequential step index in decision sequence")
    stage: str = Field(description="Decision stage identifier")
    event: str = Field(description="Event name")
    outcome: str = Field(description="Outcome status: SUCCESS, VERIFIED, AWAITING_APPROVAL, NOT_CONFIGURED")
    summary: str = Field(description="Concise description of the decision event")
    entity_reference: Optional[str] = Field(default=None, description="Referenced candidate, supplier, or parameter")
    timestamp_iso: Optional[str] = Field(default=None, description="ISO-8601 timestamp")


class RecoveryCandidate(BaseContractModel):
    """Candidate recovery plan with provenance, orders, validation, and simulated metrics."""
    candidate_id: str = Field(description="Stable deterministic candidate identifier")
    scenario_id: str = Field(description="Scenario signature")
    strategy_id: str = Field(description="Planning policy mode: agent, optimized, reorder")
    name: str = Field(description="Human-readable candidate plan name")
    description: str = Field(description="Strategy and objective description")
    objective_mode: str = Field(description="CP-SAT objective or heuristic mode")
    product_weights: Dict[str, float] = Field(description="Product shortage penalty weights applied")
    orders: List[Dict[str, Any]] = Field(description="Proposed candidate order schedule")
    validation: ValidationResult = Field(description="Feasibility validation against implemented constraints")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="Simulation-derived operational metrics")
    limitations: List[str] = Field(default_factory=list, description="Known operational and modeling boundaries")
    generation_status: str = Field(default="SUCCESS", description="Plan generation status: SUCCESS, FAILED")
    plan_fingerprint: Optional[str] = Field(default=None, description="Cryptographic SHA-256 digest of material plan details")
    validation_report: Optional[ValidationReport] = Field(default=None, description="Detailed validation breakdown")


class CandidateRanking(BaseContractModel):
    """Auditable ranking entry for an evaluated recovery candidate."""
    rank: Optional[int] = Field(default=None, description="1-based ranking position, or None if invalid")
    candidate_id: str = Field(description="Candidate identifier")
    strategy_id: str = Field(description="Strategy mode")
    name: str = Field(description="Candidate plan name")
    selectable: bool = Field(description="True if feasible and selectable under policy")
    score: Optional[float] = Field(default=None, description="Deterministic multi-criteria evaluation score, or None if candidate is an infeasible benchmark")
    p1_fill_rate: Optional[float] = Field(default=None, description="Priority 1 component fill rate percentage")
    aggregate_fill_rate: Optional[float] = Field(default=None, description="Aggregate fill rate percentage")
    total_landed_cost: Optional[float] = Field(default=None, description="Total landed cost in INR")
    recovery_day: Optional[int] = Field(default=None, description="Day sustained recovery is achieved")
    criteria_summary: str = Field(description="Summary of criteria evaluated")
    comparison_notes: str = Field(description="Comparative evaluation against other candidates")


class RecoverySelection(BaseContractModel):
    """Auditable rationale explaining the selected candidate and rejected alternatives."""
    selected_candidate_id: Optional[str] = Field(default=None, description="ID of selected candidate")
    selected_strategy_id: Optional[str] = Field(default=None, description="Strategy mode of selected candidate")
    selection_status: str = Field(description="SELECTED, BLOCKED, NEEDS_REVIEW")
    selection_rationale: str = Field(description="Justification for why this candidate was selected")
    tradeoffs_accepted: List[str] = Field(default_factory=list, description="Operational trade-offs accepted")
    rejected_alternatives: List[Dict[str, Any]] = Field(default_factory=list, description="Summary of non-selected alternatives and why they ranked lower")
    unresolved_risks: List[str] = Field(default_factory=list, description="Unmodeled or external risks remaining")
    planner_action_required: str = Field(description="Directive for the human planner")
    governance_notice: str = Field(default="No real-world purchase orders are dispatched. This decision docket is for human planner review and approval.", description="Execution boundary notice")


class RecoveryResponse(BaseContractModel):
    """Response payload for GET /api/recovery."""
    status: str = Field(description="Workflow status: awaiting_planner_approval, requires_review, planning_failed")
    scenario: ScenarioConfig
    agents: AgentReports
    optimization: OptimizationResponse
    validation: ValidationResult
    recommendation: Optional[RecoveryRecommendation] = None
    candidates: Optional[List[RecoveryCandidate]] = None
    conflicts: Optional[List[RecoveryConflict]] = None
    rankings: Optional[List[CandidateRanking]] = None
    selection: Optional[RecoverySelection] = None
    # Phase B6 trust layer extensions:
    workflow_state: str = Field(default="SELECTED", description="Workflow state: PROPOSED, VALIDATED, SELECTED, APPROVED, EXECUTED")
    plan_fingerprint: Optional[str] = Field(default=None, description="Cryptographic SHA-256 digest of the selected plan")
    decision_trace: Optional[List[DecisionTraceEvent]] = Field(default=None, description="Ordered decision trace of recovery evaluation")
    validation_report: Optional[ValidationReport] = Field(default=None, description="Comprehensive validation report of selected candidate")
    execution_status: str = Field(default="NOT_CONFIGURED", description="Execution boundary status")
    external_execution: bool = Field(default=False, description="Always False; no real ERP dispatch occurs")


# ==============================================================================
# 6C. PLANNER APPROVAL & GOVERNANCE SCHEMAS (Phase B6)
# ==============================================================================

class ApprovalRequest(BaseContractModel):
    """Payload for explicit planner approval or rejection of a candidate plan."""
    scenario_id: str = Field(description="Scenario identifier (e.g. SCEN-SD7-H21-S42)")
    candidate_id: str = Field(description="Candidate identifier being evaluated")
    action: str = Field(pattern="^(APPROVE|REJECT)$", description="Planner decision action: APPROVE or REJECT")
    plan_fingerprint: str = Field(description="SHA-256 fingerprint of the reviewed plan to bind decision to exact content")
    reviewer_label: Optional[str] = Field(default="Supply Planner", description="Self-reported demo reviewer label")
    comment: Optional[str] = Field(default=None, description="Optional planner decision comment")


class ApprovalRecord(BaseContractModel):
    """Immutable audit record of a human planner decision in the demo workflow."""
    record_id: str = Field(description="Unique approval record ID (e.g. APPR-REC-...)")
    scenario_id: str = Field(description="Scenario identifier")
    candidate_id: str = Field(description="Candidate identifier")
    strategy_id: str = Field(description="Strategy ID")
    plan_fingerprint: str = Field(description="Cryptographic plan fingerprint")
    action: str = Field(description="APPROVE or REJECT")
    workflow_state: str = Field(description="APPROVED or REJECTED")
    reviewer_label: str = Field(description="Self-reported reviewer identity")
    comment: Optional[str] = Field(default=None, description="Review comment")
    recorded_at: str = Field(description="ISO-8601 recorded timestamp")
    demo_mode: bool = Field(default=True, description="Always True for demo workflow")
    environment: str = Field(default="demo_decision_support", description="Operational environment")
    execution_status: str = Field(default="NOT_CONFIGURED", description="Real-world execution status")
    external_execution: bool = Field(default=False, description="Real-world external execution flag")
    notice: str = Field(
        default="Demo-only approval record. No live purchase orders or ERP transactions are dispatched.",
        description="Governance notice",
    )


class ExecutionAdapterStatus(BaseContractModel):
    """Status contract for external procurement and ERP execution boundary."""
    status: str = Field(default="NOT_CONFIGURED", description="Adapter status: NOT_CONFIGURED, UNAVAILABLE")
    available: bool = Field(default=False, description="True if real external execution adapter is live")
    external_execution: bool = Field(default=False, description="Always False in current phase")
    adapter_name: str = Field(default="NullExecutionAdapter", description="Active adapter implementation")
    notice: str = Field(
        default="Real-world purchase order dispatch is not configured. SupplyShield AI is an advisory decision-support system.",
        description="Governance notice",
    )


class DiagnosticsResponse(BaseContractModel):
    """Operational diagnostics snapshot for health and platform state."""
    app: str = Field(default="SupplyShield AI")
    version: str = Field(default="0.6.0")
    service_status: str = Field(default="operational")
    model_horizon_days: int = Field(default=21)
    model_seed: int = Field(default=42)
    supported_shutdown_days_range: List[int] = Field(default_factory=lambda: [1, 14])
    supported_strategies: List[str] = Field(default_factory=lambda: ["reorder", "optimized", "agent"])
    solver_status: str = Field(default="available")
    demo_approvals_enabled: bool = Field(default=True)
    approval_storage_type: str = Field(default="jsonl_ledger")
    approval_records_count: int = Field(default=0)
    execution_adapter_status: str = Field(default="NOT_CONFIGURED")
    external_execution_enabled: bool = Field(default=False)
    model_boundaries: List[str] = Field(default_factory=list)
    dataset_id: Optional[str] = Field(default="demo_v1", description="Active canonical dataset identifier")
    dataset_version: Optional[str] = Field(default="1.0.0", description="Active canonical dataset semantic version")
    dataset_fingerprint: Optional[str] = Field(default=None, description="Active dataset deterministic cryptographic fingerprint")
    data_source_type: Optional[str] = Field(default="synthetic_demo", description="Data source provenance classification")
    data_validation_status: Optional[str] = Field(default="VALID", description="Active dataset schema and relational validation status")


class ComparisonScenario(BaseContractModel):
    """Scenario parameters for strategy comparison benchmark."""
    shutdown_days: int = Field(ge=1, le=14)
    horizon_days: int = Field(default=21)
    seed: Optional[int] = Field(default=42, description="Simulation seed for reproducible evaluation")
    scenario_id: Optional[str] = Field(default=None, description="Deterministic scenario signature (e.g. SCEN-SD7-H21-S42)")


class ComparisonStrategies(BaseContractModel):
    """Three strategies evaluated under identical benchmark conditions."""
    reorder: SimulationResponse
    optimized: SimulationResponse
    agent: SimulationResponse


class ComparisonResponse(BaseContractModel):
    """Response payload for GET /api/compare."""
    scenario: ComparisonScenario
    strategies: ComparisonStrategies
