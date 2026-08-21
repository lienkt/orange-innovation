# -*- coding: utf-8 -*-
"""Per-slide speaker notes, transcribed from the recorded walkthrough and
extended with the material that is on the slide but was compressed on the day.

`dur` is the elapsed time of that slide in the recording; `end` is the running
clock when it finishes.  Slides 9-15 were delivered as a live application demo,
so their share of the 147-second demo block is apportioned by narration."""

SLIDES = [
# ---------------------------------------------------------------- 1
dict(n=1, section="OPENING", title="Opportunity Spaces / Innovation Radar",
     onscreen="Title slide — Orange Business, subtitle, and the one-line promise.",
     dur=20, end=20,
     say=[
"This is the **Orange Business Innovation Radar** — a working prototype, built against the requirements baseline.",
"It maintains a regularly refreshed view of **specific innovation opportunities**. Each one is scored on how attractive it is, how urgent the window is, and how strong Orange's right to win is.",
"[Set expectations] I'll take about ten minutes, in three parts: the concepts the product rests on, what it does, and how it is built. There's a running system behind every number you'll see.",
     ],
     advance="ADVANCE TO SLIDE 2  —  “The problem is not a shortage of information”"),
# ---------------------------------------------------------------- 2
dict(n=2, section="WHY", title="The problem is not a shortage of information",
     onscreen="Rejected topics on the left (“AI”, “Cloud”, “Cybersecurity”) against one real topic on the right.",
     dur=28, end=48,
     say=[
"The problem this solves is **not a shortage of information** about technology.",
"The information that exists is generic, undated, unsourced — and disconnected from what Orange can actually sell.",
"So “AI”, “cloud” and “cybersecurity” are **rejected as topics**. They fail validation. [point at the left column]",
"A real topic reads like this: **private 5G plus edge vision for safety compliance in mining**. Specific enough to open a customer meeting with.",
"That is the bar the whole product is built to clear — the join between an external signal and an internal asset, at a level of specificity a salesperson can use in a meeting on Thursday.",
     ],
     advance="ADVANCE TO SLIDE 3  —  “An opportunity space is a triple”"),
# ---------------------------------------------------------------- 3
dict(n=3, section="CONCEPT", title="An opportunity space is a triple",
     onscreen="Manufacturing × OT/ICS security × SIEM and SOAR, with the rendered statement underneath.",
     dur=27, end=75,
     say=[
"So — an opportunity space is a **triple**: a vertical, times a use case, times a technology.",
"The triple is the **identity**. It gives deduplication and filtering, and it is what makes a topic **recur** across refreshes rather than being recreated each time. That is what makes momentum measurable.",
"The human-readable statement underneath is a **rendering** of that triple. Both are stored.",
"And a candidate that does not resolve to exactly one vertical, one use case and one technology **fails validation automatically**.",
     ],
     advance="ADVANCE TO SLIDE 4  —  “Two scores, never one”"),
# ---------------------------------------------------------------- 4
dict(n=4, section="CONCEPT", title="Two scores, never one",
     onscreen="Three columns: Attractiveness, Right to win, Conviction — with their components listed.",
     dur=37, end=112,
     say=[
"Every topic carries **two scores that are never combined**.",
"**Attractiveness** asks whether the world is moving. It is computed from external evidence alone.",
"**Right to win** asks whether we can play and whether we can win. It is computed from a curated graph of Orange's offers, references, partners and certifications — as **named query results**, never asserted by a language model.",
"Collapsing them into one number would destroy the information the strategist needs. [beat] A topic can be excellent for a strategist — large, early, no proof points — and useless for a salesperson, because there is nothing to show.",
"There is a third quantity, **conviction** — what our own people believe. It adjusts what surfaces first for each role, and it never touches the other two.",
     ],
     advance="ADVANCE TO SLIDE 5  —  “Evidence before generation”"),
# ---------------------------------------------------------------- 5
dict(n=5, section="CONCEPT", title="Evidence before generation",
     onscreen="Four numbered defences, plus the adversarial critic panel at the foot.",
     dur=41, end=153,
     say=[
"The model **never invents a topic** out of its own knowledge. Four defences enforce that.",
"**One — evidence binding.** Every claim must cite signal identifiers that exist in the cluster that produced it. Uncited claims are **stripped, not rewritten** — asking a model to repair a claim just teaches it to attach a citation at random.",
"**Two — closed vocabulary.** Taxonomy values are validated against the enumerations. A recognised synonym is repaired once; anything else is dropped.",
"**Three — no generated numbers.** Market sizes are looked up and attributed, or they are absent. It is backstopped by a regex over every generated sentence.",
"**Four — an entailment check.** A second pass verifies each claim is genuinely entailed by the span it cites.",
"And on top of all four, an **adversarial critic** — a separate prompt that scores one to five as the **minimum** across five tests, so a single failure caps the whole score. In the live run it rejected **345 of 644 candidates**, each with a written reason.",
     ],
     advance="ADVANCE TO SLIDE 6  —  “Portfolio distance”"),
# ---------------------------------------------------------------- 6
dict(n=6, section="CONCEPT", title="Portfolio distance decides whose conversation it is",
     onscreen="The L0–L4 ladder, each rung with its owner and its verb.",
     dur=34, end=187,
     say=[
"**Portfolio distance** is the most decision-relevant number in the product. It is the shortest path from a topic to something Orange could **actually deliver**.",
"**L0** means an existing offer already addresses it as it stands. That is a sales conversation — sell it.",
"**L2** needs a capability a partner already holds — presales and alliances assemble it.",
"**L4** is white space: no plausible path from the current portfolio at all.",
"And this is what drives the **role modes** — they are not arbitrary interface presets, they fall out of this ladder.",
"A high-attractiveness **L4** topic is exactly the strategist's innovation agenda — and exactly what a salesperson should never be shown.",
     ],
     advance="ADVANCE TO SLIDE 7  —  “What the MVP has actually produced”"),
# ---------------------------------------------------------------- 7
dict(n=7, section="STATUS", title="What the MVP has actually produced",
     onscreen="Five headline figures, then four supporting lines on coverage and evidence quality.",
     dur=29, end=216,
     say=[
"Here is what the prototype has actually produced — and every figure on this slide is **read live from its database**, not typed into the deck.",
"**174 opportunity spaces**, from four and a half thousand signals, gathered across **18 live sources**, joined to **2,000 named asset links**.",
"**14 of the 15 verticals** are covered.",
"And the corpus carries around **500 French-language signals** — so the anglophone bias that was named as a principal risk is **measured, rather than assumed**.",
     ],
     numbers=["174 opportunity spaces  ·  4,658 signals ingested, 2,064 through the gate  ·  18 live sources of 25 catalogued",
              "2,007 asset links over 181 graph nodes  ·  12.3 signals per topic after enrichment",
              "3,422 tier-1 signals  ·  37 of 59 use cases and 28 of 38 technologies appear in at least one topic",
              "174 sized  ·  174 competition-scored  ·  62 with a sales brief"],
     ifasked=[("“Why is the grid so sparse?”", "Deliberately. Most cells in a 15 × 59 × 38 grid **should** stay empty — a topic only exists where evidence puts it.")],
     advance="ADVANCE TO SLIDE 8  —  “Sizing and competition”"),
# ---------------------------------------------------------------- 8
dict(n=8, section="CONCEPT", title="Sizing and competition, with the working shown",
     onscreen="Two panels — bottom-up market size on the left, competitive intensity on the right.",
     dur=41, end=257,
     say=[
"Two further questions a topic cannot be acted on without: **how big is it**, and **who else is already there**.",
"Headline market figures in the press come from paid research, are quoted without methodology, and often conflict by an order of magnitude.",
"So the radar builds **its own estimate, bottom up** — enterprise counts by sector and size class, times an observed adoption rate, times a plausible contract value — and it **shows its working**, with a method and a confidence label attached. You can reject the number on its arithmetic.",
"**Competitive intensity** is scored against a versioned competitor register, against the evidence actually collected — who is visibly playing here.",
"And a crowded field is **not a reason to walk away**. It is a reason to win on a specific differentiator.",
"[If you have time] One detail worth naming: “no competitor found” is reported as **unverified**, not as empty — because it may only mean the register has a gap.",
     ],
     advance="ADVANCE TO SLIDE 9  —  the radar view. THE DEMO SECTION STARTS HERE."),
# ---------------------------------------------------------------- 9
dict(n=9, section="FUNCTIONALITY", title="The radar view", demo=True,
     onscreen="Screenshot of the polar radar. In the recording this was a live application demo.",
     dur=40, end=297,
     say=[
"Here is the **running application**. The radar is the signature view.",
"**Angular sectors** are the six business domains. **Distance from the centre** is the time horizon — Now at the middle, Later at the rim.",
"**Marker size** is attractiveness and **marker colour** is right to win — so the two questions the radar exists to answer are visible at the same time, without a legend anyone has to study.",
"Position already carries identity, which is what frees colour to encode a quantity.",
"A marker with an **exclamation mark** carries an evidence gap — it means Orange has few published references in that vertical. [point at one]",
"And switching role changes the **ranking function**, not just a filter. Sales sees only topics with a delivery path, a published reference in the vertical, and no evidence gap — which is why the count drops when you switch. [switch the role selector]",
     ],
     advance="ADVANCE TO SLIDE 10  —  the role-ranked list"),
# ---------------------------------------------------------------- 10
dict(n=10, section="FUNCTIONALITY", title="Role-ranked list", demo=True,
     onscreen="Screenshot of the list view with the per-row score columns.",
     dur=11, end=308,
     say=[
"The **list view** shows the same topics, ranked for the selected role — with attractiveness, right to win, horizon, portfolio distance and the number of supporting signals on every row.",
"Three genuinely different rankings, not three filters: the **strategist** ranks on attractiveness and novelty and ignores right to win; **sales** ranks on right to win and proof-point density; **presales** ranks on differentiation.",
     ],
     advance="ADVANCE TO SLIDE 11  —  topic detail"),
# ---------------------------------------------------------------- 11
dict(n=11, section="FUNCTIONALITY", title="Topic detail", demo=True,
     onscreen="Screenshot of the detail pane, with the cited-claim chips visible.",
     dur=24, end=332,
     say=[
"Opening a topic gives the **detail pane**.",
"Every claim under **“why it is hot now”** is bound to the signal identifiers that support it, and each chip links out to the **original dated source**. [click one]",
"Further down, **can we play / can we win** is itemised against **named Orange assets** — a specific offer, a specific certification, a specific partner tier.",
"Never an aggregate assertion that Orange has relevant capabilities. That distinction is the whole point.",
     ],
     advance="ADVANCE TO SLIDE 12  —  “How this score was calculated”"),
# ---------------------------------------------------------------- 12
dict(n=12, section="FUNCTIONALITY", title="How this score was calculated", demo=True,
     onscreen="Screenshot of the score-explanation modal.",
     dur=29, end=361,
     say=[
"Now the part that makes the scoring **defensible**.",
"Every topic has a **“How was this calculated”** panel. It shows the weight table and the weighted total — and then, per component, the **actual stored inputs**:",
"the publishers counted and their entropy; the tier distribution; the per-period buckets the momentum slope was fitted to; the rubric level and its written rationale.",
"This is how a reviewer **outside the project** can reconstruct why a topic holds its rank. [beat] The governing constraint was: if a user cannot explain why a topic ranks where it does, the scoring is not good enough.",
     ],
     advance="ADVANCE TO SLIDE 13  —  the stage gate"),
# ---------------------------------------------------------------- 13
dict(n=13, section="FUNCTIONALITY", title="Stage gate and role assessment", demo=True,
     onscreen="Screenshot of the workflow board — Shortlisted, Demand-tested, Packaged, Live.",
     dur=18, end=379,
     say=[
"The **workflow board** implements the stage gate. A topic moves from Shortlisted, through Demand-tested and Packaged, to Live — and **ownership follows the stage**. Stalled cards are flagged, because latency is the known weakness of a stage gate.",
"Each role assesses **only the axis it owns**: sales rates customer demand, presales rates deliverability — on a **0 to 5 scale with written anchors**, because people are unreliable at rating something 73 out of 100.",
     ],
     advance="ADVANCE TO SLIDE 14  —  analytics"),
# ---------------------------------------------------------------- 14
dict(n=14, section="FUNCTIONALITY", title="Analytics", demo=True,
     onscreen="Screenshot of the analytics tab — heatmap, funnel, divergence chart.",
     dur=19, end=398,
     say=[
"The **analytics view** visualises the whole corpus.",
"The **heatmap** is vertical by domain — and the empty cells are the white space.",
"The **diverging chart** shows where the team and the evidence disagree. That is a **review queue**, because disagreement is information rather than friction.",
"[If asked about the charts] Each chart is chosen by the job the data does: sequential for magnitude, diverging with a neutral midpoint for polarity, ordinal for the funnel. Only the signal-type mix is categorical, and it ships a legend **and** a table.",
     ],
     advance="ADVANCE TO SLIDE 15  —  contextual help"),
# ---------------------------------------------------------------- 15
dict(n=15, section="FUNCTIONALITY", title="Contextual help", demo=True,
     onscreen="Screenshot of a help dialog. Short slide — this was one sentence in the recording.",
     dur=6, end=404,
     say=[
"And throughout, **every dense concept explains itself** — with a pointer back to the requirement it comes from, so the answer is checkable rather than merely confident.",
     ],
     advance="ADVANCE TO SLIDE 16  —  the pipeline. END OF THE DEMO SECTION."),
# ---------------------------------------------------------------- 16
dict(n=16, section="ARCHITECTURE", title="Seven pipeline stages, each with a contract",
     onscreen="The stage chain, with the Orange Business Graph as a parallel path underneath.",
     dur=28, end=432,
     say=[
"Architecturally, this is **seven pipeline stages**, each with a defined input and output contract — so they can be developed, tested and replaced independently.",
"Collect, normalise, classify, cluster into themes, synthesise candidates, enrich them with further evidence, score — and serve.",
"A **parallel, slower path** maintains the Orange Business Graph — offers, references, partners with tiers, certifications, analyst positions, capability pools. It **joins at the scoring stage**, so right to win can be improved without re-running discovery.",
"[If asked about speed] Collection runs in parallel — twelve sources in about forty-five seconds — while database writes stay serial, because deduplication is a read-modify-write over the whole signal table.",
     ],
     advance="ADVANCE TO SLIDE 17  —  the stack"),
# ---------------------------------------------------------------- 17
dict(n=17, section="ARCHITECTURE", title="Stack and separation of concerns",
     onscreen="Three columns — Ingestion, Intelligence, Serving — with the configuration note beneath.",
     dur=37, end=469,
     say=[
"The stack is **deliberately unremarkable**, because the value is in the schema and the curation rather than the infrastructure.",
"**19 connectors** feed a signal store — procurement portals, regulators, standards bodies, research, news in English and French.",
"**DeepSeek** sits behind a provider-agnostic client, so switching to a **sovereign, local model** is an environment variable rather than a rewrite. Embeddings already run locally.",
"The graph is **thousands of nodes, not millions**, so SQLite is entirely adequate. A FastAPI read API, and a React front end with a hand-drawn SVG radar — no chart library, because the encoding is specific to this product.",
"And taxonomies, weights, thresholds, sources and the crosswalks are all **configuration, not code** — validated at load time, so a dangling identifier is a **startup error** rather than a wrong number three stages later.",
     ],
     advance="ADVANCE TO SLIDE 18  —  what makes the numbers defensible"),
# ---------------------------------------------------------------- 18
dict(n=18, section="ARCHITECTURE", title="What makes the numbers defensible",
     onscreen="Six guarantees: decomposable, reproducible, traceable, versioned, auditable, bounded.",
     dur=35, end=504,
     say=[
"That gives **six guarantees** about the numbers.",
"**Decomposable** — every displayed score breaks into named components. No opaque scores.",
"**Reproducible** — every component stores the inputs used to compute it, so any number can be re-derived.",
"**Traceable** — lineage runs from a displayed claim all the way back to the raw ingested item, including prompt and model version.",
"**Versioned** — every score records its weight set, so trajectories are never plotted across an incomparable boundary.",
"**Auditable** — a reviewer outside the project can reconstruct why any topic holds its rank.",
"And **bounded** — counting, diversity, recency and momentum are **arithmetic, never a model**. A model asked to count is occasionally wrong and always unverifiable.",
     ],
     advance="ADVANCE TO SLIDE 19  —  what is not built"),
# ---------------------------------------------------------------- 19
dict(n=19, section="STATUS", title="What is deliberately not built — and what needs a decision",
     onscreen="Two columns: not built with the reason, and four open decisions for Orange.",
     dur=37, end=541,
     say=[
"Finally — what is **deliberately not built**, and what needs a decision from Orange.",
"There is no CRM integration, and **no learned scoring model**, because no labels exist on day one. The capture-and-replay harness ships instead, so the labels can start accumulating now.",
"And where the data will not support a figure, **no market size is shown at all**, rather than a wrong one.",
"Four things need a human. [count them off]",
"**One** — 2,000 links are machine-proposed and **unconfirmed**. Who is the curator?",
"**Two** — there is **no agriculture vertical**, so agri topics are currently being forced into four others.",
"**Three** — **terms of use** are unconfirmed for ten enabled sources. That is a Sprint 0 blocker.",
"**Four** — the **refresh cadence** is still undecided, and it drives connector design and cost more than any other choice.",
"The point to take from this slide is that the radar **surfaces its own gaps** rather than hiding them.",
     ],
     advance="ADVANCE TO SLIDE 20  —  the close"),
# ---------------------------------------------------------------- 20
dict(n=20, section="CLOSE", title="The join is the product",
     onscreen="Closing statement, with the four headline figures repeated underneath.",
     dur=17, end=558,
     say=[
"The **join** between an external signal and an internal asset **is the product**.",
"Without it, this is a competent trend feed — and trend feeds already exist.",
"With it, the radar answers a question **nobody else can answer for Orange**.",
"[Stop. Hold the slide and take questions.]",
     ],
     advance="END OF DECK  —  hold this slide and take questions",
     terminal=True),
]
