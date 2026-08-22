# FAQ index

Answers to the questions different teams ask when evaluating, adopting or reviewing this
repository as the resilience-map and impact-tolerance studio. Each file is written for a specific
audience; skim the one that matches your role.

| FAQ | For | Answers |
|---|---|---|
| [security-faq.md](security-faq.md) | AppSec / security review | server-side identity, tenant isolation on a stored map, the exposure guard, secrets, supply chain, the audit chain |
| [portability-faq.md](portability-faq.md) | Architecture / cloud / exit planning | no-lock-in, the three profiles, the sovereign exit, where a map lives |
| [features-faq.md](features-faq.md) | Product / risk / delivery | what the four engines compute, what the model is allowed to say, and the boundary with sibling catalog systems |
| [adoption-faq.md](adoption-faq.md) | Engineering leads forking the repo | rename, upstream fixes, extension points, what stays open |
| [compliance-faq.md](compliance-faq.md) | Compliance / model risk / second line | why a tolerance is defensible, maker-checker, residency, retention, model-risk evidence |

These FAQs deliberately do **not** re-document capabilities owned by sibling systems in the GRC
catalog. Where a concern belongs to another repo (the outsourcing register Rgc8, the regulatory
corpus Rsk1, the guardrail gateway Hrz1, the knowledge base Hrz2, the agent registry Hrz3, the
eval and promotion authority Hrz4, observability and the WORM sink Hrz5, the human-review console
Hrz7), the FAQ points at it and explains the boundary rather than duplicating it. See
[features-faq.md](features-faq.md) for the full "what this repo owns vs what it integrates" map.

Authority order for anything these pages disagree with: [`SPEC.md`](../../SPEC.md), then
[`ARCHITECTURE.md`](../../ARCHITECTURE.md), then [`COMPLIANCE.md`](../../COMPLIANCE.md), then
[`README.md`](../../README.md). These pages restate; they do not decide.
