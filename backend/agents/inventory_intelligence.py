"""
SupplyShield AI — Inventory Intelligence Agent (Phase B3)

Responsibility:
  Calculates inventory runway (days of cover), projected stockout timing,
  inbound replenishment pipeline effects, shortage duration windows,
  and replenishment urgency for each product component.
"""

from typing import List, Dict, Any, Optional

try:
    from agents.common import extract_context
    from schemas import AgentScenarioContext
except ImportError:
    from backend.agents.common import extract_context
    from backend.schemas import AgentScenarioContext


def inventory_agent(
    network_or_context: Any = None,
    shutdown_days: int = 7,
    horizon_days: int = 21,
    inbound_orders: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Inventory Intelligence Agent.

    Evaluates current on-hand stock, burn rates, baseline runway,
    confirmed pipeline arrivals, shortage exposure windows, and replenishment urgency.

    Returns structured proposals conforming to the AgentProposal contract.
    """
    ctx: AgentScenarioContext = extract_context(
        network_or_context,
        shutdown_days=shutdown_days,
        horizon_days=horizon_days,
        inbound_orders=inbound_orders,
    )

    proposals: List[Dict[str, Any]] = []

    # Filter for confirmed valid inbound orders
    # Only orders that are explicitly confirmed/ordered with positive integer quantities
    confirmed_inbounds = []
    for order in (ctx.inbound_orders or []):
        if not isinstance(order, dict):
            continue
        qty = order.get("quantity", 0)
        arr_day = order.get("arrival_day")
        status = order.get("status", "ordered")
        # Exclude rejected, proposed, or invalid orders
        if status in {"rejected", "invalid", "cancelled"}:
            continue
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            continue
        if isinstance(arr_day, bool) or not isinstance(arr_day, int) or arr_day < 1:
            continue
        confirmed_inbounds.append(order)

    for product in ctx.products:
        pid = product.get("id", "UNKNOWN")
        name = product.get("name", "Unknown Product")
        demand = product.get("daily_demand", 0)
        stock = product.get("initial_inventory", 0)

        # Check for zero or invalid demand / stock
        valid_demand = isinstance(demand, int) and demand > 0
        valid_stock = isinstance(stock, int) and stock >= 0

        if not valid_demand or not valid_stock:
            coverage = 0.0
            stockout_day = None
            status = "LIMITED"
            risk = "NO_DEMAND" if demand == 0 else "UNKNOWN"
            reason = (
                f"Cannot compute inventory runway for {name}: daily demand is "
                f"{demand} units/day."
            )
            recommendation = "Demand data invalid or missing; inventory analysis limited."
            confidence = 0.50
            findings = [
                {"observation": "Demand validity", "value": "INVALID or ZERO", "units": "units/day"},
                {"observation": "Usable inventory", "value": stock, "units": "units"},
            ]
            evidence = {
                "initial_on_hand": stock,
                "daily_demand": demand,
                "days_of_cover": None,
                "stockout_day": None,
            }
            limitations = ["Daily demand is zero or non-positive; stockout calculation undefined."]
            handoff = {
                "product_id": pid,
                "on_hand_inventory": stock,
                "days_of_cover": None,
                "stockout_day": None,
                "replenishment_urgency": "NONE",
            }
        else:
            coverage = stock / demand
            stockout_day = int(coverage) + 1
            status = "SUCCESS"
            risk = "HIGH" if coverage < 3 else "MODERATE"
            confidence = 0.99

            # Evaluate trajectory with confirmed pipeline arrivals
            # Matching B1 simulation convention: order arrives at start of day before demand
            prod_arrivals = [
                o for o in confirmed_inbounds
                if (o.get("product") == pid or o.get("product_id") == pid)
            ]
            confirmed_inbound_qty = sum(o["quantity"] for o in prod_arrivals)

            # Day-by-day inventory projection
            curr_inv = stock
            sim_stockout_day = None
            shortage_start = None
            shortage_days_count = 0

            for day in range(1, ctx.horizon_days + 1):
                # Add arrivals at start of day
                day_arrivals = sum(o["quantity"] for o in prod_arrivals if o["arrival_day"] == day)
                curr_inv += day_arrivals

                # Check if demand can be met
                if curr_inv < demand:
                    if sim_stockout_day is None:
                        sim_stockout_day = day
                    if shortage_start is None:
                        shortage_start = day
                    shortage_days_count += 1
                    curr_inv = 0
                else:
                    curr_inv -= demand

            # If no confirmed inbounds exist, sim_stockout_day equals basic stockout_day
            effective_depletion_day = sim_stockout_day if prod_arrivals else stockout_day

            # Shortage window analysis
            earliest_arr = min((o["arrival_day"] for o in prod_arrivals), default=None)
            if earliest_arr and stockout_day:
                if earliest_arr > stockout_day:
                    shortage_window = {
                        "shortage_start_day": stockout_day,
                        "replenishment_arrival_day": earliest_arr,
                        "uncovered_days": earliest_arr - stockout_day,
                    }
                else:
                    shortage_window = {
                        "shortage_start_day": None,
                        "replenishment_arrival_day": earliest_arr,
                        "uncovered_days": 0,
                    }
            else:
                shortage_window = {
                    "shortage_start_day": stockout_day,
                    "replenishment_arrival_day": None,
                    "uncovered_days": max(0, ctx.horizon_days - stockout_day + 1) if stockout_day else 0,
                }

            findings = [
                {
                    "observation": "Current usable on-hand inventory",
                    "value": stock,
                    "units": "units",
                },
                {
                    "observation": "Baseline runway without replenishment",
                    "value": round(coverage, 2),
                    "units": "days",
                },
                {
                    "observation": "Projected stockout day without new receipts",
                    "value": stockout_day,
                    "units": "day index",
                },
                {
                    "observation": "Confirmed pipeline inbounds",
                    "value": confirmed_inbound_qty,
                    "units": f"units across {len(prod_arrivals)} orders",
                },
                {
                    "observation": "Effective depletion day with pipeline",
                    "value": effective_depletion_day,
                    "units": "day index",
                },
            ]

            evidence = {
                "initial_on_hand_stock": stock,
                "daily_demand_burn_rate": demand,
                "initial_coverage_days": round(coverage, 2),
                "unassisted_stockout_day": stockout_day,
                "effective_depletion_day": effective_depletion_day,
                "confirmed_inbound_units": confirmed_inbound_qty,
                "shortage_window": shortage_window,
            }

            limitations = [
                "Intra-day safety stock buffer is zero; all on-hand inventory is assumed 100% usable.",
                "Warehouse physical bin capacity, stock rotation, and holding decay are not modeled.",
                "Only confirmed inbound purchase orders with explicit arrival days extend projected runway.",
            ]

            handoff = {
                "product_id": pid,
                "on_hand_inventory": stock,
                "days_of_cover": round(coverage, 2),
                "unassisted_stockout_day": stockout_day,
                "effective_depletion_day": effective_depletion_day,
                "shortage_window": shortage_window,
                "replenishment_urgency": "CRITICAL" if coverage < 2.5 else "HIGH" if coverage < 3 else "ROUTINE",
                "latest_acceptable_arrival_day": stockout_day,
            }

            recommendation = (
                f"Urgent replenishment needed. Stockout projected on Day {stockout_day} without pipeline receipts."
            )
            reason = (
                f"Initial stock ({stock} units) provides only {coverage:.1f} days of cover "
                f"at {demand} units/day burn rate."
            )

        proposals.append({
            "agent": "inventory",
            "action": "assess_stock",
            "product": pid,
            "product_name": name,
            "inventory": stock,
            "daily_demand": demand,
            "days_of_cover": round(coverage, 2),
            "stockout_day": stockout_day,
            "risk": risk,
            "recommendation": recommendation,
            "reason": reason,
            "confidence": confidence,
            "status": status,
            "findings": findings,
            "evidence": evidence,
            "limitations": limitations,
            "handoff": handoff,
        })

    return proposals
