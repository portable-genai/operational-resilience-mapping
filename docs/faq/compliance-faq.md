# Compliance FAQ

For compliance, model risk and the second line. The mapping table with a file reference on every
row is [`../../COMPLIANCE.md`](../../COMPLIANCE.md); this page answers the questions that come back
after reading it.

### Is an impact tolerance from this system defensible?

That is the reason the derivation is pure code. `ToleranceEngine` reads a named regulator pack
carried as DATA (APRA CPS 230, DORA, UK operational resilience, each with an explicit `reference`
string) and derives MTD, RTO, RPO and the customer-harm threshold from the chain criticality.
Three properties make the number mean something:

- **The chain criticality is computed, not asserted.** It is the worst criticality across the
  important business service and every node in its map, so a CRITICAL vendor buried under a HIGH
  service pulls the whole chain to CRITICAL rather than being averaged away.
- **The pack is your board's, not ours.** Every value is adopter-owned data, so replacing the
  reference numbers with your approved ones is a data edit rather than a code change, and the eval
  oracle re-derives its expectation from the same packs independently of the engine.
- **The model plays no part in any of it**, and today no model runs at all.

The same map and the same pack always produce the same tolerance, so a figure quoted to a regulator
can be replayed from the audit record.

### Who signs off a tolerance or a breach?

A human, always. `ResilienceReviewPolicy.requires_review` is unconditionally true for a tolerance
proposal, because setting a tolerance is a board-level act; a breached scenario is CRITICAL and a
within-tolerance one with aggravators is HIGH. Setting `requires_human_review` and calling
`ReviewRouterPort.route` is one act rather than a flag plus an intention: the API, the CLI and the
agent tool all route in the same call that produced the result, and
`tests/unit/test_review_routing.py` asserts the routing rather than the flag. Under the managed
profile the router REFUSES when no console is configured, so a deployment cannot swallow an
escalation silently.

### Where does the data live, and is residency enforced or just documented?

Enforced at deploy time. The region is chosen once (`asia-southeast1`) and shared by the runtime
and Terraform: `infra/terraform/variables.tf` validates the region against the residency allowlist
at plan, `org_policy.tf` pins `gcp.resourceLocations` to that region's location group, and every
regional resource (the CMEK key ring, the WORM log bucket, the Cloud Run service) is created in it.
`infra/terraform/production_edge.tftest.hcl` is the standing proof: its
`reject_region_outside_the_residency_allowlist` and `residency_defaults_are_in_country` runs fail if
the allowlist stops refusing or a resource drifts off region, and they run against a mocked provider
so they need no project and no credentials. The stack has never been applied.

### What about key management and least privilege?

One REGIONAL CMEK key with a 90-day rotation, and an explicit key binding for EACH service agent
that encrypts under it, because CMEK does not cascade (`infra/terraform/kms.tf`). One serving
identity holding only the roles a request needs, each traceable to a bound adapter, with
`logging.logWriter` write only so the process cannot read back the WORM trail it writes (`iam.tf`).
Exportable service-account keys are forbidden by org policy rather than merely avoided, and a key
creation raises an alert if one happens anyway (`org_policy.tf`, `monitoring.tf`).

### How long is the audit trail kept, and can it be edited?

The Cloud Logging bucket is LOCKED by default and its retention variable refuses anything below six
months (`reject_retention_below_six_months` in the Terraform test). The lock is irreversible: once
applied, retention cannot be reduced and the bucket cannot be deleted for the full window, not even
with project-owner rights, and `reject_reducing_existing_locked_retention` fails a plan that tries.
Confirm `retention_days` before the first apply. DATA_READ audit logging is enabled too, so a read
is itself recorded.

Offline the same guarantee is earned differently: the log is hash-chained AND externally anchored,
because a truncated tail leaves a shorter chain that verifies perfectly. The retention schedule and
the legal basis for the trail are adopter-owned.

### What personal data does this system process?

Very little by design: it reasons over business services, systems, vendors and tolerances rather
than customer records. Named individuals do appear on people-chain nodes and in the documents the
extraction port reads, and whatever appears is masked before every boundary (the audit write, the
outbound review payload, and any tool result that could enter a model's context), with the
jurisdiction rows and their ORDER chosen in `domain/pii.py`.

### Can one business unit see another's resilience map?

No. `StudioService.get_map` compares the verified principal's tenant against the stored service's
owning tenant and raises `AuthorizationError`, which the API maps to 403 rather than a 404 that
would leak existence, and the tenant comes from the verified principal rather than from the request
body. Note the honest limit: offline the store is a per-instance dict and the managed AlloyDB
adapter raises, so multi-tenant isolation at the STORE level is part of implementing durable
persistence, which this repo has not done.

### What model-risk evidence exists?

[`../model-card.md`](../model-card.md) records the model boundary as built, and the headline is that
**no model call happens in any profile today**: the managed narration adapter raises rather than
calling Gemini, and the API preflight refuses to boot under a managed profile while that placeholder
is bound (`managed_readiness.py`). The seam around it is complete (one port, a JSON schema, a
groundedness check on every figure, and a deterministic fallback that stands in whenever narration
is malformed, ungrounded or raises), so every consequential number is engine-produced whatever is
bound. What is NOT in place: no model id is pinned anywhere, there is no token budget, rate limit or
kill switch, no live-model eval run has been registered with the Hrz4 promotion gate, the service
does not yet report whether a narrative came from a model or from the fallback, and
prompt-injection screening through Hrz1 is not bound. Until those close, only the deterministic
path should be relied on.

### Which regulations does this claim to satisfy?

None, on your behalf. The mapping in `COMPLIANCE.md` is to the CATALOG's own principles (P-01 to
P-13) and platform rules (R1 to R8). The tolerance packs name APRA CPS 230, DORA and the UK
operational-resilience regime because those are the parameter SHAPES the engine carries; the values
shipped are reference defaults, not an interpretation of what any regulator requires of you. The
crosswalk to specific control ids, and the judgement that a control is SUFFICIENT for a regulation,
is explicitly adopter-owned. No row in that document should be quoted as regulatory assurance, and
the second-line review of the deterministic policy in `domain/` is bank-owned logic rather than a
vendor default to inherit unexamined.

### What is still open at go-live?

The `Partial` and `TODO (repo owner)` rows in `COMPLIANCE.md`, each of which names exactly what is
missing. The ones that need a risk acceptance if you go live without them: the managed placeholders
named in `managed_readiness.py` (including durable map persistence), rule R1 (the Hrz1 guardrail
binding, which matters here because the managed design passes extracted document text to a model),
rule R5 and P-08 (the Hrz4 metric bundle), P-10 (timeouts, circuit breaker and a documented kill
switch), and P-01's private-egress rule, which depends on your own network rather than on this
repo.
