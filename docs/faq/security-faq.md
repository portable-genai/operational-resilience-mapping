# Security FAQ

For AppSec and security architecture. Every answer names the file that is the evidence, so the
review can read the control rather than the claim.

### Who is the actor on a decision, and can a caller assert it?

A server-verified `Principal`, always. The request schemas carry no `actor` field: the audit actor
and the review maker both come from the identity adapter, and every client-supplied actor, tenant,
role, ACL and authorization header is discarded at the browser boundary
(`ui/lib/embed-policy.mjs`). Under the `gcp` profile the adapter verifies the IAP-injected
assertion against the configured audience, against IAP's own key set and against the issuer
(`adapters/gcp/identity.py`); an unset or emptied `RESILIENCE_IAP_AUDIENCE` REFUSES every caller,
because `audience=None` means google-auth does not verify the audience at all and would accept any
Google-signed token from any project. `tests/unit/test_iap_identity.py` runs in every gate and
`tests/unit/test_iap_crypto_matrix.py` drives the REAL verifier over locally minted assertions.

### Can one tenant read another tenant's resilience map?

No, and the refusal is a 403 rather than a 404. `StudioService.get_map` compares the verified
principal's tenant against the stored service's owning tenant and raises `AuthorizationError`
(`domain/errors.py`), which the API maps to 403. A 404 would leak whether a map for that service
exists at all, which is how a probe becomes an information disclosure. The tenant comes from the
verified principal, never from the request body. The offline `LocalMapStore` also keys its dict on
`(tenant, service_id)`, but the authoritative check is the domain one, so it holds whichever store
is bound.

### What happens if the profile variable goes missing in production?

The process still binds the SDK-free adapters (the alternative is importing cloud SDKs that are not
installed), but nobody chose them, so every relaxation is withdrawn: the seeded dev personas refuse
to construct, no service-to-service scheme is selected, the dev CORS allowlist and the
`X-Dev-Persona` header are gone, the interactive docs are not registered, and the loopback exposure
guard refuses every route to any non-loopback peer. An emptied or mis-capitalised value raises AT
IMPORT, so the process fails to boot rather than serving on a posture nobody chose (`config.py`,
`tests/unit/test_profile_single_source.py`).

### Does setting the service-to-service token open anything?

No, and this is enforced rather than intended. The exposure guard's posture is derived from the
identity BINDING (the adapter declares `VERIFIED` / `CLIENT_ASSERTED` / `UNIMPLEMENTED` in
`ports/identity.py`), never from a credential. `RESILIENCE_S2S_TOKEN` authenticates a calling
SERVICE and no end user. `tests/unit/test_end_user_auth_posture.py` walks the guard's argument
through the constants it names and fails the build if a credential reappears at any depth, because
it did once: setting the token switched the guard off for the end-user routes it was protecting.

### Can a managed deployment go live with half its adapters unimplemented?

No, and this is the control that most often surprises a reviewer. Several managed adapters in this
repo are still placeholders that raise, so `managed_readiness.INCOMPLETE_MANAGED_OPERATIONS` names
them and the API preflight REFUSES to start under a managed profile while any listed placeholder is
bound to a port the request path executes. Terraform's `managed_profile_implemented` local is the
deploy-time half of the same rule. `tests/unit/test_managed_readiness.py` is the standing gate. The
listed operations today are the asset-inventory scan, the document extraction, the Gemini narration,
both halves of the AlloyDB map store, the `third-party-risk-ddq` register read and the `compliance-advisory` compliance read. The test
holds the list EQUAL to the set of managed operations that actually raise, so the next placeholder
cannot be added without an entry.

### Where does personal data go?

This service reasons over services, vendors, systems and tolerances rather than customer records,
so the personal-data surface is small by construction. Named individuals do appear on people-chain
nodes and in extracted documents, and whatever appears is masked before it crosses any boundary:
before the audit write, before a review payload leaves the process
(`adapters/_review_payload.py`), and before a tool result can enter a model's context
(`agent/tools.py:_redacted`, which walks a nested result rather than only its top level). The
pattern set and its ORDER are this vertical's (`domain/pii.py`, national rows first, universal rows
last), drawn from the shared `pii-kit`.

### Can the model exfiltrate or invent anything?

Today the model cannot do anything at all: no profile performs a model call. The managed narration
adapter raises rather than calling Gemini, so the seam is built but unwired. The boundary it will
be dropped into is: exactly one port (`ports/generation.py`), a prompt built from engine figures,
and a reply that is discarded unless it parses as JSON with a `narrative` key and quotes only
figures the engine produced (`domain/narrative.py`: `parse_narrative`, `numbers_are_grounded`). A
discarded or failed narration falls back to deterministic prose. Prompt-injection screening through
the `agent-guardrail-gateway` is **not** wired, and it matters here because the managed design passes
extracted document text to the model. See [`../model-card.md`](../model-card.md).

### How is the audit trail protected?

Append-only and hash-chained, AND externally anchored. The chain catches an edit, a deletion or a
reorder; only the anchor catches a TRUNCATED TAIL, because dropping the newest rows leaves a
shorter chain that verifies perfectly. `audit_anchor_path` (`RESILIENCE_AUDIT_ANCHOR`) writes the
chain head to a file on another volume, and `tests/unit/test_audit_anchor.py` proves the detection,
proves the control case goes UNDETECTED without an anchor, and proves an append after truncation
refuses rather than re-anchoring. Under the managed profile the sink is a locked Cloud Logging
bucket (`infra/terraform/logging_worm.tf`), which provides non-rewritability itself.

### What about supply chain?

Both lockfiles are committed and pin every dependency exactly; the catalog commons are pinned to
40-character COMMIT shas rather than tags, because a re-pushed tag changes what installs with no
diff in the lockfile. The base image is digest-pinned, dependabot covers every ecosystem the repo
actually has, and `pip-audit` plus `npm audit --audit-level=high` are HARD CI failures.
`tests/unit/test_repo_artifacts.py` asserts each of these from inside the repo, and it asks git
whether each pinned sha is a COMMIT object rather than an annotated tag object, which a regular
expression cannot tell apart.

### What is deliberately out of scope?

- **Login.** This repo authenticates nobody itself: the platform in front of it does, and the UI
  forwards the assertion without parsing or trusting a parsed copy.
- **Injection defence and output filtering.** Owned by `agent-guardrail-gateway`; not bound yet.
- **The review queue.** Owned by `human-review-console`; this repo produces escalations and routes them.
- **The third-party register.** Owned by `third-party-risk-ddq`; read as data, never mirrored here.
- **The regulatory corpus.** Owned by `compliance-advisory`; read as data, never restated here.
- **Durable storage of a map.** Not implemented today: offline the store is an in-process dict and
  the AlloyDB adapter raises. A deployment implements it, and its access control is part of that
  work.
- **Network egress control.** VPC-SC governs access to Google APIs across perimeters, not arbitrary
  internet egress. The private-egress rule that lets this service reach `third-party-risk-ddq`, `compliance-advisory` and the `human-review-console` and nothing else is an adopter network decision, called out in `COMPLIANCE.md` P-01.
