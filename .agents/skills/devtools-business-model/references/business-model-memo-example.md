# Worked memo, and weak versus strong sections

The product below is fictional, so nothing here should be read as a benchmark. It exists to show the level of specificity a finished memo needs.

No real company publishes this deliberation - outcomes get announced, the reasoning behind them does not - so a fabricated-but-labelled example is the honest option. Every number in it is illustrative.

**Situation.**

- Team: five people, maintaining an Apache-2.0 workflow-orchestration server. Developers define pipelines in code, the server schedules and retries them, stores run history, and exposes a web UI.
- Adoption: roughly 4,000 self-hosted deployments send opt-in telemetry. No revenue.
- Team background: two of the founders are ex-SRE. Nobody has sold anything before.
- Runway: eighteen months.

---

## Table of Contents

- [Business model - Orchestron](#business-model-orchestron)
- [Weak versus strong sections](#weak-versus-strong-sections)

## Business model - Orchestron

### Constraints

- Licence: Apache-2.0 on everything published since the first release. The team refuses relicensing and has said so publicly.
- Deployment: the server is stateful, needs a database, and upgrades break pipelines when done carelessly - self-hosting genuinely hurts at scale.
- Buyer: telemetry shows 61% of deployments run inside companies, most of them on a single team's infrastructure. The signer is an engineering manager or platform lead, not the pipeline author.

### Rejected

- **Dual licensing** - impossible under Apache-2.0, and relicensing is refused.
- **Source-available** - no hyperscaler is reselling this; the cost would be contributors, with nothing bought.
- **Support/LTS as primary** - no enterprise footprint yet, and it caps growth at hiring speed with two engineers who would rather build.
- **Marketplace take-rate** - 19 community plugins exist; there is no market to tax.
- **OEM licensing** - nobody embeds an orchestration server, and Apache-2.0 already grants what an embedder would want.

### Primary model

Hosted open source: a managed Orchestron cloud, priced on concurrent pipeline runs. Everything in the product stays Apache-2.0; the company sells operation - upgrades, retention of run history, availability, and not being paged at 03:00 when the scheduler wedges. The prerequisite it depends on: operating it is hard enough that a platform team prefers to pay.

Telemetry supports this: 34% of company deployments are more than two minor versions behind, and the top issue label for eighteen months has been upgrade failures.

### Paid boundary

- Always free: the full server, every executor, the UI, the plugin API, all authentication methods including SSO, and every security patch.
- Paid: the hosted service only, plus retention beyond 30 days of run history on that service.

The line holds because it is not a feature line at all - nothing is withheld from the open project, so there is nothing to fork around.

### Value metric

Concurrent pipeline runs.

- Already counted: teams already size their self-hosted deployment by this number.
- Grows with value: it grows as the platform carries more of their work.
- Forecastable: it is visible in their own dashboards before the invoice arrives.
- Rejected: per-seat, because pipeline authors are a small fraction of the people who benefit and the count does not move as usage grows.

### GTM consequence

Self-serve first: sign up, point at a Git repository, run pipelines in under fifteen minutes. Expected contracts start small, so no sales hire before the first twenty paying teams.

What must be built:

- Multi-tenant isolation.
- A migration path from self-hosted state.
- Per-run metering.
- Spend caps.
- An on-call rotation the two ex-SRE founders can staff for six months and not longer.

First investments in order:

1. Metering and caps.
2. Migration tooling.
3. The third SRE.

### Leading indicator

- Primary: self-host-to-cloud conversion rate among deployments that have opted into telemetry and hit an upgrade failure in the last 90 days. Read monthly, target 3% of that cohort within two quarters of launch.
- Guardrail: gross margin per workload, tracked alongside it, with a floor of 60%.

### Risks

1. **Margin too thin.** Long-running pipelines make compute the dominant cost. Signal: gross margin per workload below 60% in any month after the third.
2. **Self-hosting is good enough.** The operational pain is real but tolerated for free. Signal: fewer than 1% of the upgrade-failure cohort converting after two quarters.
3. **Operating the service starves the project.** Releases slow, community drifts. Signal: median time-to-first-response on issues doubling from the current baseline.

### Revisit triggers

- A cloud provider announces a managed Orchestron-compatible service.
- Gross margin per workload stays below the floor for two consecutive quarters (failure condition - reopen with support/LTS as the candidate primary).
- Inbound requests for on-premises support exceed five per month, which would make support a viable secondary.
- Plugin installs pass 40% of active deployments, which would make an ecosystem model worth re-examining.

---

## Weak versus strong sections

### Paid boundary

**Weak:** "The open-source version stays fully featured; enterprise features will be added to the paid tier as we identify them."

Wrong because the boundary is deferred. "As we identify them" means:

- The community cannot tell what is safe to build.
- Contributors avoid the areas that might get taken.
- The first paid feature lands as a surprise.

A boundary that is not written is read as intent to close.

**Strong:** the section above - an explicit always-free list, a paid side that withholds nothing from the project, and a stated reason why the line survives contact with a motivated contributor.

### Value metric

**Weak:** "Usage-based pricing, based on compute consumed."

Wrong on three of the four checks:

- The customer does not count compute for their own reasons.
- Cannot forecast it before the invoice.
- Cannot verify your measurement.

Every invoice becomes a negotiation.

**Strong:** concurrent pipeline runs - a number the team already sizes their cluster with, visible in their own tooling, explainable in one sentence.

### Risks

**Weak:** "Risks: competition, execution, market timing."

Wrong because none of them has a signal, so nothing can ever be observed to be happening. A risk without a trigger is a disclaimer.

**Strong:** the three above - each with a number, a threshold and a place it is read.

### GTM consequence

**Weak:** "Open core, with SSO, RBAC and audit logging in the paid tier at $49 per user per month, sold self-serve through the website."

Wrong because the boundary and the motion contradict each other. Nothing triggers the paid tier until an organization needs governance features, and an organization buying governance features runs a security review, a procurement cycle and a legal review, none of which a self-serve checkout survives.

Model it before committing: the acquisition cost of a reviewed enterprise deal against the lifetime value of a handful of seats. David Skok's _SaaS Metrics 2.0_ puts the healthy reference at an LTV-to-CAC ratio above 3 with CAC recovered in 5-7 months. A boundary that only opens at enterprise scale, priced for a credit card, misses both by a wide margin.

Either move the boundary down so a small team crosses it, or price and staff for the sale the boundary actually requires.

**Strong:** the section above - a motion the boundary can support, a stated point at which a human enters the sale, and the investments ordered.

### Leading indicator

**Weak:** "We'll track monthly recurring revenue and GitHub stars."

Wrong because neither moves before the outcome. Revenue is the outcome, and stars measure attention that no model converts. A leading indicator has to sit upstream of the money and be readable monthly.

**Strong:** the section above - conversion of a specific, observable cohort, read on a stated cadence, with a target, a date and a margin floor beside it.

### Rejected

**Weak:** omitting the section entirely.

Wrong because the discarded options come back every quarter, argued from scratch, usually by whoever was not in the room. Writing the blocking constraint next to each rejection converts a debate into a lookup.
