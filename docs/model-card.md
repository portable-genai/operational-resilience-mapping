# Model card: Operational Resilience Studio (Rgc9)

This is a STARTER model card. It records the model boundary as built and the controls that must be
completed before a managed deployment. The deterministic engines are the system of record; the
model is a bounded, replaceable component that writes one paragraph of prose.

The most important fact on this page is that **no model call happens in any profile today.** The
generation seam is fully wired (a port, three adapters, a schema, a groundedness check and a
deterministic fallback), and the managed adapter is a placeholder that raises rather than a Gemini
call. Read the sections below as a description of the boundary a managed narrator will be dropped
into, not as a description of a model that is running.

## What the model does, and does not do

- **Would do**: write a short justification narrative for impact tolerances the engine has ALREADY
  derived. It receives a system instruction plus a prompt built from engine-owned figures in
  `StudioService._narrate_tolerances`, pinned to a one-key JSON schema
  (`domain/narrative.NARRATIVE_SCHEMA`, `build_request`).
- **Does NOT**: produce any tolerance value, chain criticality, scenario outcome, concentration
  finding, severity band or escalation decision. Tolerances come from `ToleranceEngine` over the
  data-carried `TOLERANCE_PACKS`; the stay-within-tolerance verdict comes from `ScenarioEngine`;
  the map integrity gaps come from `MapService`; the concentration findings come from
  `ConcentrationService`; the review band comes from `ResilienceReviewPolicy`. All of it is pure
  stdlib in `domain/`, and `tests/unit/test_tolerance_engine.py`,
  `tests/unit/test_scenario_engine.py`, `tests/unit/test_map_service.py` and
  `tests/unit/test_concentration_exit_parity.py` pin the arithmetic.
- **Does NOT mutate the graph either.** In a managed deployment the generation port is also meant
  to propose candidate dependency edges from extracted document text; `IngestionService`
  deterministically reconciles those candidates against the known nodes and turns an ungroundable
  candidate into a named gap rather than a silent edge (`tests/unit/test_ingestion_service.py`).
  Offline, the proposer in `StudioService._propose_edges` is deterministic code, so the gate is
  reproducible.

## Boundary and validation

- The model is reachable through exactly one port, `ports/generation.py`. There is no second model
  seam in the repo.
- The reply is held to two hard rules before it is allowed out (`domain/narrative.py`):
  **schema validation**, so `parse_narrative` returns an empty string for anything that is not a
  JSON object with a string `narrative` key, rather than repairing it; and **groundedness**, so
  `numbers_are_grounded` rejects a narrative containing any figure the engine did not produce.
- When a narrative is discarded, the deterministic prose stands in: `_narrate_tolerances` returns
  `"Proposed tolerances: ..."` built purely from the engine values, so a surface always has a
  grounded sentence and never a hallucinated one.
- The generation call is wrapped, so a narrator that raises degrades to the same deterministic
  prose rather than failing a proposal. This is why the unwired managed adapter does not crash the
  pipeline, and it is also why an unwired narrator is invisible from the outside: see the remaining
  controls below.
- The regulatory grounding behaves the same way. `StudioService._requirements` catches a
  compliance-source failure and returns an answer that carries no citations and sets
  `requires_human_review`, so an ungrounded finding is escalated rather than quietly asserted.
- Personal data is masked before the audit write and before an outbound review payload
  (`domain/pii.py`, `adapters/_review_payload.py`), and `agent/tools.py` masks a tool result before
  it can enter a model's context.
- Every consequential result sets `requires_human_review` and is routed to Hrz7 (rule R8) in the
  same call; nothing auto-executes. `tests/unit/test_review_routing.py` asserts the routing rather
  than the flag.

## Adapters and profiles

| Profile | Generation adapter | Behaviour |
|---|---|---|
| `local` | `adapters/local/generation.py` | Deterministic stub: returns the narration schema's JSON with one fixed prose string that carries NO figures, so every engine number is identical run to run and the groundedness check passes trivially. SDK-free, no network. |
| `gcp` | `adapters/gcp/generation.py` | **Not wired.** It performs the lazy `from google import genai` and then raises `NotImplementedError("Gemini narration is wired at deploy time")`. No model id is pinned, no request is sent, and no token is spent. |
| `onprem` | `adapters/onprem/generation.py` | Fail-fast placeholder: refuses at call time rather than pretending to narrate, so a placeholder never becomes a silent no-op on the one path where an empty answer would look like a working narrator. |

Because the managed adapter is a placeholder, the API preflight refuses to start under a managed
profile while it is bound: `generation.CloudGenerationAdapter.generate` is one of the entries in
`managed_readiness.INCOMPLETE_MANAGED_OPERATIONS`, and `tests/unit/test_managed_readiness.py` is
the standing gate. That refusal is the control that stops the unwired narrator from reaching a
deployment, and it is the reason the fallback path is not a silent production hazard today.

## What the eval actually measures

`eval/run_eval.py --mode smoke` scores four metrics: `tolerance_accuracy` (0.99),
`concentration_accuracy` (0.99), `review_safety` (1.0) and `narrative_groundedness` (0.99). Read
the last one honestly: it does not score a model. It asserts that `numbers_are_grounded` ACCEPTS a
narrative quoting an engine figure and REJECTS one quoting an invented figure, so it proves the
check works rather than measuring what a narrator wrote. There is no model in the offline gate to
measure. Scoring a real narrator is the managed-profile run listed below.

Note what the not-falsely-green harness covers. `tests/unit/test_not_falsely_green.py` used to
plant its mutant against a `pii_safety` scorer defined inside the test, while the eval reported no
`pii_safety` metric at all: the proof was green, the SPEC promised the metric, and nothing was
measuring the boundary. `pii_safety` is now a reported metric and the harness falsifies the
SHIPPED scorer, on both boundaries it covers. The other four metrics still have no planted mutant
of their own; they are scored against independent oracles in `eval/datasets/`, so they are honest
measurements, but "every metric is proved able to go red" is true of `pii_safety` here and is
still an aspiration for the rest.

## Remaining controls (TODO, repo owner)

- **Wire or delete the managed narrator.** `adapters/gcp/generation.py` currently raises. Either
  implement the Gemini call (and then remove its entry from
  `managed_readiness.INCOMPLETE_MANAGED_OPERATIONS`), or drop the managed narrator and state that
  this service is deterministic-only. Leaving it as a placeholder is fine while the preflight
  refuses to boot with it bound; it stops being fine the moment somebody removes that entry without
  writing the call.
- **Model id, version and region** (P-07): there is no pinned model id in this repo at all, so
  there is nothing to confirm and nothing to record yet. When the adapter is written, pin the exact
  model and version and record it here. Gemini model ids are regional and an unavailable one fails
  at call time rather than at boot, so confirm the id is served in your deployment region before a
  managed deploy.
- **Budget, rate limit and a kill switch** (P-10, P-11): there is no per-tenant token budget, no
  request rate limit, and no switch that forces deterministic-only operation. The fallback path
  already exists, since a discarded or failed narration yields the deterministic prose, but nothing
  yet lets an operator disable a narrator deliberately.
- **A visible narration provenance flag.** The service returns the narrative text but does not
  report whether it came from the model or from the fallback, so a narrator that silently fails
  every call looks identical to one that works. Return the provenance alongside the text before you
  enable a managed narrator, so the eval and the demo can tell them apart.
- **Evaluation of the live model**: add a managed-profile run, registered with the Hrz4 promotion
  gate (P-08, rule R5), that scores `narrative_groundedness` over RAW narrator output rather than
  over the check's own fixtures.
- **Prompt-injection screening** (rule R1): the Hrz1 guardrail gateway is not bound. The exposure
  is real here rather than theoretical, because the managed pipeline is designed to pass extracted
  DOCUMENT TEXT (process docs, runbooks, org charts, via `DocumentExtractionPort`) to the model for
  edge proposal. Screen that text before it reaches a prompt, and fail closed to deterministic-only
  when the screen is unavailable.
- **Reasoning trace**: the audit record carries the result and its citations, not the prompt and
  reply pair. `COMPLIANCE.md` P-07 records that as owed.

Until these are complete the system is safe to run offline (deterministic engines plus the stub
adapter) and there is no managed model path to clear.
