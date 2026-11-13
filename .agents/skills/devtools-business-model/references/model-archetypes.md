# Developer-tool business model archetypes

Nine ways a developer tool turns adoption into revenue. Each entry gives what is sold, the prerequisite that must be true, the economics, the go-to-market it forces, the leading indicator that moves before revenue, and the failure mode it dies of.

Company names appear as public illustrations only - never as an argument that a model fits your situation. The numbering below is a catalogue index, not a ranking: the order to work through them is the efficiency order in the skill's step 2.

## Contents

1. Proprietary hosted SaaS
2. Open core
3. Hosted open source
4. Support, LTS and certified builds
5. Dual licensing
6. Source-available / delayed open source
7. Consumption metering on a free client
8. Ecosystem take-rate
9. Embedded / OEM licensing
10. Non-models
11. Stacking rules

---

## 1. Proprietary hosted SaaS

- **Sold:** access to a vendor-operated service, priced per seat, per unit of usage, or both.
- **Prerequisite:** the product is operable as a multi-tenant service, and the buyer accepts data leaving their perimeter.
- **Economics:** software margins, provided the free surface is bounded. Cost-to-serve is the variable to watch.
- **GTM forced:** self-serve for small contracts, inside sales as contracts grow, security review at enterprise scale.
- **Leading indicator:** activation-to-paid conversion rate within the first month of signup.
- **Dies of:** commoditization by an open alternative that is 80% as good and free, and by buyers who cannot send data out.

## 2. Open core

- **Sold:** proprietary modules around an open-source core. The term was coined by Andrew Lampitt in 2008 for monetizing open-source software "to which a for-profit company provides significant development support".
- **Prerequisite:** a paid boundary built from features an organization needs and an individual does not - SSO/SAML, RBAC, audit logging, multi-cluster or multi-tenant management, compliance reporting, long-term support builds.
- **Economics:** adoption is cheap, conversion is the hard part; expect a long gap between deployment count and revenue.
- **GTM forced:** two release trains, a written open/paid boundary, and some way to learn who runs the free version (opt-in telemetry, registry signals, community presence). Pipeline generation is the bottleneck, not closing.
- **Leading indicator:** rate at which free deployments hit a paid-boundary trigger - a second team, an audit request, a second cluster.
- **Dies of:** a core good enough that nobody crosses the boundary, or a boundary drawn through something the community already built.
- **Public illustration:** GitLab's community versus enterprise editions.

## 3. Hosted open source

- **Sold:** running the fully open project for the customer - uptime, upgrades, backups, scaling, support.
- **Prerequisite:** genuine operational burden. Convenience is only worth money when self-hosting hurts; stateless single-binary tools rarely qualify.
- **Economics:** infrastructure margin, thinner than pure software. Gross margin per workload is the number that decides viability.
- **GTM forced:** an SRE-grade operations team, margin discipline, and a pitch built on time, risk and uptime rather than features - your largest competitor is your own free self-hosted option.
- **Leading indicator:** self-host-to-cloud conversion rate, and gross margin per workload.
- **Dies of:** a cloud provider offering the same managed service with better distribution and lower cost of capital.

## 4. Support, LTS and certified builds

- **Sold:** a subscription covering SLAs, security backports, certified or hardened builds, indemnification and an escalation path.
- **Prerequisite:** enterprise buyers with procurement, audit and risk requirements, plus a real support organization.
- **Economics:** revenue scales with headcount, not usage. Predictable, defensible, slow, and valued lower per unit of revenue than usage-based models.
- **GTM forced:** field sales, procurement-ready paperwork (security questionnaires, DPAs, insurance), backport engineering, on-call support tiers.
- **Leading indicator:** renewal rate, and support cost per contract.
- **Dies of:** linear scaling - every new contract needs more people.
- **Public illustration:** the Red Hat subscription model.

## 5. Dual licensing

- **Sold:** a proprietary licence exempting the buyer from copyleft obligations.
- **Prerequisite:** the vendor owns or is assigned every copyright - hence a CLA - and the obligation is genuinely painful. AGPL for server software is the classic forcing function; permissive licences make this model impossible.
- **Economics:** high margin, lumpy, legally triggered rather than value triggered.
- **GTM forced:** copyright hygiene, an inbound legal-triggered sales path, and a team comfortable holding licence-compliance conversations without becoming adversarial.
- **Leading indicator:** commercial-licence inquiries per thousand downloads.
- **Dies of:** a permissively licensed near-equivalent, or an audience that complies rather than pays.
- **Public illustration:** Qt's commercial licence alongside its LGPL/GPL offering.

## 6. Source-available / delayed open source

- **Sold:** the same product, with competing hosted use restricted by licence (BUSL, FSL, Elastic License), often converting to an open licence after a set period. The Functional Source License, created by Sentry, states the bargain plainly: "You can do anything with FSL software except undermine its producer. You can run it for almost all purposes, study it, modify it, and distribute your changes" - converting to Apache-2.0 or MIT two years after each version ships.
- **Prerequisite:** a credible hyperscaler-absorption threat that already exists. If nobody could plausibly resell your software as a service, this buys nothing and costs contributors.
- **Economics:** protects hosted revenue; costs contribution, packaging and procurement reach.
- **GTM forced:** language discipline - "source-available", "fair source", "delayed open source", never "open source" - plus a plan for the distributions, foundations and corporate allowlists that exclude non-OSI licences.
- **Leading indicator:** contributor count and downstream packaging status in the two quarters after the change.
- **Dies of:** the fork, the trust cost, or both. Every documented relicensing has produced at least one.
- **Documented outcomes:**
  - Elasticsearch moved from Apache-2.0 to SSPL plus Elastic License 2.0 in 2021 and AWS forked OpenSearch; Elastic added AGPL-3.0 back as a third option in 2024.
  - Redis moved from BSD to RSALv2 plus SSPLv1 in March 2024 and AWS and Google backed the Valkey fork; Redis added AGPLv3 in Redis 8 in May 2025, its CEO writing that the change achieved the anti-hyperscaler goal but "hurt our relationship with the Redis community".
  - HashiCorp moved from MPL-2.0 to BUSL-1.1 in August 2023, for future releases only, and OpenTofu forked under the Linux Foundation.
- **Naming discipline:** the OSI ruled that SSPL "violates the Open Source Definition", and Bruce Perens, co-author of that definition, argues restrictive provisions disqualify a licence from being called open source. Say "source-available", "fair source" or "delayed open source" instead. The correction always arrives in public otherwise.

## 7. Consumption metering on a free client

- **Sold:** a metered backend service; the SDK, CLI and client libraries are free and often open.
- **Prerequisite:** a value metric the customer already counts and can forecast - requests, messages, builds, gigabytes, active devices, tokens.
- **Economics:** revenue expands with customer success and contracts with their downturns. Net revenue retention is the headline number.
- **GTM forced:** metering and usage attribution, spend caps and alerts, forecast tooling, committed-spend contracts at the top end.
- **Leading indicator:** net revenue retention, and the share of accounts above their committed floor.
- **Dies of:** bill shock. Unpredictable invoices in a developer audience become public posts and then churn.

## 8. Ecosystem take-rate

- **Sold:** a share of third-party transactions, listings or applications built on the platform.
- **Prerequisite:** liquidity - enough buyers _and_ enough suppliers that neither side has to be recruited individually.
- **Economics:** near-zero marginal cost, very long ramp. Almost never a first model.
- **GTM forced:** supplier recruitment, listing review and quality control, payouts, dispute handling, and a two-sided growth plan.
- **Leading indicator:** share of active customers installing at least one third-party listing.
- **Dies of:** being started before the ecosystem exists, and being taxed hard enough that suppliers route around it.

## 9. Embedded / OEM licensing

- **Sold:** the right for another vendor to ship your component inside their product - per device, per instance, or as a revenue share.
- **Prerequisite:** a component that is hard to rebuild and boring to own, plus a licensing and compliance function.
- **Economics:** few deals, large, slow, with long renewal cycles and heavy negotiation.
- **GTM forced:** partner-style business development, technical due diligence support, contract and audit machinery.
- **Leading indicator:** signed evaluation agreements and design wins in the partner's release cycle.
- **Dies of:** a permissively licensed near-equivalent that removes the need to sign anything at all.

## Non-models

- **Sponsorship and donations** fund maintainers, not payroll. Treat them as sustainability instruments and route them to funding-side guidance.
- **Consulting and implementation services** buy time and customer intimacy, and cap growth at hiring speed. Legitimate as a bridge, dangerous as a destination.
- **Training and certification** are a real revenue line, rarely a primary model, and they demand their own defensibility work before anyone pays for a credential.

## Stacking rules

- Combinations that work:
  - Hosted open source plus enterprise support.
  - Open core plus hosted.
  - Consumption plus a committed-spend floor.
  - Any model plus a training line once the first one is proven.
- Combinations that fight each other:
  - Open core plus source-available (two boundaries the community must track).
  - Consumption plus seats on the same value (the customer optimises against you).
  - Marketplace take-rate plus first-party competition with your own suppliers.
- One primary, at most one secondary. A plan with two primaries is a plan where the decision has not been made.
