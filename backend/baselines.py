"""
SupplyShield AI - Strategy Planning Baselines

Defines the three distinct planning policies evaluated on the same synthetic supply network:
1. reorder_rules_plan: Fixed target-stock reordering from primary supplier (disrupted during shutdown)
2. optimization_only_plan: Mathematical optimization using Google OR-Tools CP-SAT (pure cost minimization)
3. agent_assisted_plan: Coordinated multi-agent optimization with product priority weighting and buffer targets
"""

from typing import List, Dict, Any
from copy import deepcopy
from simulator import NETWORK, TRANSPORT_COST, HORIZON
from optimizer import optimize_plan


def reorder_rules_plan(shutdown_days: int = 7, horizon: int = HORIZON) -> Dict[str, Any]:
    """
    Strategy 1: Traditional Reorder Point / Target Stock Rules.

    Policy:
      - Always orders replenishment from primary supplier SUP-01.
      - Target stock = 3 days of product demand.
      - Order quantity = max(0, target_stock - (inventory + on_order)).
      - Orders placed on days 1..shutdown_days are rejected because SUP-01 is shut down.
      - Orders placed on days > shutdown_days arrive after SUP-01 lead time (2 days).
      - No contingency supplier (SUP-02) is engaged.
    """
    products = NETWORK["products"]
    suppliers = {s["id"]: s for s in NETWORK["suppliers"]}
    primary_supplier = suppliers["SUP-01"]

    orders: List[Dict[str, Any]] = []
    inventory = {p["id"]: p["initial_inventory"] for p in products}
    pipeline: List[Dict[str, Any]] = []

    for day in range(1, horizon + 1):
        # 1. Receive pipeline arrivals
        for order in [o for o in pipeline if o["arrival_day"] == day]:
            inventory[order["product_id"]] += order["quantity"]
        pipeline = [o for o in pipeline if o["arrival_day"] != day]

        # 2. Consume daily demand
        for p in products:
            pid = p["id"]
            fulfilled = min(inventory[pid], p["daily_demand"])
            inventory[pid] -= fulfilled

        # 3. Replenishment ordering decision
        remaining_capacity = primary_supplier["capacity"]
        for p in products:
            pid = p["id"]
            demand = p["daily_demand"]
            on_order = sum(o["quantity"] for o in pipeline if o["product_id"] == pid)
            position = inventory[pid] + on_order
            target = 3 * demand
            needed = max(0, target - position)

            if needed == 0:
                continue

            qty = min(needed, remaining_capacity)
            if qty <= 0:
                continue

            arrival_day = day + primary_supplier["lead_time"]
            if arrival_day > horizon:
                continue

            cost = qty * (primary_supplier["unit_cost"] + TRANSPORT_COST["SUP-01"])

            order_entry = {
                "order_day": day,
                "arrival_day": arrival_day,
                "product": pid,
                "supplier": "SUP-01",
                "quantity": qty,
                "cost": round(cost, 2),
                "strategy": "reorder_rules",
            }
            orders.append(order_entry)

            # During shutdown, primary supplier cannot accept orders (rejected)
            if day <= shutdown_days:
                continue

            remaining_capacity -= qty
            pipeline.append({
                "product_id": pid,
                "quantity": qty,
                "arrival_day": arrival_day,
            })

    return {
        "strategy": "reorder",
        "name": "Reorder Rules",
        "description": "Static target-stock replenishment with primary supplier only. Orders attempted during shutdown are rejected.",
        "orders": orders,
    }


def optimization_only_plan(shutdown_days: int = 7, horizon: int = HORIZON) -> Dict[str, Any]:
    """
    Strategy 2: Pure Cost-Minimization Mathematical Optimization.

    Policy:
      - Uses Google OR-Tools CP-SAT to solve multi-period sourcing MIP.
      - Explores both primary (SUP-01) and alternate (SUP-02) suppliers.
      - Objective treats shortage penalties uniformly across all products (no business priority weighting).
      - Respects supplier daily capacities, shutdown windows, and lead times.
    """
    opt_result = optimize_plan(shutdown_days=shutdown_days, priority_weighted=False)
    orders = opt_result.get("orders", [])

    return {
        "strategy": "optimized",
        "name": "Optimization Only",
        "description": "OR-Tools CP-SAT multi-period mathematical solver with uniform shortage penalty.",
        "orders": orders,
        "solver_metrics": opt_result.get("metrics", {}),
        "solver_status": opt_result.get("status", "UNKNOWN"),
    }


def agent_assisted_plan(shutdown_days: int = 7, horizon: int = HORIZON) -> Dict[str, Any]:
    """
    Strategy 3: Agent-Assisted Coordinated Recovery.

    Policy:
      - Demand Intelligence Agent: recognizes PROD-01 is Priority 1 critical component; doubles shortage penalty
        weight to protect critical service level when alternate supplier capacity (60 units) is scarce.
      - Supplier Risk Agent: detects 7-day disruption at SUP-01, directing orders to qualified alternate SUP-02.
      - Inventory Analyst Agent: projects stockout by Day 3 and flags urgent buffer replenishment.
      - Logistics Planner Agent: accounts for 4-day transit lead time from SUP-02, initiating orders on Day 1.
      - Coordinator translates agent directives into priority-weighted mathematical optimization constraints.
    """
    opt_result = optimize_plan(shutdown_days=shutdown_days, priority_weighted=True)
    orders = opt_result.get("orders", [])

    return {
        "strategy": "agent",
        "name": "Agent-Assisted Recovery",
        "description": "Multi-agent coordination (Demand, Inventory, Risk, Logistics) + Priority-weighted OR-Tools solver.",
        "orders": orders,
        "solver_metrics": opt_result.get("metrics", {}),
        "solver_status": opt_result.get("status", "UNKNOWN"),
    }
