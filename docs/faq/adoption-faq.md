# Adoption FAQ

For an engineering lead forking this repo as their institution's resilience studio. The
step-by-step is [`../ADOPTING.md`](../ADOPTING.md); this answers the "will it hurt later?"
questions.

### How do I rebrand it for my organisation?

`scripts/rename_fork.py` rewrites the package name (`operational_resilience_mapping`, which is also the console
script), the `RESILIENCE_` env prefix (including the bare token that
`infra/terraform/render.tf.json` carries as `render_env_prefix`, so Terraform sets the same variable
names on the service), the Terraform `name_prefix` resource stem (`rgc9-svc`) and the distribution /
git id in one pass. Preview with `--dry-run`, apply with `--yes`, then recreate the venv,
`make install`, and run `make gate`. It skips itself, so the renamer is never left half-rewritten,
and it validates `--resource` against the same regex `infra/terraform/variables.tf` enforces, so a
stem the stack would refuse fails here rather than at plan time. The catalog id `Rgc9` is left alone
unless you pass `--catalog-id`, so a fork stays traceable to the entry it descends from. The script
does the mechanical rename; the human decisions (region, IdP, the estate, the tolerance packs, the
eval golden sets) are the checklist in `ADOPTING.md`.

### If several institutions fork this, how does each take upstream fixes?

Track upstream via **git tags**. The repo declares a core-vs-adopter-owned boundary
(`ADOPTING.md` section 2): upstream owns `domain/kernel.py`, `ports/`, `tests/contract/`, the eval
harness mechanics, `managed_readiness.py`, CI and the Terraform stack; you own
`config/settings.yaml` values, the fixture estate, the tolerance packs and scenario constants,
`adapters/onprem/*`, UI theming and `terraform.tfvars`. The commons packages (`hex-service-kit`,
`agent-eval-kit`, `pii-kit`, `review-kit`) are pinned by commit sha, so you take their fixes by
bumping the pin rather than by merging code. Rebase your adopter-owned changes onto each release
rather than merging `main` continuously.

### What do we have to supply that is not in this repo?

Four things, and two of them are code here:

1. **The estate.** `adapters/local/_fixtures.py` builds an obviously fictional important business
   service, technology inventory, outsourcing register, document corpus and compliance answer. Yours
   replaces all of it.
2. **Durable map persistence.** Offline the store is a per-instance dict; the managed AlloyDB
   adapter raises. Implementing `MapStorePort` against a real store, carrying each map's owning
   tenant on its rows, is the largest single piece of adoption work and it is not started.
3. **The upstream feeds.** Rgc8's register and Rsk1's compliance answers are read over A2A
   (`RGC8_REGISTER_URL`, `RSK1_COMPLIANCE_URL`). Both siblings are unbuilt in this wave, so the
   offline fixtures are the frozen contract; the managed adapters refuse when unconfigured rather
   than inventing data.
4. **The review console.** An Hrz7 deployment reachable at `HUMAN_REVIEW_URL`. The managed
   router REFUSES to swallow an escalation when this is empty, so a fork cannot ship rule R8 unwired
   and green.

### How do I add a new outbound dependency (a new port)?

There is a fixed touch list and a contract test that enforces it. A port must be registered in FIVE
places or it runs with no enforcement at all: `ports/__init__.py` (`PORT_PROTOCOLS`),
`config.DEFAULT_BINDINGS`, a `Container` accessor, `config/settings.yaml`, and a `PortCase` in
`tests/contract/canonical.py`. Then bind it in all three families.
`tests/contract/test_port_parity.py` asserts set equality across the five. See
[`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

### Can I retune the tolerance and scenario policy without touching code?

Partly, and the gap is stated honestly. `TolerancePack` values are DATA and `ToleranceEngine`
accepts an injected pack map, `ResilienceReviewPolicy` in `domain/hitl.py` is a frozen dataclass,
and the scenario recovery constants and concentration thresholds are module constants in
`domain/scenario_engine.py` and `domain/concentration_exit/`. What none of them are yet is a
`policy:` block in
`config/settings.yaml` with a `from_policy(...)` constructor, so today retuning means editing a
module rather than editing configuration. That is the open B4 item in
[`../practices-audit.md`](../practices-audit.md). If your resilience function must own these numbers
as configuration, plan that addition as part of adoption.

### Does the gate run for my fork out of the box?

Yes. `make gate` is offline, credential-free and network-free (ruff, ruff format, mypy strict, the
whole suite except integration, and the eval). You add secrets only when you wire the `gcp` profile.
Note the eval measures the REFERENCE packs and the reference estate until you rebuild the golden
sets for your own; that is an explicit adoption step, not a silent pass. Note also that the
tolerance oracle re-derives its expectation from the same packs, so editing a pack moves both sides
of the comparison: review that diff rather than accepting a still-green run as confirmation.

### The eval reports high scores. Should we believe them?

Believe what each one measures, and read two caveats rather than the headline.

`tolerance_accuracy` and `concentration_accuracy` are scored against INDEPENDENT oracles: the
golden rows in `eval/datasets/` carry their own expected values, and the tolerance oracle re-derives
its expectation from the packs rather than from the engine's answer. `review_safety` scores whether
a consequential result was escalated. Those three are honest measurements.

The caveats. First, `narrative_groundedness` does not measure a narrator: it asserts that
`numbers_are_grounded` accepts a grounded figure and rejects an invented one. It proves the check
works, which is worth having, but no model runs in the offline gate for it to score. Second, the
planted-mutant proof in `tests/unit/test_not_falsely_green.py` covers the SHIPPED `pii_safety`
metric only; a mutant planted in a scorer defined inside the test proves nothing about a metric
the eval actually reports, so "proved able to go red" is true of `pii_safety` and not yet of the
other four. Adding a mutant per reported metric is a small and worthwhile piece of adoption work.
See
[`../model-card.md`](../model-card.md).

### Will the demo rot after I diverge?

It is guarded, and the guard is inside the gate. A demo step lives in `demo.STEPS` and in
`walkthrough.CHECKS`, and `tests/unit/test_demo_surface.py` holds the two equal, so a claim the demo
makes but nobody verifies cannot exist. `make demo-selftest` runs the whole arc headless over the
real loopback server and exits non-zero when a claim stops being true. If you diverge, keep the step
keys and the `facts` dict the checks read.

### What is still open?

[`../practices-audit.md`](../practices-audit.md) carries the per-check verdict and the work list.
The ones that matter most before production: the managed placeholders in `managed_readiness.py`
(the asset-inventory scan, document extraction, Gemini narration and both halves of the AlloyDB map
store), the missing surfaces for the scenario and concentration engines, binding the Hrz1 guardrail
gateway before untrusted document text reaches a narrator, registering this repo's metric bundle
with Hrz4 so `eval/run_eval.py --mode gate` has an authority to ask, and B4. The Terraform stack is
written, validated and tested against a mocked provider; it has never been applied.
