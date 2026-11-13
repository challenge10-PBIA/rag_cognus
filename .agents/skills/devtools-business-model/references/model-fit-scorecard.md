# Model fit scorecard

Use this to eliminate archetypes fast, then to score the survivors. Fill it in writing - a test answered in conversation and never recorded is a test that gets silently re-answered later.

## Contents

1. Constraint elimination table
2. The five paid-boundary tests
3. Scoring sheet
4. Value metric checks
5. Never on the paid side
6. Reversibility ladder
7. Validation experiment per candidate

---

## 1. Constraint elimination table

Answer the three constraints from step 1, then strike out what they forbid.

| Constraint answer                                                   | Archetypes eliminated                                           | Archetypes favoured                                     |
| ------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| Customer must run it themselves (compliance, data gravity, air gap) | hosted SaaS, hosted open source                                 | open core, support/LTS, dual licensing, OEM             |
| You operate it and customers accept that                            | -                                                               | hosted SaaS, hosted open source, consumption            |
| Already published under a permissive licence                        | dual licensing (no forcing function)                            | open core, hosted open source, support/LTS              |
| Already published under strong copyleft you own entirely            | -                                                               | dual licensing, open core                               |
| No copyright ownership (community-owned, DCO only, foundation)      | dual licensing, source-available                                | hosted open source, support/LTS, consumption            |
| Nothing published, no intention to open anything                    | open core, hosted open source, dual licensing, source-available | hosted SaaS, consumption, OEM                           |
| No credible hyperscaler-absorption threat                           | source-available                                                | any open model                                          |
| No sales capacity and none planned                                  | support/LTS, OEM, dual licensing                                | hosted SaaS, consumption, hosted open source            |
| Near-zero cost to serve a user                                      | hosted open source (nothing to sell)                            | consumption is weak here; seats or open core fit better |
| Heavy per-user infrastructure cost                                  | generous free tiers of any kind                                 | consumption, hosted models with caps                    |
| No ecosystem of third-party builders                                | ecosystem take-rate                                             | revisit after platform adoption                         |
| Individual developers only, no organizations                        | open core, support/LTS, dual licensing, OEM                     | hosted convenience tiers, small consumption plans       |

A constraint that eliminates every archetype means one of the constraints is wrong or the product is not a business yet. Say so rather than forcing a fit.

## 2. The five paid-boundary tests

Per surviving candidate, answer yes or no, with one line of evidence each. A "no" on any of the five is a blocking failure, not a weakness to compensate elsewhere.

1. **Organization-only.** Is everything on the paid side something a company needs and a solo developer does not? Governance, scale management, guaranteed response, compliance evidence, hosted operation. Anything an individual also wants gets rebuilt upstream.
2. **Defensible without hostility.** Could a motivated contributor build the paid part upstream in a weekend, and would they want to? A boundary that only holds because you refuse pull requests is a fork with a start date.
3. **Observable trigger.** Can someone see the crossing from free need to paid need - a second team, a production deployment, an audit request, a volume threshold, a support escalation? Name the signal and where it is read.
4. **Cost-to-serve covered.** What does one free user cost per month, in currency? What does one paying customer cost? If the free number is unknown, the model is untested.
5. **Licence-compatible.** Does this work with what is already published, with no relicensing? If it needs one, treat it as a separate, irreversible decision with its own approval.

## 3. Scoring sheet

Once a candidate passes all five gates, score it 1-5 on each dimension. Scores never rescue a failed gate, and the total is not the order:

- Value half of the efficiency ratio: willingness to pay, margin, defensibility, expansion.
- Effort-and-cost half: time to first revenue, team fit, community cost.

The ratio is what re-ranks the default order in the skill's step 2 for this specific company. A high total carried by four value dimensions and one on team fit is an expensive model wearing a good score.

| Dimension             | 1                                                        | 5                                                          |
| --------------------- | -------------------------------------------------------- | ---------------------------------------------------------- |
| Willingness to pay    | buyer must be convinced the problem exists               | buyer already budgets for this category                    |
| Time to first revenue | multi-quarter enterprise cycle                           | self-serve within days                                     |
| Margin                | resells infrastructure at thin markup                    | software margin                                            |
| Defensibility         | a permissive competitor removes the need to pay          | switching means re-architecting or losing compliance cover |
| Team fit              | requires a function you do not have and cannot hire soon | uses strengths already on the team                         |
| Community cost        | erodes trust or invites a fork                           | community is neutral or benefits                           |
| Expansion             | flat revenue per customer forever                        | revenue grows as the customer succeeds                     |

Record the two lowest scores as the risks that go into the memo. A candidate winning on total while scoring 1 on team fit is a plan to hire, not a plan to sell.

## 4. Value metric checks

The billed metric should satisfy all four:

- The customer already counts it for their own reasons.
- It grows as the value they receive grows.
- They can forecast it before the invoice arrives.
- You can measure it accurately and explain the measurement in one sentence.

Common breakages:

- Seats on a product driven by automation or agents, where usage rises without headcount.
- Raw infrastructure units the customer cannot map to their own outcomes.
- A metric only you can measure, which turns every invoice into a dispute.

## 5. Never on the paid side

- Basic authentication hardening. Charging for it is the "SSO tax", catalogued at sso.tax (the actively maintained `robchahin/sso-wall-of-shame` list) on the argument that "security shouldn't be a premium feature" and that SSO is "a core security requirement for any company with more than five employees".
- Security patches for the free version. Withholding fixes turns users into adversaries and attracts CVE-driven press.
- Features the community contributed. The most cited cause of a hostile fork in this market.
- Data export and portability. Lock-in read as a trap is punished harder here than in any other B2B segment.

## 6. Reversibility ladder

This ladder sequences the experiments. It does not re-rank the shortlist, which the skill's efficiency order already did. Prefer the reversible experiment first.

- **Reversible in a quarter:** price points, packaging, free-tier limits, adding a hosted option, adding a support tier at the top.
- **Reversible with effort and cost:** opening a previously closed component, entering a cloud marketplace, restructuring the value metric on existing contracts.
- **Effectively irreversible:** any licence change on already-published code, closing a previously open core, and any public promise about what stays free forever.

Irreversible levers have to be pulled early to matter at all, because everything already released stays released. Pull them deliberately, with the fork and procurement consequences written down, or do not pull them.

## 7. Validation experiment per candidate

Every candidate carried into step 2's short-list needs one cheap test with a success criterion and a date, run before the company is rebuilt around the model. Suggestions by archetype:

| Candidate          | Experiment                                                                                                                | Reads as a pass when                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Open core          | Publish the intended boundary as a written statement and offer an early-access paid tier to the largest known deployments | a named organization asks to buy before the modules exist                                  |
| Hosted open source | Waitlist page with an indicative price and a migration promise, promoted to the self-hosting audience                     | signups convert to paid pilots, and the pilots' unit cost lands inside the intended margin |
| Support/LTS        | Sell three paid support contracts by hand at the intended annual price                                                    | all three renew intent at 90 days without custom engineering promises                      |
| Dual licensing     | Add a commercial-licence enquiry page and count inbound over a quarter                                                    | enquiries arrive unprompted from organizations that cannot comply                          |
| Consumption        | Instrument the metric and shadow-bill existing free users for one month                                                   | shadow invoices are within the users' own forecast when shown to them                      |
| Marketplace        | Recruit ten suppliers by hand                                                                                             | buyers install without the platform brokering each match                                   |

An experiment nobody can fail is not an experiment. Write the number that would make you drop the candidate, not only the one that would confirm it.
