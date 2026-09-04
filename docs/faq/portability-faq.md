# Portability FAQ

For architecture, cloud governance and exit planning. The question underneath all of these is "how
do we leave, and how do we know the answer is true today rather than on the day it was written?"

### What is the lock-in surface?

Every outbound dependency is a `@runtime_checkable` Protocol in `ports/` (asset inventory, audit,
compliance, document extraction, generation, identity, map store, observability, third-party
register, review router), bound per profile from `config/settings.yaml`. There is no cloud SDK
import anywhere in `domain/`, and the managed adapters import their SDK LAZILY inside the method,
so the other two families import with no SDK installed at all. Every consequential calculation
(map integrity, tolerances, scenarios, concentration) is pure stdlib in `domain/`, not a managed
service.

### What are the three profiles?

| Profile | What it is | Who it is for |
|---|---|---|
| `local` | SDK-free offline stack: seeded dev personas, a hash-chained SQLite WORM audit log, an in-process map store, a fictional estate behind the ingestion ports, a deterministic stub narrator | dev, test, CI, and the offline demo |
| `gcp` | the managed stack: IAP identity, Cloud Logging WORM, Cloud Asset Inventory, Document AI, AlloyDB, A2A clients for `third-party-risk-ddq` and `compliance-advisory`, an HTTP client to the `human-review-console` | a managed deployment, once its placeholders are implemented |
| `onprem` | fail-fast `NotImplementedError` placeholders | the sovereign exit: a client binds its own in-country implementations here |

`RESILIENCE_PROFILE` selects the family. Unset means the offline adapters bind but nobody chose
them, which withdraws every relaxation rather than granting one.

### Is the managed profile actually finished?

Not yet, and the repo says so in code rather than in a footnote.
`managed_readiness.INCOMPLETE_MANAGED_OPERATIONS` names the managed adapters that are still
placeholders (the asset-inventory scan, the document extraction, the Gemini narration, both
halves of the AlloyDB map store, the `third-party-risk-ddq` register read and the `compliance-advisory` compliance read), the API
preflight refuses to boot under a managed profile while
one of them is bound, and Terraform's `managed_profile_implemented` local
(`infra/terraform/managed_readiness.tf`) gates the serving edge the same way. Treat the `gcp`
column as a wiring plan with a fail-closed guard on it, not as a shipped deployment.

### Is the portability claim tested, or just documented?

Tested, three ways, all in the offline gate or one command:

- `tests/contract/test_port_parity.py` asserts set equality across all five homes of a port (the
  `PORT_PROTOCOLS` map, `config.DEFAULT_BINDINGS`, the `Container` accessor, `settings.yaml` and the
  canonical-call table), so a port cannot be added in four places and run unenforced.
- `tests/contract/test_behavioral_parity.py` proves the offline family ANSWERS, the on-premises
  family RAISES and the managed family REFUSES rather than silently succeeding. This matters most
  on the narration seam: a placeholder that quietly returned an empty narrative would look exactly
  like a working narrator.
- `make portability` is the executable claim: eight named checks with a pass or fail each (every
  port bound in every profile, adapter construction and Protocol conformance, the offline family
  answering, the exit family refusing, rewritten-record detection, anchored truncation detection,
  the trail leaving the codebase intact, and no cloud SDK imported), exiting non-zero on any
  failure. The stronger SDK-free proof lives in `tests/contract/_sdk_free_probe.py`, which BLOCKS
  the `google` import in a fresh interpreter rather than hoping the machine has none installed.

### Where does a resilience map live, and can we take it with us?

Today the offline `LocalMapStore` keeps maps in a per-instance dict and the managed AlloyDB adapter
raises, so the audit trail is the durable artefact. That is honest rather than ideal: a deployment
implements `MapStorePort` against a real store, and choosing it is adoption step 3 in
[`../ADOPTING.md`](../ADOPTING.md). What already exports cleanly is the audit trail, which
round-trips to and from JSON Lines, so the record of every proposal, scenario and finding is a file
copy. A map itself is plain frozen dataclasses (`domain/models.py`), and a saved map round-trips
byte-identical, so serialising it is a schema decision rather than a vendor extraction.

### How do we actually exit?

[`../onprem-migration.md`](../onprem-migration.md) is the path. The short version: the domain is
pure stdlib and moves unchanged; what you implement is one adapter per port under
`adapters/onprem/`, each of which currently raises with a message naming what to bind. Nothing in
`domain/` has to change, which is the point of the split.

### Can it run with no model at all?

Yes, and today that is the only way it runs. Every consequential figure is produced by a
deterministic engine, so the tolerances, the scenario verdict, the map gaps, the concentration
findings and the escalation are identical whichever generation adapter is bound. The model would
change one paragraph of prose and nothing else, and even that has a deterministic fallback used
whenever the narration is malformed, ungrounded, or raises. See
[`../model-card.md`](../model-card.md).

### Is the data residency claim portable too?

The region is chosen once and shared by the runtime and Terraform: `config/settings.yaml:region`,
`infra/terraform/render.tf.json:render_region`, and the Terraform `region` / `allowed_regions` pair,
which refuses an unapproved region at plan time. Changing jurisdiction is a configuration change in
those three places plus a re-run of `infra/terraform/production_edge.tftest.hcl`, not a code change.
