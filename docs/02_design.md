# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `MFGPLComplianceAgent`
- **L1 Base**: `AgentBaseGraph` (L1 direct); `VectorRAGAgent` pattern reference only
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

Cat 2 — outer `AgentBaseGraph` + `GraphNode` (`main` slot) wrapping an inner `BaseGraph`
(`PLComplianceWorkflowGraph`). See scaffold issue #408 (`[DRAFT-393] MFG-C2-066`) Engineer
Review §4 for the source-of-truth workflow.

### Node Configuration (outer)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | schema_version, session_id, trust_level | - | - | InitializeNode (default) |
| pre_process | `QueryNormalizeNode` — sanitize; enum-validate `defect_type_hint`; classify intent | `user_input`, `defect_type_hint`, `jurisdiction` | `intent_type`, `jurisdiction`, `validated_input` | FunctionNode |
| main | `PLComplianceGraphNode` — dispatches to inner subgraph | `validated_input` | `defect_type`, `kb_sub_index`, `pl_reg_passages`, `eu_pld_crossref`, `kb_source_ref`, `law_citation`, `required_action_steps` | GraphNode |
| post_process | `ResponseValidateNode` — non-suppressible 弁護士 referral; S-5 recall-burst rate limit; S-4 audit | `law_citation`, `required_action_steps` | `formatted_output`, `liability_framing_note`, `legal_advisor_referral_notice` | FunctionNode |
| finalize | response_metadata, total_time_ms | - | - | FinalizeNode (default) |

### Node Configuration (inner — `PLComplianceWorkflowGraph`)

| Inner node | Responsibility | Output |
|---|---|---|
| `defect_type_classify` | Classify defect type (design/manufacturing/instruction/ambiguous) → KB sub-index | `defect_type`, `kb_sub_index` |
| `pl_reg_kb_retrieve` | Retrieve 製造物責任法/METI/消費者庁 (+ opt EU PLD 2024) passages, namespace `japan_pl_law` | `pl_reg_passages`, `eu_pld_crossref`, `kb_source_ref` |
| `action_guide_generate` | Generate recall/notification action steps + 製造物責任法 citation; generic-only framing | `law_citation`, `required_action_steps` |

### Data Flow

```
START → initialize → pre_process(QueryNormalize) → main(GraphNode) → post_process(ResponseValidate) → finalize → END
                                                          │
                                                          ▼ inner subgraph
                                        defect_type_classify → pl_reg_kb_retrieve → action_guide_generate
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `defect_type_hint` | `NotRequired[str]` | Caller-supplied raw defect type hint (enum-validated) | No |
| `jurisdiction` | `NotRequired[str]` | `"jp"` \| `"jp_eu_cross"` | No |
| `intent_type` | `NotRequired[str]` | `"pl_compliance"` \| `"recall_procedure"` | No |
| `defect_type` | `NotRequired[str]` | Classified defect type | No |
| `kb_sub_index` | `NotRequired[str]` | Legal-standard KB sub-index | No |
| `pl_reg_passages` | `NotRequired[str]` | JSON list of retrieved passages | No |
| `law_citation` | `NotRequired[str]` | 製造物責任法 article citation | No |
| `required_action_steps` | `NotRequired[str]` | JSON list of action steps | No |
| `eu_pld_crossref` | `NotRequired[str]` | JSON dict\|null — EU PLD 2024 cross-reference | No |
| `liability_framing_note` | `NotRequired[str]` | Generic-only liability framing note | No |
| `legal_advisor_referral_notice` | `NotRequired[str]` | Non-suppressible 弁護士 referral notice | No |
| `kb_source_ref` | `NotRequired[str]` | JSON list of cited KB source ref_ids | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types); every agent-specific field wrapped `NotRequired[...]`
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [ ] ConnectionPolicy (retry/timeout strategy)
- [ ] SecurityViolationError
- [x] S-2: `_extra_security_gate_input()` — not needed beyond default PII scan (QueryNormalizeNode's
      defect_type enum validation is business-logic input validation inside `execute()`, not a security gate hook)
- [x] S-3: `_extra_security_gate_output()` — `ResponseValidateNode` non-suppressible re-check: the 弁護士
      referral notice must be present in every answer, and the answer must never quantify liability for a
      specific incident (preservation variant, per the framework's non-suppressible-output security rule)
- [x] S-4: `emit_trace_event()` — every node emits ≥1 domain event inside `execute()`
      (`query_normalized`, `defect_type_classified`, `pl_reg_kb_retrieved`, `action_guide_generated`,
      `pl_compliance_query_answered`; GraphNode wrapper emits `pl_compliance_workflow_dispatched`/`_completed`
      inside `extract_input()`/`merge_output()`)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass → framework `@final` gate always runs automatically;
>   extend via `_extra_security_gate_input()` / `_extra_security_gate_output()` only
> - `GraphNode` / `RemoteAgentNode` → deliberate no-op (upstream or remote node's gate already applied)
> - Custom `BaseNode` subclass → must implement `_security_gate_input()` and
>   `_security_gate_output()` directly (`@abstractmethod` — omission raises `TypeError` at instantiation)

### Composition Pattern

- **Pattern**: GraphNode (subgraph) — outer `AgentBaseGraph` `main` slot wraps inner `BaseGraph`
  (`PLComplianceWorkflowGraph`)
- **Composition target**: `src/graph/domain_workflow_graph.py` (`PLComplianceWorkflowGraph`)
- **Error propagation strategy**: propagate (fail fast; `error_strategy: ClassVar[str] = "propagate"`)

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## LLM Degrade Policy (`action_guide_generate`)

**Node responsibility.** `ActionGuideGenerateNode` synthesizes the recall/notification action
guide + 製造物責任法 citation. An LLM materially improves this over the deterministic
keyword-templated fallback, but is not required for the node to produce a valid, compliant
answer — `generate_action_guide(defect_type, passages, llm=None)` already produces a complete
generic-only action guide from the retrieved KB passages alone.

**Wiring.** `generation_mode: "llm"` (`config/agent.yaml`). The constructor `llm=` parameter is
a **test-double seam only** — production wiring (`register_nodes()`) never passes a real client.
On each invocation, `_resolve_llm()` builds a fresh `AzureOpenAIClient` from three secrets
(`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`) resolved via
`ctx.secrets.require(...)`; the client is never cached on `self` (node instances are reused
across callers via the registry's LRU cache — caching a client built from one caller's secrets
would leak it to the next caller).

**Error handling — graceful degrade, not fail-closed.** Any problem building or calling the LLM
(missing secret, malformed endpoint, API error, empty/unusable response) falls back to
`generate_action_guide(..., llm=None)` instead of failing the request — an LLM outage is not a
pipeline failure. This differs from `docs/07_operation_guide.md`'s HITL/mandatory-LLM templates:
here `status=error` is reserved for genuine input/content problems (missing `defect_type`, an
S-3 incident-quantification violation), never for LLM unavailability.

**Security.** The three secrets are never logged (S-4 audit events carry only
`defect_type`/`step_count`, never LLM prompt/response content); `AZURE_OPENAI_API_KEY` never
reaches state or the JSON response; the S-3 generic-only re-check (`has_incident_specific_
quantification`) runs on the LLM's output exactly the same as on the deterministic fallback, so
an LLM cannot bypass the non-suppressible legal-liability control.

**Not declared under `requires.secrets`.** `AZURE_OPENAI_API_KEY`/`_ENDPOINT`/`_DEPLOYMENT` are
deliberately **excluded** from `config/agent.yaml`'s `requires.secrets` list — that field is
enforced via `require_at_compile()` (hard-fail if absent), which would contradict this node's
graceful-degrade contract and prevent the agent from compiling key-less at all (the same
precedent as `ANTHROPIC_API_KEY` in the scaffold's own reference `agent.yaml`).
`requires.extras: ["openai"]` is still declared (needed for `AgentRegistry`'s extras validation).

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed 5-node compliance-Q&A pipeline, no autonomous loop needed |
| Composition pattern | Flat (Cat 1 style) | GraphNode + inner subgraph | **GraphNode + inner subgraph** | Cat 2 requires 3-layer composition (`gate-composition`); 5 conceptual steps map to outer pre/post + 3 inner nodes |
| Rate limiting (S-5) | Config-only | Injected `RecallBurstRateLimiter` dep | **Injected dep** | Deterministic in-memory limiter as an immutable node constructor dependency (like an LLM client) |
| Action-guide LLM (2026-09-18 reintegration) | Mandatory LLM, fail-closed | LLM-optional with deterministic fallback | **LLM-optional, graceful degrade** | The KB-grounded deterministic path already produces a complete, compliant action guide; nothing about this template's core capability requires an LLM |
