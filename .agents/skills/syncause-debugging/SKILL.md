---
name: syncause-debugging
description: Evidence-based debugging skill inspired by Syncause. Enforces capturing runtime facts (reproduction logs, stack traces, variable state, test assertions) before proposing code edits to eliminate speculative patching.
---

# Syncause Evidence-Based Debugging

This skill enforces a rigorous, evidence-first troubleshooting methodology to prevent "patch-and-pray" cycles when fixing bugs.

## 1. Core Rule: No Fix Without Evidence

Never propose code changes based on intuition alone. Every bug resolution must proceed through four sequential phases:

```
[1. Reproduce] ──► [2. Collect Runtime Facts] ──► [3. Isolate Root Cause] ──► [4. Minimal Patch & Verify]
```

## 2. The Four Debugging Steps

### Step 1: Deterministic Reproduction
- Formulate the exact command, API query, or test case that triggers the defect.
- Confirm whether the error occurs consistently or intermittently.
- Example: `GET /api/simulate?mode=reorder&shutdown_days=7` returning unexpected default mode.

### Step 2: Runtime Fact Collection
- Capture actual stdout/stderr, stack traces, exit codes, and network payloads.
- Inspect argument handling and query parameter routing.
- Check environment variables and process states.

### Step 3: Root Cause Isolation
- Formulate a testable hypothesis explaining the observed failure.
- Verify against active source code lines (never assume ground truth without viewing the file).
- Differentiate between symptom (e.g. `recovery_day = 1`) and true underlying cause (e.g. window scan triggered before disruption impact).

### Step 4: Minimal Patch & Verification
- Apply the smallest coherent edit that directly resolves the root cause.
- Run automated tests (unit tests, compilation checks, linter).
- Confirm that existing functionality and adjacent modules remain intact.
