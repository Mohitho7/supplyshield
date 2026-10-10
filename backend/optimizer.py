
from ortools.sat.python import cp_model

from simulator import (
    NETWORK,
    TRANSPORT_COST,
    HORIZON,
    TARGET_FILL_RATE,
    calculate_recovery_day,
)


def optimize_plan(
    shutdown_days: int = 7,
    priority_weighted: bool = False,
    product_weights: Optional[Dict[str, int]] = None,
    network: Optional[Dict[str, Any]] = None,
):
    """
    Optimize sourcing over the same deterministic demand horizon.

    Objective:
      Minimize purchasing/transport costs, inventory holding costs,
      and heavily penalized unmet demand. When priority_weighted is True (agent-assisted mode),
      Priority 1 products carry double penalty to protect critical service level under scarce capacity.
      Explicit product_weights from Demand Agent handoff are consumed directly when provided.

    Constraints:
      - Initial inventory is respected.
      - Supplier daily capacity is shared across products.
      - Primary supplier cannot ship during the shutdown.
      - Orders arrive only after their lead time.
      - Inventory cannot become negative.
      - Orders arriving beyond the horizon are excluded.

    This model optimizes supplier-to-product replenishment.
    It does not yet optimize factory/DC transportation flows.
    """
    if not 1 <= shutdown_days <= 14:
        raise ValueError("shutdown_days must be between 1 and 14")

    model = cp_model.CpModel()
    products = network["products"] if network and "products" in network else NETWORK["products"]
    suppliers = network["suppliers"] if network and "suppliers" in network else NETWORK["suppliers"]
    supplier_by_id = {s["id"]: s for s in suppliers}

    # Integer quantities keep the model suitable for CP-SAT.
    order = {}
    fulfilled = {}
    inventory = {}

    for p in products:
        pid = p["id"]

        for day in range(1, HORIZON + 1):
            fulfilled[pid, day] = model.new_int_var(
                0, p["daily_demand"], f"fulfilled_{pid}_{day}"
            )
            inventory[pid, day] = model.new_int_var(
                0, 10000, f"inventory_{pid}_{day}"
            )

        for s in suppliers:
            sid = s["id"]

            for day in range(1, HORIZON + 1):
                # Orders arriving beyond the horizon cannot help this plan.
                arrival_day = day + s["lead_time"]
                allowed = arrival_day <= HORIZON

                # Primary supplier is unavailable during the shutdown.
                if sid == "SUP-01" and day <= shutdown_days:
                    allowed = False

                upper = s["capacity"] if allowed else 0

                order[pid, sid, day] = model.new_int_var(
                    0, upper, f"order_{pid}_{sid}_{day}"
                )

    # Shared daily supplier capacity across all products.
    for s in suppliers:
        sid = s["id"]
        for day in range(1, HORIZON + 1):
            model.add(
                sum(
                    order[p["id"], sid, day]
                    for p in products
                ) <= s["capacity"]
            )

    # Inventory balance and demand fulfillment.
    for p in products:
        pid = p["id"]
        previous_inventory = p["initial_inventory"]

        for day in range(1, HORIZON + 1):
            arrivals = []

            for s in suppliers:
                sid = s["id"]
                arrival_order_day = day - s["lead_time"]

                if arrival_order_day >= 1:
                    arrivals.append(
                        order[pid, sid, arrival_order_day]
                    )

            model.add(
                inventory[pid, day]
                == previous_inventory
                + sum(arrivals)
                - fulfilled[pid, day]
            )

            previous_inventory = inventory[pid, day]

    # Minimize total cost. Costs are scaled by 10 for integer arithmetic.
    objective_terms = []
    base_shortage_penalty = 10000  # Scaled cost units per unmet unit.

    for p in products:
        pid = p["id"]
        # In agent-assisted mode, Priority 1 products carry double penalty to protect critical service.
        # When product_weights are explicitly passed from Demand Agent handoff, consume those weights.
        if product_weights is not None and pid in product_weights:
            weight = product_weights[pid]
        else:
            weight = 2 if (priority_weighted and p.get("priority", 2) == 1) else 1
        shortage_penalty = base_shortage_penalty * weight

        for day in range(1, HORIZON + 1):
            demand = p["daily_demand"]
            unmet = demand - fulfilled[pid, day]

            objective_terms.append(shortage_penalty * unmet)

            # Small holding cost discourages unnecessary excess inventory.
            objective_terms.append(2 * inventory[pid, day])

        for s in suppliers:
            sid = s["id"]
            unit_cost = (
                s["unit_cost"] + TRANSPORT_COST[sid]
            )
            scaled_cost = round(unit_cost * 10)

            for day in range(1, HORIZON + 1):
                objective_terms.append(
                    scaled_cost * order[pid, sid, day]
                )

    model.minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 4

    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": solver.status_name(status),
            "scenario": {
                "shutdown_days": shutdown_days,
                "horizon_days": HORIZON,
                "priority_weighted": priority_weighted,
                "disrupted_supplier_id": "SUP-01",
                "seed": 42,
                "scenario_id": f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
            },
            "message": f"Solver terminated with status {solver.status_name(status)}. No feasible plan found within solver limits.",
            "orders": [],
            "daily_results": [],
            "limitations": [
                "Solver terminated without an optimal or feasible replenishment plan",
                "Synthetic deterministic demand",
                "Supplier-to-product sourcing only",
            ],
            "metrics": None,
        }

    plan = []
    total_ordered = 0
    total_fulfilled = 0
    total_demand = 0
    total_purchase_cost = 0.0
    daily_results = []

    for day in range(1, HORIZON + 1):
        day_orders = []

        for p in products:
            pid = p["id"]

            for s in suppliers:
                sid = s["id"]
                qty = solver.value(order[pid, sid, day])

                if qty > 0:
                    arrival_day = day + s["lead_time"]
                    cost = qty * (
                        s["unit_cost"] + TRANSPORT_COST[sid]
                    )

                    entry = {
                        "order_day": day,
                        "arrival_day": arrival_day,
                        "product": pid,
                        "supplier": sid,
                        "quantity": qty,
                        "cost": round(cost, 2),
                    }
                    plan.append(entry)
                    day_orders.append(entry)
                    total_ordered += qty
                    total_purchase_cost += cost

        # Arrivals on this day from earlier orders
        day_arrivals = []
        for p in products:
            for s in suppliers:
                arrival_order_day = day - s["lead_time"]
                if arrival_order_day >= 1:
                    arr_qty = solver.value(order[p["id"], s["id"], arrival_order_day])
                    if arr_qty > 0:
                        day_arrivals.append({
                            "supplier": s["id"],
                            "product": p["id"],
                            "quantity": arr_qty,
                        })

        day_fulfilled = sum(
            solver.value(fulfilled[p["id"], day])
            for p in products
        )
        day_demand = sum(p["daily_demand"] for p in products)
        day_inventory = {
            p["id"]: solver.value(inventory[p["id"], day])
            for p in products
        }
        product_fulfillment = {
            p["id"]: {
                "demand": p["daily_demand"],
                "fulfilled": solver.value(fulfilled[p["id"], day]),
                "unmet": p["daily_demand"] - solver.value(fulfilled[p["id"], day]),
            }
            for p in products
        }

        total_fulfilled += day_fulfilled
        total_demand += day_demand

        daily_fill = (
            day_fulfilled / day_demand * 100
            if day_demand else 100.0
        )

        day_outstanding = sum(
            1 for o in plan if o["order_day"] <= day and o["arrival_day"] > day
        )
        day_landed_cost = round(sum(o.get("cost", 0) for o in day_orders), 2)
        shortage = day_demand - day_fulfilled

        daily_results.append({
            "day": day,
            "demand": day_demand,
            "fulfilled": day_fulfilled,
            "backorders": shortage,
            "unmet_demand": shortage,
            "fill_rate": round(daily_fill, 2),
            "landed_cost": day_landed_cost,
            "arrivals": day_arrivals,
            "orders": day_orders,
            "inventory": day_inventory,
            "outstanding_orders": day_outstanding,
            "products": product_fulfillment,
        })

    # Recovery requires 3 consecutive days at or above target service after the disruption dip
    recovery_day = calculate_recovery_day(daily_results, TARGET_FILL_RATE)

    # Calculate cumulative product breakdown
    product_totals = {
        p["id"]: {
            "demand": sum(daily_results[d - 1]["products"][p["id"]]["demand"] for d in range(1, HORIZON + 1)),
            "fulfilled": sum(daily_results[d - 1]["products"][p["id"]]["fulfilled"] for d in range(1, HORIZON + 1)),
            "unmet": sum(daily_results[d - 1]["products"][p["id"]]["unmet"] for d in range(1, HORIZON + 1)),
        }
        for p in products
    }
    for pid, pdata in product_totals.items():
        pdata["fill_rate"] = round(
            pdata["fulfilled"] / pdata["demand"] * 100 if pdata["demand"] else 100.0,
            2,
        )

    return {
        "status": solver.status_name(status),
        "scenario": {
            "shutdown_days": shutdown_days,
            "horizon_days": HORIZON,
            "priority_weighted": priority_weighted,
            "disrupted_supplier_id": "SUP-01",
            "seed": 42,
            "scenario_id": f"SCEN-SD{shutdown_days}-H{HORIZON}-S42",
        },
        "metrics": {
            "total_demand": total_demand,
            "total_fulfilled": total_fulfilled,
            "total_backorders": total_demand - total_fulfilled,
            "fill_rate": round(
                total_fulfilled / total_demand * 100, 2
            ),
            "total_purchase_and_transport_cost": round(
                total_purchase_cost, 2
            ),
            "total_landed_cost": round(
                total_purchase_cost, 2
            ),
            "recovery_day": recovery_day,
            "ending_inventory": daily_results[-1]["inventory"],
            "outstanding_orders_at_horizon": daily_results[-1]["outstanding_orders"],
            "product_breakdown": product_totals,
            "objective_value_scaled": solver.objective_value,
            "solver_time_seconds": round(solver.wall_time, 4),
        },
        "orders": plan,
        "daily_results": daily_results,
        "limitations": [
            "Synthetic deterministic demand",
            "Supplier-to-product sourcing only",
            "Factory and distribution-center flow constraints are not modeled",
            "No uncertainty or stochastic demand",
            "Cost and shortage penalty assumptions require calibration",
        ],
    }

