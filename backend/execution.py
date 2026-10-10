"""
SupplyShield AI — Execution Boundary & Adapter Specification (Phase B6)

Defines the safe boundary between planner decision support and external execution.
SupplyShield AI is an advisory decision-support simulator:
- Does NOT dispatch real purchase orders.
- Does NOT integrate with live ERP systems.
- Does NOT contact live supplier APIs.
- Does NOT execute financial or payment transactions.
- Does NOT fabricate execution receipts or ERP identifiers.
"""

from typing import Protocol, Dict, Any
from schemas import ExecutionAdapterStatus


class ExecutionAdapter(Protocol):
    """Protocol for external procurement and ERP execution boundary."""

    def check_status(self) -> ExecutionAdapterStatus:
        """Returns the readiness and configuration status of the execution adapter."""
        ...

    def attempt_dispatch(self, plan: Any) -> Dict[str, Any]:
        """Attempts purchase order dispatch; raises RuntimeError when not configured."""
        ...


class NullExecutionAdapter:
    """
    Default safe execution adapter enforcing the non-execution boundary.
    Reports execution status as strictly NOT_CONFIGURED with external_execution=False.
    """

    def __init__(self) -> None:
        self.adapter_name = "NullExecutionAdapter"

    def check_status(self) -> ExecutionAdapterStatus:
        """Reports that external execution is not configured."""
        return ExecutionAdapterStatus(
            status="NOT_CONFIGURED",
            available=False,
            external_execution=False,
            adapter_name=self.adapter_name,
            notice=(
                "Real-world purchase order dispatch is not configured. "
                "SupplyShield AI is an advisory decision-support system."
            ),
        )

    def attempt_dispatch(self, plan: Any) -> Dict[str, Any]:
        """Refuses execution with explicit error; no orders are dispatched."""
        raise RuntimeError(
            "External execution is disabled: NullExecutionAdapter is active and no real-world ERP integration is configured."
        )


# Singleton instance
_default_adapter = NullExecutionAdapter()


def get_execution_adapter() -> NullExecutionAdapter:
    """Returns the configured execution adapter."""
    return _default_adapter
