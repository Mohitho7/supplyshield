"""
SupplyShield AI — Supplier Risk & Sourcing Agent (Phase B3)

Responsibility:
  Monitors disruption telemetry, enforces facility outage windows,
  evaluates alternate vendor eligibility, daily shared capacity limits,
  and landed procurement cost implications.
"""

from typing import List, Dict, Any, Optional

try:
    from agents.common import extract_context
    from schemas import AgentScenarioContext
except ImportError:
    from backend.agents.common import extract_context
    from backend.schemas import AgentScenarioContext


def supplier_risk_agent(
    network_or_context: Any = None,
    shutdown_days: int = 7,
    horizon_days: int = 21,
) -> List[Dict[str, Any]]:
    """
    Supplier Risk & Sourcing Agent.

    Evaluates primary supplier disruption status, qualified alternate capacity,
    sourcing eligibility by day, landed cost differentials, and supplier constraints.

    Returns structured proposals conforming to the AgentProposal contract.
    """
    ctx: AgentScenarioContext = extract_context(
        network_or_context, shutdown_days=shutdown_days, horizon_days=horizon_days
    )

    proposals: List[Dict[str, Any]] = []

    # Calculate total daily demand across products for capacity deficit calculation
    total_daily_demand = sum(p.get("daily_demand", 0) for p in ctx.products)

    for supplier in ctx.suppliers:
        sid = supplier.get("id", "UNKNOWN")
        name = supplier.get("name", "Unknown Supplier")
        capacity = supplier.get("capacity", 0)
        lead_time = supplier.get("lead_time", 2)
        unit_cost = supplier.get("unit_cost", 10.0 if sid == "SUP-01" else 13.0)
        freight_cost = ctx.transport_costs.get(sid, 2.0 if sid == "SUP-01" else 3.5)
        landed_cost = unit_cost + freight_cost

        is_disrupted = (
            sid == ctx.disrupted_supplier_id and ctx.shutdown_days > 0
        )

        # Capacity deficit compared to total daily demand
        capacity_deficit = max(0, total_daily_demand - capacity)

        # Sourcing eligibility windows
        if is_disrupted:
            eligible_days_range = f"Days {ctx.shutdown_days + 1} to {ctx.horizon_days}"
            outage_days_range = f"Days 1 to {ctx.shutdown_days}"
            risk_label = "CRITICAL"
            status_desc = "OFFLINE (Facility outage active)"
        else:
            eligible_days_range = f"Days 1 to {ctx.horizon_days}"
            outage_days_range = "None"
            risk_label = "AVAILABLE"
            status_desc = "ONLINE (Qualified active vendor)"

        findings = [
            {
                "observation": "Supplier operational status",
                "value": status_desc,
                "outage_window": outage_days_range,
            },
            {
                "observation": "Shared daily dispatch capacity",
                "value": capacity,
                "units": "units/day across all products",
            },
            {
                "observation": "Transit lead time",
                "value": lead_time,
                "units": "days",
            },
            {
                "observation": "Landed unit procurement cost",
                "value": landed_cost,
                "units": f"INR/unit (base ₹{unit_cost} + freight ₹{freight_cost})",
            },
            {
                "observation": "Daily throughput deficit vs demand",
                "value": capacity_deficit,
                "units": f"units/day against {total_daily_demand}u/d demand",
            },
        ]

        evidence = {
            "supplier_id": sid,
            "disruption_active": is_disrupted,
            "shutdown_days": ctx.shutdown_days if is_disrupted else 0,
            "daily_capacity": capacity,
            "lead_time_days": lead_time,
            "base_unit_cost_inr": unit_cost,
            "freight_cost_inr": freight_cost,
            "total_landed_cost_inr": landed_cost,
            "eligible_order_window": eligible_days_range,
            "network_daily_demand": total_daily_demand,
            "shared_capacity_deficit": capacity_deficit,
        }

        limitations = [
            "Historical supplier reliability rates, delivery variance, and credit risk are not modeled.",
            "Synthetic scenario rules guarantee configured availability; real-world external vendor stock is unconfirmed.",
            "Supplier capacity is shared across all product lines; individual order checks alone do not guarantee aggregate feasibility.",
        ]

        handoff = {
            "supplier_id": sid,
            "is_available_for_orders": not is_disrupted,
            "earliest_eligible_order_day": ctx.shutdown_days + 1 if is_disrupted else 1,
            "shared_daily_capacity": capacity,
            "lead_time_days": lead_time,
            "landed_cost_per_unit": landed_cost,
            "capacity_is_constrained": capacity < total_daily_demand,
        }

        recommendation = (
            f"Primary supplier offline for {ctx.shutdown_days} days. Divert all replenishment orders to SUP-02."
            if is_disrupted
            else f"Qualified backup vendor available. Shared capacity capped at {capacity} units/day."
        )

        reason = (
            f"{name} is shut down on Days 1-{ctx.shutdown_days}; lead time is {lead_time} days."
            if is_disrupted
            else f"{name} active with {lead_time}-day lead time and {capacity} units/day limit."
        )

        proposals.append({
            "agent": "supplier_risk",
            "action": "assess_supplier",
            "supplier": sid,
            "supplier_name": name,
            "risk": risk_label,
            "shutdown_days": ctx.shutdown_days if is_disrupted else 0,
            "capacity": capacity,
            "recommendation": recommendation,
            "reason": reason,
            "confidence": 0.99,
            "status": "SUCCESS",
            "findings": findings,
            "evidence": evidence,
            "limitations": limitations,
            "handoff": handoff,
        })

    return proposals
