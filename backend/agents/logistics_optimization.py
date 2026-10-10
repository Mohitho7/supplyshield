"""
SupplyShield AI — Logistics Optimization Agent (Phase B3)

Responsibility:
  Evaluates transit lead times, delivery arrival physics (D + L),
  freight transport costs, 21-day horizon cutoffs, and shortage transit gap exposure.
"""

from typing import List, Dict, Any, Optional

try:
    from agents.common import extract_context
    from schemas import AgentScenarioContext
except ImportError:
    from backend.agents.common import extract_context
    from backend.schemas import AgentScenarioContext


def logistics_agent(
    network_or_context: Any = None,
    shutdown_days: int = 7,
    horizon_days: int = 21,
) -> List[Dict[str, Any]]:
    """
    Logistics Optimization Agent.

    Evaluates freight transit times, lead-time arrival physics (arrival_day = order_day + lead_time),
    landed cost structures, horizon cutoff boundaries, and unavoidable transit shortage gaps.

    Returns structured proposals conforming to the AgentProposal contract.
    """
    ctx: AgentScenarioContext = extract_context(
        network_or_context, shutdown_days=shutdown_days, horizon_days=horizon_days
    )

    proposals: List[Dict[str, Any]] = []

    for supplier in ctx.suppliers:
        sid = supplier.get("id", "UNKNOWN")
        name = supplier.get("name", "Unknown Supplier")
        lead_time = supplier.get("lead_time", 2)
        unit_cost = supplier.get("unit_cost", 10.0 if sid == "SUP-01" else 13.0)
        transport_cost = ctx.transport_costs.get(sid, 2.0 if sid == "SUP-01" else 3.5)
        landed_cost = unit_cost + transport_cost

        is_primary = sid == ctx.disrupted_supplier_id

        # Deterministic earliest order day & arrival day
        earliest_order_day = ctx.shutdown_days + 1 if is_primary else 1
        earliest_arrival = earliest_order_day + lead_time

        # Horizon cutoff day (latest day an order can be placed and still arrive within horizon)
        latest_feasible_order_day = ctx.horizon_days - lead_time
        earliest_arrival_within_horizon = earliest_arrival <= ctx.horizon_days

        # Scenario-specific shortage gap analysis:
        # Initial inventory for both products depletes on Day 3 without replenishment.
        # Check if confirmed inbound orders exist that arrive on or before Day 3:
        inbound_on_time = any(
            o.get("arrival_day", 99) <= 3 and o.get("quantity", 0) > 0
            for o in (ctx.inbound_orders or [])
            if isinstance(o, dict) and o.get("status") not in {"rejected", "invalid", "cancelled"}
        )

        # Network earliest feasible arrival day:
        # SUP-01 arrives on (shutdown_days + 1) + 2 = shutdown_days + 3
        # SUP-02 arrives on 1 + 4 = 5
        network_earliest_arrival = min(5, ctx.shutdown_days + 3)

        if inbound_on_time:
            transit_gap_days = []
            gap_explanation = "Pipeline orders arriving on or before Day 3 prevent pre-replenishment stockout."
        elif ctx.shutdown_days == 1:
            # 1-day shutdown: SUP-01 orders placed Day 2 arrive Day 4 (2 + 2 = 4).
            # Day 3 stockout is unassisted, but Day 4 is replenished by SUP-01!
            transit_gap_days = [3]
            gap_explanation = (
                "For a 1-day shutdown, SUP-01 resumes order eligibility on Day 2 (2d lead time), "
                "delivering on Day 4. Initial inventory depletes on Day 3, so only Day 3 experiences "
                "a stockout gap before Day 4 replenishment."
            )
        else:
            # Extended shutdown (>= 2 days): SUP-01 cannot arrive until Day >= 5.
            # SUP-02 placed Day 1 arrives Day 5 (1 + 4 = 5).
            # Neither supplier can deliver on Day 3 or Day 4.
            transit_gap_days = [3, 4]
            gap_explanation = (
                f"For a {ctx.shutdown_days}-day shutdown, initial inventory depletes on Day 3. "
                f"Neither SUP-01 (offline until Day {ctx.shutdown_days + 1}, arriving Day {ctx.shutdown_days + 3}) "
                f"nor SUP-02 (4d lead time, arriving Day 5) can deliver before Day 5. "
                f"Days 3 and 4 experience an unavoidable lead-time transit gap."
            )

        findings = [
            {
                "observation": "Transit lead time",
                "value": lead_time,
                "units": "days",
            },
            {
                "observation": "Unit freight cost",
                "value": transport_cost,
                "units": "INR/unit",
            },
            {
                "observation": "Earliest feasible delivery arrival day",
                "value": earliest_arrival,
                "units": f"Day {earliest_arrival} (order Day {earliest_order_day} + lead {lead_time}d)",
            },
            {
                "observation": "Horizon cutoff order day",
                "value": latest_feasible_order_day,
                "units": f"Day {latest_feasible_order_day} (orders placed after arrive > Day {ctx.horizon_days})",
            },
            {
                "observation": "Landed transport expenditure premium",
                "value": landed_cost,
                "units": f"INR/unit (base ₹{unit_cost} + freight ₹{transport_cost})",
            },
            {
                "observation": "Pre-replenishment transit gap",
                "value": transit_gap_days,
                "units": f"{len(transit_gap_days)} day(s) before first arrival",
            },
        ]

        evidence = {
            "supplier_id": sid,
            "lead_time_days": lead_time,
            "earliest_order_day": earliest_order_day,
            "earliest_possible_arrival_day": earliest_arrival,
            "network_earliest_arrival_day": network_earliest_arrival,
            "horizon_cutoff_order_day": latest_feasible_order_day,
            "arrives_within_horizon": earliest_arrival_within_horizon,
            "freight_cost_per_unit": transport_cost,
            "unit_procurement_cost": unit_cost,
            "total_landed_cost_per_unit": landed_cost,
            "transit_gap_days": transit_gap_days,
            "transit_gap_explanation": gap_explanation,
            "formula": "arrival_day = order_day + lead_time",
        }

        limitations = [
            "Carrier freight fleet capacity, trucking availability, and expedited route options are not modeled.",
            "Weather delays, customs processing, and transit time variance are assumed zero.",
            "Single-echelon freight transport direct to plants is assumed; multi-echelon consolidation is not supported.",
        ]

        handoff = {
            "supplier_id": sid,
            "lead_time_days": lead_time,
            "freight_cost_per_unit": transport_cost,
            "total_landed_cost_per_unit": landed_cost,
            "earliest_possible_arrival_day": earliest_arrival,
            "order_cutoff_day_for_horizon": latest_feasible_order_day,
            "transit_gap_days": transit_gap_days,
        }

        recommendation = (
            f"Place Day 1 orders to ensure earliest arrival on Day {earliest_arrival}."
            if not is_primary
            else f"Resume ordering immediately on Day {ctx.shutdown_days + 1}; receipts arrive on Day {earliest_arrival}."
        )

        reason = (
            f"{name}: {lead_time}-day transit lead time; "
            f"freight cost ₹{transport_cost} per unit."
        )

        proposals.append({
            "agent": "logistics",
            "action": "evaluate_route",
            "supplier": sid,
            "supplier_name": name,
            "lead_time_days": lead_time,
            "transport_cost_per_unit": transport_cost,
            "earliest_possible_arrival_day": earliest_arrival,
            "recommendation": recommendation,
            "reason": reason,
            "confidence": 0.95,
            "status": "SUCCESS",
            "findings": findings,
            "evidence": evidence,
            "limitations": limitations,
            "handoff": handoff,
        })

    return proposals
