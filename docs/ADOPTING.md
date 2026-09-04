# Adopting this repo as your base

This repository (`operational-resilience-mapping`, Operational Resilience Studio) is a **common base** that a bank or other
regulated institution forks to build its own **resilience-map and impact-tolerance studio**: the
service that answers what an important business service actually depends on, what tolerance the
board should set for it, whether a named failure stays inside that tolerance, and where the estate
is concentrated with no exit. It ships a reusable hexagonal core (a pure-stdlib domain, typed
ports, three swappable adapter profiles, a green offline gate) plus four worked deterministic
engines over an obviously fictional estate that you can keep, reseed, or retune.

This guide is the step-by-step for making it yours. It has two halves: a **mechanical rebrand**
(one script) and the **human decisions** the script cannot make for you.

> Related reading: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (the port table and topology),
> [`CONTRIBUTING.md`](../CONTRIBUTING.md) (adding an adapter, adding a port), the
> [`faq/`](faq/) directory, [`model-card.md`](model-card.md) (the model boundary),
> [`practices-audit.md`](practices-audit.md) (the per-check verdict).

---

## 1. What you keep vs what you rewrite

The core is hexagonal, and the boundary between reusable machinery and this vertical is a physical
module split with an enforced dependency direction. `domain/kernel.py` owns the vertical-neutral
contracts and imports nothing from the vertical; `domain/models.py` holds this service's own
resilience artifacts.

| Layer | Where | For your own studio |
|---|---|---|
| **Vertical-neutral machinery** | `domain/kernel.py` (`Citation`, `AuditEvent`, `Severity`, `SEVERITY_RANK`, `Decision`, `utcnow`), every Protocol in `ports/`, the container wiring in `config.py` | keep untouched |
| **Graph and scoring machinery** | `domain/map_service.py` (dedup, orphan and cycle detection), the traversal in `domain/scenario_engine.py`, the cosine-free set arithmetic in `domain/concentration_exit/concentration_service.py` | keep untouched; it is vertical-neutral graph work |
| **Policy (your numbers and rules)** | `TOLERANCE_PACKS` in `domain/tolerance_engine.py` (the per-regulator MTD, RTO, RPO and customer-harm parameter shapes), `_BASE_RECOVERY`, `_HOP_PENALTY` and `_NO_EXIT_MULTIPLIER` in `domain/scenario_engine.py`, `ResilienceReviewPolicy` in `domain/hitl.py`, the portability baselines in `domain/concentration_exit/portability_policy.py`, the jurisdiction list in `domain/pii.py`, the metric thresholds in `eval/run_eval.py` | change deliberately (see section 4) |
| **Vertical (the estate content)** | the fictional estate in `adapters/local/_fixtures.py`, the vertical models in `domain/models.py`, the narration prompt in `domain/studio_service.py`, the eval golden sets in `eval/datasets/` | reseed and rewrite for your own service map |

If your product is another *dependency-graph plus threshold* service, the hexagon, the three
profiles, the deterministic-verdict pattern, the eval gate and the `human-review-console` review routing transfer
directly; you replace the estate content and retune the tolerance and scenario policy.

## 2. Core-vs-adopter-owned files (so upstream merges stay mechanical)

Upstream keeps evolving these; avoid diverging from them so you can pull fixes cleanly:

- **Upstream-owned** (take our changes): `domain/kernel.py`, `ports/`, `tests/contract/`, the eval
  harness mechanics (`eval/run_eval.py`), the CI workflows, the hexagon wiring (`config.py`
  `Container`, `factory.py`), `managed_readiness.py` and the deploy stack in `infra/terraform/`.
- **Adopter-owned** (yours; expect to edit): `config/settings.yaml` *values*, the fixture estate in
  `adapters/local/_fixtures.py`, the tolerance packs and the scenario constants, `adapters/onprem/*`,
  UI theming and branding, the golden eval datasets, `infra/terraform/terraform.tfvars`, and the
  regulator crosswalk section of `COMPLIANCE.md`.

Track upstream via git tags; rebase your adopter-owned changes onto each release rather than
merging `main` continuously.

## 3. The mechanical rebrand (one script)

`scripts/rename_fork.py` rewrites the package name (`operational_resilience_mapping`, which is also the console
script), the `RESILIENCE_` env prefix (including the bare token that
`infra/terraform/render.tf.json` carries as `render_env_prefix`, so Terraform sets the same
variable names on the service), the cloud resource stem (`rgc9-svc`, the Terraform `name_prefix`)
and the distribution / git id in one pass. Preview first, then apply:

```bash
# Preview (writes nothing):
python scripts/rename_fork.py --package acme_resilience_mapping --env-prefix ACME \
    --resource acme-resilience --dry-run

# Apply:
python scripts/rename_fork.py --package acme_resilience_mapping --env-prefix ACME \
    --resource acme-resilience --yes

# Then recreate the environment (the distribution name changed) and prove it is green:
python3.12 -m venv .venv && source .venv/bin/activate
make install
make gate
```

`--dist` defaults to the `--resource` value; pass it explicitly when your git id differs from your
resource stem. `--resource` is validated against the same regex the Terraform `name_prefix`
variable enforces, so a stem the stack would refuse fails here instead of at plan time. Add
`--include-docs` to sweep Markdown prose too. The catalog id `operational-resilience-mapping` is left alone unless you pass
`--catalog-id`, so a fork stays traceable to the entry it descends from. The script skips itself,
so the renamer is never left half-rewritten, and it deliberately does NOT touch the human decisions
below.

## 4. The human decisions (the script can't make these)

1. **Region / residency.** The build defaults to `asia-southeast1` (MAS / Singapore), chosen once
   and shared: `config/settings.yaml:region`, `infra/terraform/render.tf.json:render_region` and
   the Terraform `region` / `allowed_regions` pair. Set all of them to your in-country region and
   re-run `infra/terraform/production_edge.tftest.hcl`, whose
   `reject_region_outside_the_residency_allowlist` run refuses a region outside the allowlist at
   plan time. See [`runbook.md`](runbook.md).
2. **Identity / IdP.** This repo owns no login flow: the `gcp` profile verifies the IAP-injected
   assertion at the edge, `local` uses seeded dev personas, and `onprem` is a client IdP
   placeholder. Wire your issuer on the deployed service (auth is configured ON the service, not in
   this code) and set `RESILIENCE_IAP_AUDIENCE`. An unset or emptied audience refuses every caller
   rather than verifying without one.
3. **The estate itself.** `adapters/local/_fixtures.py` builds an obviously fictional demo estate:
   an important business service, a technology inventory, an outsourcing register, a document
   corpus and a grounded compliance answer. That fixture is a shape, not your service map. Replace
   it with your own, and decide where a map lives in a deployment: the offline `LocalMapStore`
   holds maps in a per-instance dict, and `adapters/gcp/map_store.py` is an AlloyDB placeholder
   that raises, so a real deployment has to implement durable persistence behind `MapStorePort`.
4. **Policy your resilience function owns.** Four sets of numbers decide everything consequential
   and none of them are ours to set for you:
   - `TOLERANCE_PACKS` in `domain/tolerance_engine.py`, the per-regulator (APRA CPS 230, DORA, UK
     operational resilience) MTD, RPO and customer-harm parameter shapes plus the RTO fraction.
     Your board approves these; the pack is data, so swapping them is a data edit.
   - `_BASE_RECOVERY`, `_HOP_PENALTY` and `_NO_EXIT_MULTIPLIER` in `domain/scenario_engine.py`,
     which turn a removed node into computed disruption minutes.
   - `ResilienceReviewPolicy` in `domain/hitl.py`, which decides that a tolerance proposal is
     always reviewed and what band a breached scenario carries.
   - the concentration thresholds and portability baselines in `domain/concentration_exit/`.

   These are module-level constants and injectable dataclasses today rather than a `policy:`
   section in `config/settings.yaml` (practices-audit check B4 is the open item); change them
   deliberately and add a test that pins your values.
5. **Tenancy.** A stored map carries its owning tenant, and `StudioService.get_map` raises
   `AuthorizationError` (mapped to 403, never a 404 that would leak existence) when the verified
   principal's tenant does not match. Offline the fixture estate IS the demo bank's estate. Decide
   how your deployment carries the owning tenant on map rows before you serve a second one.
6. **Reference data is fictional.** Every fixture uses obviously fake parties and `.example`
   domains, and the demo service is named `Retail Payments (FICTIONAL)`. Replace them with your own
   synthetic data. **Do not run against a real service map or a real outsourcing register without
   your own security and model-risk sign-off.**
7. **Eval golden set.** Rebuild `eval/datasets/golden_tolerances.jsonl` and
   `eval/datasets/golden_plans.jsonl` for your packs: a fork inherits a green gate that measures
   the WRONG numbers until you do. The four metrics (`tolerance_accuracy`,
   `concentration_accuracy`, `review_safety`, `narrative_groundedness`) and their thresholds are
   generic; the golden cases are yours. The tolerance oracle re-derives the expected value from the
   same packs independently of the engine, so a pack edit moves both sides and you must review the
   diff rather than accept it.
8. **Deployment posture.** Review the Dockerfile (digest-pinned base, non-root uid 10001),
   `infra/terraform/` (Org Policy, CMEK, a dry-run-first VPC-SC perimeter, the locked WORM log
   bucket, the load-balancer-only serving edge) and the loopback-by-default binding before you
   expose anything. The WORM lock is irreversible: confirm `retention_days` before the first apply.
   Note also `managed_readiness.INCOMPLETE_MANAGED_OPERATIONS`: the API preflight refuses to boot
   under a managed profile while a listed placeholder adapter is still bound, so implementing those
   adapters is part of going managed rather than an optional extra.

## 5. Do not duplicate the platform

This repo is one system in a catalog of composable GRC systems. It is deliberately the OWNER of the
resilience map and the impact tolerance, and a READER of everything else. What it integrates rather
than rebuilds (see [`faq/features-faq.md`](faq/features-faq.md) for the full map):

- `third-party-risk-ddq` third-party / outsourcing register: read as data over `RegisterReadPort`
  (`RGC8_REGISTER_URL`). `third-party-risk-ddq` owns the register; this repo never keeps a second copy of it.
- `compliance-advisory`: the regulatory text that grounds a tolerance basis or a
  concentration finding, read over `CompliancePort` (`RSK1_COMPLIANCE_URL`). The studio never
  invents regulatory text.
- `human-review-console` human-review / maker-checker console: every `requires_human_review` escalation is routed
  to it over the shared `review-kit` (rule R8); you wire your endpoint
  (`HUMAN_REVIEW_URL`), you do not re-implement the console.
- `agent-observability` plus immutable WORM audit: audit events and trace spans go to it through
  `AuditSinkPort` and `ObservabilityTracerPort`.
- `model-quality-gate` AI-quality / model-risk gate: owns promotion. `eval/run_eval.py --mode gate` is the
  client half and refuses to run off the managed profile.
- `agent-registry`: this agent publishes its A2A card at `/.well-known/agent-card.json`;
  register it rather than inventing a discovery mechanism.

The guardrail gateway (`agent-guardrail-gateway`) is **not** integrated today, and the enterprise knowledge base (`enterprise-knowledge-base`)
is not either. `agent-guardrail-gateway` becomes mandatory the moment untrusted free text reaches the narrator: see rule
R1 in [`../COMPLIANCE.md`](../COMPLIANCE.md).

## 6. Adoption checklist

- [ ] Ran `scripts/rename_fork.py`, recreated the venv, `make gate` green.
- [ ] Set the region in all three places (settings, `render.tf.json`, tfvars) and re-ran the
      Terraform residency tests.
- [ ] Wired your IdP audience on the deployed service (this repo owns no login flow).
- [ ] Replaced the fixture estate with your own important business services, technology inventory,
      third parties and documents, and implemented durable persistence behind `MapStorePort`.
- [ ] Owned the policy numbers (tolerance packs, scenario recovery constants, the review policy,
      the concentration thresholds) with your resilience and risk functions.
- [ ] Decided how the owning tenant is carried on map rows before serving a second tenant.
- [ ] Replaced every synthetic fixture.
- [ ] Rebuilt both eval golden sets for your packs.
- [ ] Reviewed the deploy posture (Dockerfile, Terraform, `retention_days`, bind address) and
      worked through `managed_readiness.INCOMPLETE_MANAGED_OPERATIONS`.
- [ ] Wired your `human-review-console` review endpoint and decided which sibling services you integrate vs stub.
- [ ] Read [`model-card.md`](model-card.md) and closed its remaining controls before enabling any
      managed narrator.
- [ ] Recorded your baseline upstream tag so you can take future fixes.
