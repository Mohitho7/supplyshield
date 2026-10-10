import time
from copy import deepcopy
from typing import List, Dict, Any, Optional

try:
    from data_repository import get_active_dataset
except ImportError:
    from backend.data_repository import get_active_dataset

# Initialize canonical model configuration from validated data repository snapshot
_active_dataset = get_active_dataset()
NETWORK = _active_dataset.to_network_dict()
TRANSPORT_COST = _active_dataset.to_transport_cost_dict()
HORIZON = _active_dataset.horizon
TARGET_FILL_RATE = _active_dataset.target_fill_rate


def calculate_recovery_day(
    daily_results: List[Dict[str, Any]],
    target_fill_rate: float = TARGET_FILL_RATE,
) -> Optional[int]:
    """
    Sustained recovery requires 3 consecutive days at or above target_fill_rate (95.0%)
    occurring on or after the first disruption dip below target.
    If no disruption dip occurs, returns Day 1 (fully resilient).
    If sustained recovery is never achieved within the horizon, returns None.
    """
    first_dip_day = None
    for r in daily_results:
        if r["fill_rate"] < target_fill_rate:
            first_dip_day = r["day"]
            break

    if first_dip_day is None:
        return 1

    for i in range(len(daily_results) - 2):
        if daily_results[i]["day"] >= first_dip_day:
            window = daily_results[i:i + 3]
            if all(r["fill_rate"] >= target_fill_rate for r in window):
                return window[0]["day"]

    return None


def simulate_order_plan(
    orders: List[Dict[str, Any]],
    shutdown_days: int = 7,
    horizon: int = HORIZON,
    recovery_mode: str = "agent",
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Unified ground-truth deterministic supply chain evaluation engine.

    Executes any order plan across the 21-day horizon under identical:
      - Synthetic network topology and node parameters
      - Deterministic daily demand profile (PROD-01: 45, PROD-02: 35)
      - Initial on-hand inventory (PROD-01: 100, PROD-02: 75)
      - Supplier shutdown enforcement (SUP-01 offline days 1..shutdown_days)
      - Daily shared supplier capacity limits (SUP-01: 100, SUP-02: 60)
      - Transport lead times (SUP-01: 2 days, SUP-02: 4 days)
      - Landed cost accounting (unit procurement cost + freight)
      - Sustained recovery criterion (3 consecutive days at or above 95% fill rate after disruption dip)
    """
    network = deepcopy(NETWORK)
    products = network["products"]
    products_by_id = {p["id"]: p for p in products}
    suppliers = {s["id"]: s for s in network["suppliers"]}

    inventory = {p["id"]: p["initial_inventory"] for p in products}
    daily_results = []
    violations = []

    # Filter and index orders by order_day, validating order day boundaries
    orders_by_day: Dict[int, List[Dict[str, Any]]] = {d: [] for d in range(1, horizon + 1)}
    for o in orders:
        day = o.get("order_day", None)
        if not isinstance(day, bool) and isinstance(day, int) and 1 <= day <= horizon:
            orders_by_day[day].append(o)
        else:
            violations.append({
                "day": day,
                "type": "invalid_order_day",
                "order": o,
            })

    pipeline: List[Dict[str, Any]] = []
    total_demand = 0
    total_fulfilled = 0
    total_backorders = 0
    total_landed_cost = 0.0

    # Group product fulfillment over the horizon
    product_totals = {
        p["id"]: {"demand": 0, "fulfilled": 0, "unmet": 0}
        for p in products
    }

    for day in range(1, horizon + 1):
        arrivals = []

        # 1. Receive pipeline arrivals for today
        arriving_now = [o for o in pipeline if o["arrival_day"] == day]
        pipeline = [o for o in pipeline if o["arrival_day"] != day]

        for order in arriving_now:
            inventory[order["product_id"]] += order["quantity"]
            arrivals.append({
                "supplier": order["supplier"],
                "product": order["product_id"],
                "quantity": order["quantity"],
            })

        # 2. Serve deterministic demand from available stock
        day_demand = 0
        day_fulfilled = 0
        day_backorders = 0
        product_day_data = {}

        for product in products:
            pid = product["id"]
            demand = product["daily_demand"]
            available = inventory[pid]
            fulfilled = min(available, demand)

            inventory[pid] -= fulfilled
            shortage = demand - fulfilled

            day_demand += demand
            day_fulfilled += fulfilled
            day_backorders += shortage

            product_totals[pid]["demand"] += demand
            product_totals[pid]["fulfilled"] += fulfilled
            product_totals[pid]["unmet"] += shortage

            product_day_data[pid] = {
                "demand": demand,
                "fulfilled": fulfilled,
                "unmet": shortage,
            }

        # 3. Process and validate replenishment orders placed on this day
        day_orders_placed = orders_by_day.get(day, [])
        proposals = []
        supplier_day_used = {sid: 0 for sid in suppliers}

        for order in day_orders_placed:
            sid = order.get("supplier")
            pid = order.get("product")
            qty = order.get("quantity", None)

            if sid not in suppliers:
                violations.append({
                    "day": day,
                    "type": "unknown_supplier",
                    "supplier": sid,
                    "order": order,
                })
                continue

            if pid not in products_by_id:
                violations.append({
                    "day": day,
                    "type": "unknown_product",
                    "product": pid,
                    "order": order,
                })
                continue

            # Quantity must strictly be a positive integer (reject 0, negative, float, bool, None)
            if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
                violations.append({
                    "day": day,
                    "type": "invalid_quantity",
                    "order": order,
                })
                continue

            supplier = suppliers[sid]

            # Validate explicit arrival_day if specified by caller
            expected_arrival = day + supplier["lead_time"]
            given_arrival = order.get("arrival_day")
            if given_arrival is not None and given_arrival != expected_arrival:
                violations.append({
                    "day": day,
                    "type": "arrival_mismatch",
                    "expected_arrival_day": expected_arrival,
                    "given_arrival_day": given_arrival,
                    "order": order,
                })
                proposals.append({
                    "product": pid,
                    "supplier": sid,
                    "quantity": 0,
                    "status": "rejected_arrival_mismatch",
                })
                continue

            # Constraint Check: Shutdown violation
            if sid == "SUP-01" and day <= shutdown_days:
                violations.append({
                    "day": day,
                    "type": "supplier_shutdown_violation",
                    "supplier": sid,
                    "quantity": qty,
                })
                proposals.append({
                    "product": pid,
                    "supplier": sid,
                    "quantity": 0,
                    "status": "rejected_supplier_shutdown",
                })
                continue

            # Check capacity: shared daily supplier limit
            if supplier_day_used[sid] + qty > supplier["capacity"]:
                violations.append({
                    "day": day,
                    "type": "supplier_capacity_exceeded",
                    "supplier": sid,
                    "attempted": qty,
                    "already_used": supplier_day_used[sid],
                    "capacity": supplier["capacity"],
                    "order": order,
                })
                proposals.append({
                    "product": pid,
                    "supplier": sid,
                    "quantity": 0,
                    "status": "rejected_capacity_exceeded",
                })
                continue

            supplier_day_used[sid] += qty
            arrival_day = expected_arrival
            order_cost = qty * (supplier["unit_cost"] + TRANSPORT_COST[sid])
            total_landed_cost += order_cost

            # Register in pipeline
            pipeline.append({
                "product_id": pid,
                "supplier": sid,
                "quantity": qty,
                "order_day": day,
                "arrival_day": arrival_day,
                "cost": round(order_cost, 2),
            })

            proposals.append({
                "product": pid,
                "supplier": sid,
                "quantity": qty,
                "arrival_day": arrival_day,
                "cost": round(order_cost, 2),
                "status": "ordered",
            })

        total_demand += day_demand
        total_fulfilled += day_fulfilled
        total_backorders += day_backorders

        daily_fill = (
            day_fulfilled / day_demand * 100
            if day_demand else 100.0
        )

        daily_results.append({
            "day": day,
            "demand": day_demand,
            "fulfilled": day_fulfilled,
            "backorders": day_backorders,
            "unmet_demand": day_backorders,
            "fill_rate": round(daily_fill, 2),
            "landed_cost": round(
                sum(p.get("cost", 0) for p in proposals), 2
            ),
            "arrivals": arrivals,
            "orders": proposals,
            "inventory": deepcopy(inventory),
            "outstanding_orders": len(pipeline),
            "products": product_day_data,
        })

    overall_fill = (
        total_fulfilled / total_demand * 100 if total_demand else 100.0
    )

    # Sustained recovery requires 3 consecutive days at or above TARGET_FILL_RATE
    # occurring after the first disruption dip
    recovery_day = calculate_recovery_day(daily_results, TARGET_FILL_RATE)

    # Add fill rate percentage for individual products
    for pid, pdata in product_totals.items():
        pdata["fill_rate"] = round(
            pdata["fulfilled"] / pdata["demand"] * 100
            if pdata["demand"] else 100.0,
            2,
        )

    return {
        "scenario": {
            "shutdown_days": shutdown_days,
            "recovery_mode": recovery_mode,
            "horizon_days": horizon,
            "seed": seed,
            "scenario_id": f"SCEN-SD{shutdown_days}-H{horizon}-S{seed}",
        },
        "metrics": {
            "total_demand": total_demand,
            "total_fulfilled": total_fulfilled,
            "total_backorders": total_backorders,
            "fill_rate": round(overall_fill, 2),
            "total_landed_cost": round(total_landed_cost, 2),
            "recovery_day": recovery_day,
            "ending_inventory": inventory,
            "outstanding_orders_at_horizon": len(pipeline),
            "constraint_violations": len(violations),
            "product_breakdown": product_totals,
        },
        "violations": violations,
        "daily_results": daily_results,
        "network": network,
        "assumptions": [
            "Deterministic daily demand (Component A: 45, Component B: 35) over a 21-day horizon",
            "Initial on-hand stock: Component A = 100 (2.2 days), Component B = 75 (2.1 days)",
            "Orders arrive strictly after supplier lead time (SUP-01: 2 days, SUP-02: 4 days)",
            "Supplier capacity is a shared daily limit across all products (SUP-01: 100, SUP-02: 60)",
            "Primary supplier SUP-01 accepts zero orders during days 1 to shutdown_days",
            "Unfilled daily demand is reported as unmet demand / backorder, not carried forward",
            "Landed cost accounts for unit procurement cost + freight on all placed orders",
            "Recovery requires three consecutive days at or above 95% fill rate after disruption shock",
            "Factory and distribution nodes are topology-modeled; echelons operate with unconstrained internal transfer",
            "Fully deterministic and reproducible evaluation without external stochastic variation",
        ],
    }


def run_simulation(
    shutdown_days: int = 7,
    recovery_mode: str = "agent",
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Entry point for strategy simulation.

    Generates the candidate order schedule for the chosen strategy and executes it
    through the unified deterministic supply chain evaluation engine.

    Modes:
      - 'reorder': Naive target-stock policy (primary supplier only; orders rejected during shutdown)
      - 'optimized': OR-Tools CP-SAT multi-period optimization with uniform shortage penalty
      - 'agent': Agent-coordinated optimization prioritizing critical component (Component A)
    """
    if not 1 <= shutdown_days <= 14:
        raise ValueError("shutdown_days must be between 1 and 14")

    if recovery_mode not in {"reorder", "optimized", "agent"}:
        raise ValueError(f"Invalid recovery_mode '{recovery_mode}'. Must be 'reorder', 'optimized', or 'agent'.")

    from baselines import reorder_rules_plan, optimization_only_plan, agent_assisted_plan

    start_time = time.perf_counter()

    if recovery_mode == "reorder":
        plan_meta = reorder_rules_plan(shutdown_days=shutdown_days, horizon=HORIZON)
    elif recovery_mode == "optimized":
        plan_meta = optimization_only_plan(shutdown_days=shutdown_days, horizon=HORIZON)
    else:
        plan_meta = agent_assisted_plan(shutdown_days=shutdown_days, horizon=HORIZON)

    planning_time = time.perf_counter() - start_time

    orders = plan_meta.get("orders", [])
    sim_result = simulate_order_plan(
        orders=orders,
        shutdown_days=shutdown_days,
        horizon=HORIZON,
        recovery_mode=recovery_mode,
        seed=seed,
    )

    # Attach planning execution runtime and strategy metadata
    sim_result["metrics"]["runtime_seconds"] = round(planning_time, 4)
    sim_result["strategy_info"] = {
        "id": recovery_mode,
        "name": plan_meta.get("name", recovery_mode),
        "description": plan_meta.get("description", ""),
        "planning_time_ms": round(planning_time * 1000, 2),
    }

    return sim_result
