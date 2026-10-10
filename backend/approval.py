"""
SupplyShield AI — Demo Planner Approval Ledger & Governance (Phase B6)

Manages the explicit human-in-the-loop approval workflow for recovery candidates:
1. Validates candidate feasibility and cryptographic plan fingerprint.
2. Persists decisions to an append-only JSONL ledger.
3. Re-evaluates candidate before granting or reading approval to prevent stale authorizations.
4. Distinguishes demo decision-support approval from real-world ERP execution.

Persistence Disclosures:
- Demo ledger uses a local append-only JSONL file.
- Designed strictly for demonstration and evaluation tracing.
- Does not provide enterprise identity federation, hardware signing, or non-repudiation.
- In ephemeral or containerized filesystems, data is non-durable without persistent volume mounting.
"""

import json
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from schemas import ApprovalRequest, ApprovalRecord

logger = logging.getLogger("supplyshield.approval")

# Environment configuration
ENV_APPROVALS_ENABLED = "SUPPLYSHIELD_DEMO_APPROVALS_ENABLED"
ENV_LEDGER_PATH = "SUPPLYSHIELD_APPROVAL_LEDGER_PATH"


def is_approval_enabled() -> bool:
    """Returns True if the demo approval workflow is enabled in configuration."""
    val = os.environ.get(ENV_APPROVALS_ENABLED, "true").strip().lower()
    return val in ("true", "1", "yes", "on")


def get_ledger_path() -> Path:
    """Returns the resolved Path to the append-only approval ledger file."""
    configured = os.environ.get(ENV_LEDGER_PATH)
    if configured:
        return Path(configured)
    # Default to data/approval_ledger.jsonl in backend directory
    base_dir = Path(__file__).resolve().parent
    return base_dir / "data" / "approval_ledger.jsonl"


def read_approval_records() -> List[Dict[str, Any]]:
    """
    Reads all approval records from the append-only JSONL ledger.
    Handles missing files or malformed entries safely without crashing.
    """
    path = get_ledger_path()
    if not path.exists():
        return []

    records: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean = line.strip()
                if not clean:
                    continue
                try:
                    record = json.loads(clean)
                    if isinstance(record, dict) and "record_id" in record:
                        records.append(record)
                except json.JSONDecodeError as err:
                    logger.warning(
                        f"Skipping malformed ledger line {line_no} in {path.name}: {err}"
                    )
    except Exception as e:
        logger.error(f"Failed to read approval ledger at {path.name}: {e}")
        return []

    return records


def get_approval_records_count() -> int:
    """Returns the total number of valid records in the ledger."""
    return len(read_approval_records())


def get_latest_approval(scenario_id: str, candidate_id: str) -> Optional[ApprovalRecord]:
    """
    Retrieves the most recent approval record matching the scenario and candidate,
    or None if no record exists.
    """
    records = read_approval_records()
    matched = [
        r for r in records
        if r.get("scenario_id") == scenario_id and r.get("candidate_id") == candidate_id
    ]
    if not matched:
        return None
    latest_raw = matched[-1]
    try:
        return ApprovalRecord(**latest_raw)
    except Exception as e:
        logger.warning(f"Failed to parse approval record {latest_raw.get('record_id')}: {e}")
        return None


def record_approval(
    request: ApprovalRequest,
) -> Tuple[Optional[ApprovalRecord], Optional[str], int]:
    """
    Explicit server-side evaluation and recording of a planner decision:
    1. Validates demo approval mode is enabled.
    2. Re-evaluates the candidate from the deterministic engine to verify existence and feasibility.
    3. Verifies that the submitted plan_fingerprint matches the actual candidate plan fingerprint.
    4. Prohibits approval of infeasible plans (e.g. baseline reorder benchmark).
    5. Deduplicates identical repeated requests (idempotency).
    6. Appends the new ApprovalRecord to the JSONL ledger.

    Returns: (record, error_message, http_status_code)
    """
    if not is_approval_enabled():
        return (
            None,
            "Demo approval workflow is disabled (SUPPLYSHIELD_DEMO_APPROVALS_ENABLED=false).",
            403,
        )

    # 1. Parse scenario shutdown duration
    # Expected format: SCEN-SD{d}-H21-S42 or similar
    match = re.search(r"SD(\d+)", request.scenario_id)
    if not match:
        return (
            None,
            f"Invalid scenario identifier format: '{request.scenario_id}'. Expected 'SCEN-SD{{days}}-...'",
            422,
        )

    shutdown_days = int(match.group(1))
    if not (1 <= shutdown_days <= 14):
        return (
            None,
            f"Shutdown duration {shutdown_days} out of bounds (must be 1 to 14 days).",
            422,
        )

    # 2. Re-evaluate scenario to verify plan truthfulness independently
    try:
        from coordinator import coordinate_recovery
        recovery_result = coordinate_recovery(shutdown_days=shutdown_days)
    except Exception as e:
        logger.error(f"Failed to re-evaluate scenario {request.scenario_id}: {e}")
        return None, "Internal error evaluating scenario for approval.", 500

    candidates = recovery_result.get("candidates") or []
    candidate = next((c for c in candidates if c.get("candidate_id") == request.candidate_id), None)

    if not candidate:
        return (
            None,
            f"Candidate '{request.candidate_id}' not found in scenario '{request.scenario_id}'.",
            404,
        )

    # 3. Check feasibility if action is APPROVE
    if request.action == "APPROVE":
        is_valid = candidate.get("validation", {}).get("valid", False)
        violation_count = candidate.get("validation", {}).get("violation_count", 0)
        if not is_valid:
            return (
                None,
                f"Cannot approve candidate '{request.candidate_id}': plan failed feasibility validation with {violation_count} violation(s). Infeasible benchmarks cannot be approved.",
                400,
            )

    # 4. Check plan fingerprint integrity
    actual_fingerprint = candidate.get("plan_fingerprint")
    if not actual_fingerprint or actual_fingerprint != request.plan_fingerprint:
        return (
            None,
            f"Plan fingerprint mismatch: submitted fingerprint does not match the current deterministic plan fingerprint for candidate '{request.candidate_id}'.",
            409,
        )

    # 5. Check idempotency: if the latest record matches exactly, return it without duplicating
    latest = get_latest_approval(request.scenario_id, request.candidate_id)
    if (
        latest
        and latest.action == request.action
        and latest.plan_fingerprint == request.plan_fingerprint
        and latest.reviewer_label == (request.reviewer_label or "Supply Planner")
        and latest.comment == request.comment
    ):
        return latest, None, 200

    # 6. Construct new approval record
    record_id = f"APPR-REC-{uuid.uuid4().hex[:12].upper()}"
    rec_dict = {
        "record_id": record_id,
        "scenario_id": request.scenario_id,
        "candidate_id": request.candidate_id,
        "strategy_id": candidate.get("strategy_id", "unknown"),
        "plan_fingerprint": request.plan_fingerprint,
        "action": request.action,
        "workflow_state": "APPROVED" if request.action == "APPROVE" else "REJECTED",
        "reviewer_label": request.reviewer_label or "Supply Planner",
        "comment": request.comment,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "demo_mode": True,
        "environment": "demo_decision_support",
        "execution_status": "NOT_CONFIGURED",
        "external_execution": False,
        "notice": "Demo-only approval record. No live purchase orders or ERP transactions are dispatched.",
    }

    try:
        record = ApprovalRecord(**rec_dict)
    except Exception as e:
        logger.error(f"Failed to create ApprovalRecord model: {e}")
        return None, "Error serializing approval record.", 500

    # 7. Safe append to JSONL ledger
    path = get_ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), separators=(",", ":")) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to approval ledger at {path}: {e}")
        return None, "Failed to persist approval record to local ledger storage.", 500

    logger.info(
        f"Approval decision recorded: record_id={record_id} action={request.action} "
        f"scenario={request.scenario_id} candidate={request.candidate_id}"
    )
    return record, None, 201
