"""
SupplyShield AI — Specialized Agents Package (Phase B3)

Exports:
  - demand_agent: Demand Intelligence Agent
  - inventory_agent: Inventory Intelligence Agent
  - supplier_risk_agent: Supplier Risk & Sourcing Agent
  - logistics_agent: Logistics Optimization Agent
  - build_scenario_context: Deterministic scenario context builder
"""

from .demand_intelligence import demand_agent
from .inventory_intelligence import inventory_agent
from .supplier_risk import supplier_risk_agent
from .logistics_optimization import logistics_agent
from .common import build_scenario_context

__all__ = [
    "demand_agent",
    "inventory_agent",
    "supplier_risk_agent",
    "logistics_agent",
    "build_scenario_context",
]
