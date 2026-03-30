---
id: TASK-007
title: Fix diagnostic error sensor native_value (BUG-003)
priority: P2
status: in-progress
depends_on: []
branch: task/TASK-007-bug003-error-sensor
iteration: 1
max_iterations: 5
created: 2026-03-30
---

## Description
`FluidraErrorSensor.native_value` returns "No Error" when `coordinator.error_information` is None
or empty, which is correct. But when there IS an error, the sensor state is just the raw error code
string (e.g. "E001") with no human-readable label in the main state. The HA history graph shows "E001"
with no context. Fix: return `"{code} — {description}"` as the native value so the state is self-describing.

## Acceptance Criteria
- [ ] `native_value` returns `"E001 — No water flow detected"` format when error exists
- [ ] `native_value` returns `"No Error"` when no error
- [ ] `extra_state_attributes` still contains all raw fields
- [ ] Sensor shows correct value in HA developer tools

## Implementation Notes
- File: `custom_components/fluidra_pool/sensor.py`, class `FluidraErrorSensor`
- `ERROR_CODES` map is in `const.py` — use it for the human-readable description
- Current: `return str(error_code)` → change to include description from ERROR_CODES dict

## Execution Log
| Iteration | Outcome | New Tasks Generated | Notes |
|-----------|---------|---------------------|-------|
| 1 | implementing | — | simple one-line fix |

## Output Artifacts
- Modified `custom_components/fluidra_pool/sensor.py`
