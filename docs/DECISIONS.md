# Decisions

*The choices that shaped this build, each with the reason and the thing it costs.
A decision without a recorded reason gets re-litigated; a decision without a
recorded cost gets mistaken for a free win.*

---

## D-01 · Two scores, never one

**Decision.** Attractiveness and right to win travel as separate fields end to
end and are never combined into a displayed number. Conviction and competitive
intensity are third and fourth quantities beside them, not inputs to them.

**Why.** Collapsing them destroys the information the strategist needs. A topic
can be excellent for a strategist — large, early, no proof points — and useless
for a salesperson, because there is nothing to show. One number cannot say that.

**Cost.** No single "best topic" ranking exists, so every list needs a role. The
interface has to carry two visual channels (marker size and marker colour) where
one would have been simpler.

---

## D-02 · Portfolio distance drives the role modes

**Decision.** Role modes are not interface presets. Sales sees L0–L1, presales
L0–L2, strategy L1–L4, because that is what each role can act on.

**Why.** "Only topics with enough internal content to credibly back up" sounds
subjective. It has a computable definition: a delivery link at L0/L1, **and** a
published reference in the vertical, **and** no evidence gap. Enforced in the
read model, so re-sorting a list cannot bypass it.

**Cost.** A salesperson genuinely cannot reach white space, even deliberately.
That is intended and occasionally frustrating.

---

## D-03 · Supporting evidence is typed `SUP`, not `L0`

**Decision.** Certifications, analyst positions, published references and
capability pools are linked, displayed and scored — but excluded from portfolio
distance and from the role filter.

**Why.** Every L0–L4 definition in the requirements baseline describes a
*delivery* capability. Typing a certification L0 would mean any topic in a
regulated vertical scored as a direct sell purely because Orange holds ISO 27001,
which makes portfolio distance meaningless.

**Status.** This is an extension beyond the baseline and is **worth confirming
with Orange.**

---

## D-04 · Arithmetic where arithmetic will do

**Decision.** Counting, publisher diversity, recency, momentum, right-to-win and
market sizing involve no model call. Only strategic relevance, the next action,
the narrative and the competitor comparison do.

**Why.** A model asked to count will occasionally be wrong and always be
unverifiable.

**Cost.** More code than "ask the model", and the rubric prompt has to carry
written anchors because a free 0–100 request compresses every answer into the
middle of the scale.

---

## D-05 · Uncited claims are stripped, not rewritten

**Decision.** A claim that cannot cite evidence is deleted. The model is never
asked to fix it.

**Why.** Asking a model to repair an uncited claim teaches it to attach a
citation at random. The cheapest correct answer to "this claim has no source" is
to delete the claim — the remaining ones are still true.

**Cost.** Thinner output, visibly. What was stripped is listed in the interface
rather than quietly omitted, which makes the thinness obvious — deliberately.

---

## D-06 · Market size is computed, never quoted

**Decision.** Two independent methods published side by side; no headline figure
is ever repeated; where the data will not support a number, none is shown.

**Why.** Press figures originate from paid research, are quoted without
methodology, and frequently conflict by an order of magnitude.

**Cost.** Public administration has no Eurostat enterprise count, so those spaces
are sized from observed procurement only — and some are not sized at all. An
absent number is harder to sell with than a confident wrong one.

---

## D-07 · SQLite, on purpose

**Decision.** One file, no database server.

**Why.** The graph is thousands of nodes, not millions. A single file makes the
replay harness a file copy. The serving profile is read-mostly with one writer.

**Cost.** Concurrent curation would serialise. Nothing in the schema prevents a
move to a server-based store, and section 19 of the Technical Architecture
records what would force one.

---

## D-08 · Competitor sites are tier 4, and may only seed

*Added with the competitor intelligence subsystem.*

**Decision.** A competitor's own website is tier-4 "interested party" evidence
everywhere it is scored. A profile may **explain** a competitor already matched
to a topic, and it may **seed** generation. It may not lift any published score.

**Why.** It is definitionally vendor marketing. SC-09 asserts that vendor-only
evidence scores low, and a subsystem that quietly exempted 1,745 vendor pages
from that rule would have hollowed out the guarantee while leaving the test
passing.

**Alternatives considered.** Making profiles ordinary tier-4 signals (rejected:
65 vendor sites would add a lot of low-tier volume and dilute publisher
diversity), and a new tier between practitioner and interested party (rejected:
requires a new weight set and recalibration of every existing score).

**Cost.** A competitor doing something obvious and new cannot, on its own,
create a topic. It can only point at a cell where the *corpus* is then checked.

---

## D-09 · A refusal is recorded, not worked around

**Decision.** Six competitor sites answer 403 to a declared automated client and
one disallows crawling in robots.txt. A browser User-Agent gets through all of
them. It is not used.

**Why.** The project already handles refusals this way — `config/sources.yaml`
records Ofcom as unwired because it 403s automated clients. Applying a different
standard to competitors because the data is more interesting would be exactly
the kind of quiet inconsistency the rest of the design exists to prevent.

**Cost.** 12 of 65 competitors are unprofiled, including Cisco and Fortinet,
which materially thins the competitive picture on security spaces. The gap is
named per competitor in the Coverage view and counted per topic, so it is visible
rather than silent.

**This is a decision with an owner, not a technical limit.** If Orange decides
the trade is worth making, it is a one-line change.

---

## D-10 · A closed vocabulary needs corroboration

*Added after a defect.*

**Decision.** A vocabulary id supplied by a model is kept only if the term also
appears in the source text. Word boundaries, minimum four characters.

**Why.** Asked for OVHcloud's technologies, the model returned the **first eight
ids of the technology vocabulary in vocabulary order**. Every one was valid, so
closed-vocabulary validation passed all eight. OVHcloud's pages mention 5G zero
times. A list-echo is the characteristic failure of handing a model an
enumeration, and the enumeration is what makes it survive validation.

This is the rule `enrichment` already applies to signal attachment —
*"similarity alone is not evidence"* — applied to the same problem elsewhere.

**Cost.** A genuine capability described in words the vocabulary does not use is
dropped. The cost of a false negative is a thinner profile; the cost of a false
positive is a competitor credited with a capability they never claimed, in front
of a customer.

---

## D-11 · Incomplete is not the same as stale

**Decision.** `topic_briefs.brief_schema` records which section set a brief was
rendered with. A brief missing a section that current briefs carry is reported as
**incomplete**, with its own banner and its own regenerate control, separately
from **stale**.

**Why.** A stale brief was correct when it was built and has been overtaken.
An incomplete brief never carried the section, so no amount of waiting fixes it.
Conflating them hides the more actionable of the two.

**Cost.** A migration, and a version constant that has to be bumped by hand when
a section is added.

---

## D-12 · A failed request must not render as a finding

*Added after a defect.*

**Decision.** Every panel distinguishes "the request failed" from "the answer is
empty", and says which.

**Why.** The competitor pane rendered `!data || entries.length === 0` before
checking `error`. A failed fetch produces `data === null`, so a request that
never completed printed *"No competitor from the register is matched to this
space"* — the most confident possible sentence about the competitive field, at
the exact moment nothing was known about it.

That is this product's core failure mode reproduced inside its own interface,
which makes it worse than an ordinary UI bug.

**Cost.** Three states to design instead of two, on every panel that loads
asynchronously.

---

## D-13 · Generation lenses rotate per cluster

*Added after a latent bug.*

**Decision.** The evidence-lens window is offset by the cluster, not fixed at
zero.

**Why.** `GENERATION_LENSES[index % len(LENSES)]` with three passes over four
lenses meant lenses 0, 1 and 2 fired on every cluster and lens 3 fired on none.
The cross-vertical lens was **unreachable for the entire life of the pipeline**,
and every lens added after it would have been dead on arrival.

**Cost.** None. Each cluster still gets three different lenses; the corpus as a
whole now gets all five.

---

## Open decisions

These need a human and are not engineering tasks.

| Question | Why it matters |
|---|---|
| **Who is the curator?** | 4,832 links are machine-proposed. The first occurrence of each pattern needs a named human, and without one quality drifts. |
| **Is the four-year contract assumption right?** | Tender notices publish a contract's whole value; annualising needs a duration. Every size moves inversely with it. |
| **May a browser User-Agent be used?** | See D-09. Twelve competitor profiles depend on the answer. |
| **What is the refresh cadence?** | Drives connector design and cost more than any other choice. Currently a 14-day period, which is also the unit the lifecycle counts in. |
| **Do internal taxonomies exist?** | The 59 use cases and 38 technologies are a drafted Sprint 0 deliverable and should be replaced if an internal catalogue exists. |
| **Terms of use** | Unconfirmed for several enabled sources. A Sprint 0 blocker, not a runtime concern. |
