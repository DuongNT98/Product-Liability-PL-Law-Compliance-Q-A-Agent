# Test Specification

## Test Strategy
- Coverage target: every node ≥1 unit success + ≥1 error/edge; full graph ≥1 integration compile+invoke
- Test types: Unit / Integration / Proof-of-Boundary

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | Fail-closed on invalid input (empty query, missing envelope fields) | Error state, no raise | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via configurable only | Direct access raises error | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | PASS |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | PASS |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden | PASS |
| TC-08 | `required_trust_level` enforced | Insufficient trust → refused | PASS |
| TC-09 | S-2: defect_type enum validation (business-logic, not a gate hook) | Free-form defect text rejected | PASS |
| TC-10 | S-3: `_extra_security_gate_output()` non-suppressible referral + generic-only check | Missing referral notice / incident quantification → blocked | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path | PASS |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | L1 → External service (KB) | KB retrieval via injected `kb` dependency | Deterministic passages | PASS |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified for every `src/nodes/` node | PASS |
| PB-7 | HITL interrupt propagation | `hitl.enabled` absent → auto-skip | N/A (no HITL in this template) | SKIP (N/A) |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Defect-type classification routes to correct KB sub-index | "This has a design flaw" | `defect_type=design`, `kb_sub_index=japan_pl_law.design_defect` | PASS |
| BL-02 | Non-suppressible 弁護士 referral notice always present | Any valid PL query | `formatted_output` contains `REFERRAL_NOTICE` | PASS |
| BL-03 | Generic-only framing rejects incident-specific liability quantification | Action guide text quantifying "your liability is..." | S-3 re-check blocks output | PASS |
| BL-04 | Recall-burst rate limit (S-5) | >20 requests/min from same caller | Subsequent requests → ERROR | PASS (unit-level via `RecallBurstRateLimiter`) |
| BL-05 | Action-guide LLM override generates from a well-formed response | Injected fake LLM returns real prose | `law_citation`/`required_action_steps` reflect the LLM response, not the deterministic template | PASS |
| BL-06 | Action-guide LLM prose/markdown-wrapped response accepted as-is | Injected fake LLM returns a fenced-code-block response | `status=success` (free-text output, no JSON parsing required) | PASS |
| BL-07 | Action-guide LLM empty response degrades to deterministic | Injected fake LLM returns `{"content": ""}` | `status=success` with the deterministic `law_citation`, no error surfaced | PASS |
| BL-08 | Action-guide LLM raising degrades to deterministic | Injected fake LLM raises on `.complete()` | `status=success` with the deterministic `law_citation`, no error surfaced | PASS |
| BL-09 | No LLM injected, no secret bound (real production shape) | No constructor override, no bound `InvocationContext` secrets | `_resolve_llm()` returns `None`; deterministic path runs | PASS |
| BL-10 | Missing `defect_type` never invokes the LLM | Injected fake LLM configured to raise if called; state has no `defect_type` | `status=error`, LLM `.complete()` never called | PASS |

## Test Execution Summary
- Execution date: 2026-07-12 (LLM degrade-policy tests added 2026-09-18)
- Total tests: unit (nodes + framework compliance) + integration + proof_of_boundary
- Pass: all / Fail: 0 / Skip: PB-7 (N/A, no HITL)
- Coverage: all 5 nodes + outer/inner graph composition covered; action-guide LLM
  wiring covered end-to-end with a test-double (no real Azure OpenAI call in the suite)
