# Features FAQ

For a product owner, a risk lead or a delivery manager deciding what this system does, what it
refuses to do, and where its responsibility ends.

### What does it actually do?

It builds and maintains the **resilience map** for an important business service, derives the
**impact tolerances** that map implies, and tests whether a named failure stays inside them. Four
deterministic engines and one narrated step:

1. **Ingestion and reconciliation** (`domain/ingestion_service.py`): three sources become typed
   dependency nodes, the technology estate from `AssetInventoryPort`, the material third parties
   from Rgc8's register over `RegisterReadPort`, and the process, people and facilities nodes from
   documents through `DocumentExtractionPort`. Candidate edges are reconciled against the known
   nodes; a candidate whose endpoint is unknown becomes a named gap, never a silent edge.
2. **Map integrity** (`domain/map_service.py`): deduplicates nodes and edges, and reports orphan
   nodes the service cannot reach and dependency cycles.
3. **Impact tolerance** (`domain/tolerance_engine.py`): per-regulator packs (APRA CPS 230, DORA, UK
   operational resilience) carried as DATA turn the chain criticality into MTD, RTO, RPO and a
   customer-harm threshold. The chain criticality is the worst criticality across the service and
   every node beneath it, so a CRITICAL vendor under a HIGH service pulls the whole chain to
   CRITICAL.
4. **Scenario testing** (`domain/scenario_engine.py`): remove a node, propagate the disruption
   across the graph, compare the computed recovery against the accepted MTD. A removed node with no
   exit path recovers slower, so a concentration finding is an aggravator rather than a separate
   report.
5. **Concentration and exit** (`domain/concentration_exit/`): four deterministic dimensions,
   SINGLE_PROVIDER, SINGLE_REGION, CRITICAL_SERVICE and DATA_GRAVITY, each mapped to the
   outsourcing expectation it offends and grounded afterwards on Rsk1's cited answer.

Narration sits on top of step 3 and computes nothing.

### What makes a tolerance defensible?

Three properties, all pure code:

- **The numbers come from a named pack, not from a model.** `TOLERANCE_PACKS` carries each
  regulator's parameter shape as data with an explicit `reference`, so the derivation is inspectable
  and a board can replace the pack with its own approved numbers without touching the engine.
- **The derivation is replayable.** Same map, same pack, same tolerance, every time. The eval
  oracle re-derives the expected value from the SAME packs independently of the engine
  (`eval/run_eval.py`), so the metric measures the engine rather than agreeing with it.
- **The regulatory basis is cited, never invented.** The grounding text comes from Rsk1 over
  `CompliancePort`. When that source is unavailable the answer carries no citations and sets
  `requires_human_review`, so an ungrounded finding escalates instead of being asserted.

### What is the model allowed to say?

Only a justification narrative that restates figures the engine produced, and today it says nothing
at all: no profile performs a model call, because the managed narration adapter is still a
placeholder that raises. When one is wired, the reply must parse as JSON with a `narrative` key and
may quote only engine figures; anything else is discarded and deterministic prose stands in. See
[`../model-card.md`](../model-card.md).

### What will it refuse to do?

- **It will not serve another tenant's map.** `StudioService.get_map` raises `AuthorizationError`,
  which the API maps to 403 rather than a 404 that would leak whether the map exists.
- **It will not invent a dependency.** A model-proposed edge whose endpoint is unknown becomes a
  reconciliation gap, not an edge.
- **It will not invent regulatory text.** A concentration finding or a tolerance basis cites the
  answer Rsk1 returned, and an unavailable source escalates.
- **It will not auto-execute a consequential result.** A tolerance proposal is ALWAYS reviewed
  (`ResilienceReviewPolicy.requires_review` is unconditionally true), and a breached scenario is
  CRITICAL; both are ROUTED to the Hrz7 console in the same call that produced them (rule R8).
- **It will not become healthy on a managed profile with placeholder adapters bound.** The preflight
  refuses to start (`managed_readiness.py`).
- **It will not answer without provenance.** Every claim carries a `Citation`.

### Which surfaces expose it?

The FastAPI app (`POST /v1/tolerance`, which builds the map and proposes tolerances in one
request), the argparse CLI (`map` and `tolerance`), the agent tools (`assess_resilience`,
`verify_audit_trail`, advertised on the A2A card at `/.well-known/agent-card.json`), the embeddable
`ui/` micro-frontend, and the eval harness. Each routes escalations in the same call, so rule R8
does not hold on some surfaces and not others.

Note the honest limit on surface coverage: `StudioService.run_scenario` and
`StudioService.concentration` are engine-complete and exercised by the demo and the tests, but they
have no HTTP route, CLI subcommand or agent tool yet. Exposing them is a straightforward addition
and is not done.

### What does this repo own, and what does it integrate?

| Concern | Owner | How this repo touches it |
|---|---|---|
| The resilience map for an important business service | **this repo (Rgc9)** | it IS the system of record. Consumers read the map from here rather than rebuilding one. |
| Impact tolerances and stay-within-tolerance scenario testing | **this repo (Rgc9)** | derived by pure engines from the map plus a regulator pack. |
| Concentration and exit findings | **this repo (Rgc9)** | the `domain/concentration_exit/` module, kept here so a concentration finding can aggravate a scenario instead of living in a second tool. |
| The third-party / outsourcing register | **Rgc8** third-party risk and DDQ | read as data over `RegisterReadPort` (`RGC8_REGISTER_URL`). Rgc8 is unbuilt, so the offline fixture register is the frozen contract. |
| The regulatory corpus and grounded rule text | **Rsk1** compliance assistant | read over `CompliancePort` (`RSK1_COMPLIANCE_URL`). This repo cites what Rsk1 returns; it does not track the corpus. |
| Agent discovery and entitlements | **Hrz3** agent registry | this agent publishes a card; the registry owns discovery. |
| Model and agent promotion | **Hrz4** AI quality and model risk | `eval/run_eval.py --mode gate` asks Hrz4; the offline smoke mode never promotes. |
| Traces and the immutable audit sink | **Hrz5** agent observability | `AuditSinkPort` and `ObservabilityTracerPort`. |
| Human review and maker-checker | **Hrz7** human review console | `ReviewRouterPort` over the shared `review-kit`. This repo produces escalations; it does not render a queue. |
| Prompt-injection defence and output filtering | **Hrz1** agent guardrail gateway | **not wired today.** It becomes mandatory the moment untrusted free text reaches the narrator (rule R1), and the managed design does pass extracted document text to it. |
| Grounded retrieval over an enterprise corpus | **Hrz2** enterprise knowledge base | not wired; this service reasons over its own graph and cites Rsk1 for rule text. |

### Can I demo it without a cloud project?

Yes, and the demo is code rather than a deck. `make demo` runs a presenter-paced walkthrough over
eight steps (opened, routine, escalation, redaction, review queue, audit, tamper, portability) on
its own loopback server; `make demo-selftest` runs the same arc headless and asserts every narrated
claim, so a claim that stops being true fails a build rather than a meeting; `make demo-static`
renders the same audit-first panels to static HTML for screenshots.
`tests/unit/test_demo_surface.py` holds `demo.STEPS` and `walkthrough.CHECKS` equal, so a claim the
demo makes but nobody verifies cannot exist.

### What is not built yet?

The honest list is [`../practices-audit.md`](../practices-audit.md) and the `TODO (repo owner)` rows
in [`../../COMPLIANCE.md`](../../COMPLIANCE.md). The four that matter most for a production
decision: the managed placeholders named in `managed_readiness.py` (including durable map
persistence), routes for the scenario and concentration engines, the Hrz1 guardrail binding, and
registering this repo's metric bundle with Hrz4 so `--mode gate` has an authority to ask.
