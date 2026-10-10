"""
SupplyShield AI — Agent Shared Context & Helpers (Phase B3)

Provides deterministic scenario context creation, typed models,
and data extraction helpers for the four specialist agents.
"""

from copy import deepcopy
from typing import Dict, Any, List, Optional

try:
    from simulator import NETWORK, TRANSPORT_COST, HORIZON
    from schemas import AgentScenarioContext, AgentProposal
except ImportError:
    from backend.simulator import NETWORK, TRANSPORT_COST, HORIZON
    from backend.schemas import AgentScenarioContext, AgentProposal


def build_scenario_context(
    network: Optional[Dict[str, Any]] = None,
    shutdown_days: int = 7,
    horizon_days: int = HORIZON,
    current_day: int = 1,
    disrupted_supplier_id: str = "SUP-01",
    transport_costs: Optional[Dict[str, float]] = None,
    inbound_orders: Optional[List[Dict[str, Any]]] = None,
    seed: int = 42,
) -> AgentScenarioContext:
    """
    Construct a strongly-typed deterministic AgentScenarioContext.
    Produces a signature like 'SCEN-SD7-H21-S42' without implying database persistence.
    """
    net = deepcopy(network) if network is not None else deepcopy(NETWORK)
    t_costs = deepcopy(transport_costs) if transport_costs is not None else deepcopy(TRANSPORT_COST)
    orders = deepcopy(inbound_orders) if inbound_orders is not None else []

    scenario_sig = f"SCEN-SD{shutdown_days}-H{horizon_days}-S{seed}"

    return AgentScenarioContext(
        scenario_id=scenario_sig,
        shutdown_days=shutdown_days,
        horizon_days=horizon_days,
        current_day=current_day,
        disrupted_supplier_id=disrupted_supplier_id,
        products=net.get("products", []),
        suppliers=net.get("suppliers", []),
        transport_costs=t_costs,
        inbound_orders=orders,
        seed=seed,
    )


def extract_context(
    network_or_context: Any,
    shutdown_days: int = 7,
    horizon_days: int = HORIZON,
    inbound_orders: Optional[List[Dict[str, Any]]] = None,
) -> AgentScenarioContext:
    """
    Polymorphic context resolver: accepts either an AgentScenarioContext
    or a legacy network dict, normalizing to AgentScenarioContext.
    """
    if isinstance(network_or_context, AgentScenarioContext):
        return network_or_context
    elif isinstance(network_or_context, dict) and "scenario_id" in network_or_context:
        return AgentScenarioContext.model_validate(network_or_context)
    elif isinstance(network_or_context, dict) and "products" in network_or_context:
        return build_scenario_context(
            network=network_or_context,
            shutdown_days=shutdown_days,
            horizon_days=horizon_days,
            inbound_orders=inbound_orders,
        )
    else:
        return build_scenario_context(
            shutdown_days=shutdown_days,
            horizon_days=horizon_days,
            inbound_orders=inbound_orders,
        )
