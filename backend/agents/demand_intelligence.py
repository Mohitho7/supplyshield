"""
SupplyShield AI — Demand Intelligence Agent (Phase B3)

Responsibility:
  Evaluates product criticality tiers, daily demand volume, total demand exposure,
  and customer service impact when supply is constrained.
  Generates priority-weighted allocation guidance and handoff contracts for planning.
"""

from typing import List, Dict, Any, Optional

try:
    from agents.common import extract_context
    from schemas import AgentScenarioContext
except ImportError:
    from backend.agents.common import extract_context
    from backend.schemas import AgentScenarioContext


def demand_agent(
    network_or_context: Any = None,
    shutdown_days: int = 7,
    horizon_days: int = 21,
) -> List[Dict[str, Any]]:
    """
    Demand Intelligence Agent.

    Evaluates product criticality tiers, daily demand exposure across the 21-day horizon,
    and priority allocation trade-offs under alternate supplier capacity constraints.

    Returns a list of structured proposals conforming to the AgentProposal contract.
    """
    ctx: AgentScenarioContext = extract_context(
        network_or_context, shutdown_days=shutdown_days, horizon_days=horizon_days
    )

    proposals: List[Dict[str, Any]] = []

    # Sort products by configured priority tier (1 = Highest Criticality)
    sorted_products = sorted(
        ctx.products, key=lambda p: p.get("priority", 99)
    )

    # Compute network-level demand parameters
    total_network_daily_demand = sum(p.get("daily_demand", 0) for p in ctx.products)
    alternate_supplier = next(
        (s for s in ctx.suppliers if s.get("id") != ctx.disrupted_supplier_id),
        None,
    )
    alternate_capacity = alternate_supplier.get("capacity", 60) if alternate_supplier else 60

    for product in sorted_products:
        pid = product.get("id", "UNKNOWN")
        name = product.get("name", "Unknown Product")
        priority = product.get("priority", 2)
        daily_demand = product.get("daily_demand", 0)
        is_tier1 = priority == 1

        # Check for malformed or limited data
        has_valid_demand = isinstance(daily_demand, int) and daily_demand > 0
        status = "SUCCESS" if has_valid_demand else "LIMITED"

        # Deterministic demand exposure over planning horizon
        horizon_demand_exposure = daily_demand * ctx.horizon_days if has_valid_demand else 0

        # Priority-aware capacity allocation guidance under constrained alternate supply
        if is_tier1:
            recommended_daily_allocation = min(daily_demand, alternate_capacity)
            expected_daily_shortfall = max(0, daily_demand - alternate_capacity)
            service_target_desc = ">=90% fill rate (heuristic operational guideline; not an external contractual SLA)"
            tradeoff_note = (
                f"Full allocation of {recommended_daily_allocation}u/d from alternate capacity "
                f"protects Tier 1 demand but leaves only {max(0, alternate_capacity - recommended_daily_allocation)}u/d "
                f"for Tier 2 components."
            )
        else:
            tier1_daily_demand = sum(
                p.get("daily_demand", 0) for p in ctx.products if p.get("priority", 99) < priority
            )
            remaining_cap = max(0, alternate_capacity - tier1_daily_demand)
            recommended_daily_allocation = min(daily_demand, remaining_cap)
            expected_daily_shortfall = max(0, daily_demand - remaining_cap)
            service_target_desc = "Secondary buffer (best-effort fulfillment after Tier 1)"
            tradeoff_note = (
                f"Subordinated to Priority 1 allocation. Experiences {expected_daily_shortfall}u/d "
                f"daily capacity deficit during alternate vendor sole-source window."
            )

        findings = [
            {
                "observation": "Configured product criticality",
                "value": f"Priority {priority}",
                "tier": "Tier 1 (Critical)" if is_tier1 else "Tier 2 (Standard)",
            },
            {
                "observation": "Deterministic daily demand requirement",
                "value": daily_demand,
                "units": "units/day",
            },
            {
                "observation": "Cumulative horizon demand exposure",
                "value": horizon_demand_exposure,
                "units": f"units over {ctx.horizon_days} days",
            },
            {
                "observation": "Disruption window capacity allocation",
                "value": recommended_daily_allocation,
                "units": "units/day recommended from SUP-02",
            },
            {
                "observation": "Projected daily deficit during disruption",
                "value": expected_daily_shortfall,
                "units": "units/day deficit",
            },
            {
                "observation": "Operational service target",
                "value": ">=90% fill rate" if is_tier1 else "Best-effort buffer",
                "target_type": "DEMONSTRATION_HEURISTIC",
                "target_description": service_target_desc,
            },
        ]

        evidence = {
            "scenario_signature": ctx.scenario_id,
            "configured_priority": priority,
            "daily_demand": daily_demand,
            "horizon_days": ctx.horizon_days,
            "total_demand_exposure": horizon_demand_exposure,
            "network_total_daily_demand": total_network_daily_demand,
            "alternate_capacity_cap": alternate_capacity,
            "recommended_daily_allocation": recommended_daily_allocation,
            "daily_shortfall_during_outage": expected_daily_shortfall,
            "tradeoff_analysis": tradeoff_note,
            "service_target": service_target_desc,
            "service_target_type": "DEMONSTRATION_HEURISTIC",
        }

        limitations = [
            "Deterministic daily demand assumed; stochastic customer demand spikes or cancellations are not modeled.",
            "The 90% service target for Priority 1 is a demonstration heuristic guiding contingency capacity allocation, not a contractual customer SLA or external legal commitment.",
            "Demand exposure represents gross customer order requirements, not achieved fulfilled volume.",
        ]

        handoff = {
            "product_id": pid,
            "priority_tier": priority,
            "is_critical": is_tier1,
            "daily_demand": daily_demand,
            "horizon_demand": horizon_demand_exposure,
            "recommended_solver_weight": 2.0 if is_tier1 else 1.0,
            "target_service_level": 0.90 if is_tier1 else 0.80,
            "service_target_type": "DEMONSTRATION_HEURISTIC",
            "min_recommended_daily_allocation": recommended_daily_allocation,
        }

        proposals.append({
            "agent": "demand",
            "action": "prioritize_product",
            "product": pid,
            "product_name": name,
            "daily_demand": daily_demand,
            "priority": priority,
            "criticality": "CRITICAL (Tier 1)" if is_tier1 else "STANDARD (Tier 2)",
            "recommendation": (
                "Prioritize alternate supplier capacity to maintain >=90% fill rate."
                if is_tier1
                else "Buffer remaining capacity after Tier 1 demand is satisfied."
            ),
            "reason": (
                f"{name} carries Priority {priority} with {daily_demand} units/day demand. "
                f"Operational policy prioritizes Tier 1 to protect critical service (heuristic target >=90%, not contractual SLA)."
            ),
            "confidence": 0.95,
            "status": status,
            "findings": findings,
            "evidence": evidence,
            "limitations": limitations,
            "handoff": handoff,
        })

    return proposals
