# Orange Business — Opportunity Spaces / Innovation Radar

MVP implementation of the requirements baseline in
[`docs/Orange_Innovation_Radar_Requirements_and_Approach.docx`](docs/).

An opportunity space is **Vertical × Use Case × Technology** with a human-readable
statement. Each one carries two scores that are never combined: **attractiveness**
("is the world moving") and **right to win** ("can we play, can we win"), plus
**conviction** ("do our own people believe it") and **competitive intensity**
("how crowded is the field") as separate quantities beside them. Each also carries
a **market size** computed bottom-up from published statistics, a written
description bound to its own evidence, and a **PDF brief** a salesperson can take
into a meeting. Every claim is bound to a dated, attributable source, and every
number decomposes into named components.

Section references below (§4.5.3, SC-13, FR-30 …) point at the requirements
document. They are also carried in the code as comments, so any given behaviour
can be traced back to the requirement that asked for it.

---

## Quick start

```bash
# 1. Python deps
pip install -r requirements.txt

# 2. Configure the LLM provider and contact address
cp .env.example .env        # then fill in DEEPSEEK_API_KEY

# 3. Check the config and vocabularies load
PYTHONPATH=src python3 -m radar.cli check

# 4. Run the pipeline end to end. Collection is parallel (~45s for 12 sources,
#    plus up to 11 min if GDELT is rate-limiting); synthesis dominates the rest.
PYTHONPATH=src python3 -m radar.cli refresh --since-days 60

# 5. Serve the read API
PYTHONPATH=src python3 -m radar.cli serve            # → http://127.0.0.1:8000

# 6. Serve the React frontend (separate terminal)
npm --prefix frontend install
npm --prefix frontend run dev                        # → http://localhost:5173
```

The pipeline can also be run stage by stage, which is how you iterate:

```bash
PYTHONPATH=src python3 -m radar.cli refresh --stages collect,classify
PYTHONPATH=src python3 -m radar.cli refresh --stages themes
PYTHONPATH=src python3 -m radar.cli refresh --stages synthesise --max-clusters 8
PYTHONPATH=src python3 -m radar.cli refresh --stages graph,link,score,actions
PYTHONPATH=src python3 -m radar.cli refresh --stages reference,size,competition
PYTHONPATH=src python3 -m radar.cli refresh --stages describe
```

Useful commands:

| Command | What it does |
|---|---|
| `radar check` | Validate config, print vocabulary sizes, flag unconfirmed source terms |
| `radar topics --role sales` | Role-ranked topic list (FR-13) |
| `radar show OS012` | Full decomposition: claims, sources, links, score breakdown (NFR-01) |
| `radar whitespace` | High attractiveness, no portfolio path (FR-32) |
| `radar orphan-offers` | Offers with no live topic — portfolio decay (FR-33) |
| `radar coverage` | Language / geography / tier coverage (NFR-08) |
| `radar replay --date 2024-06-01` | Historical replay with leakage controls (FR-35) |
| `radar confirm-link <pattern> --decision confirmed --curator x` | Curator link decision (LK-06) |
| `radar reference-data` | Fetch the Eurostat denominators market sizing needs (§4.3.4) |
| `radar size` | Compute market size per opportunity space, both methods (§4.3.4) |
| `radar competition` | Assess competitive intensity per space (§4.3.3) |
| `radar describe --limit 40` | Write the long-form descriptions and solution diagrams (FR-14) |
| `radar brief OS012 --open` | Render the sales/presales PDF brief (FR-18) |

---

## Architecture

Seven pipeline stages with defined input/output contracts (§4.2, Table 16), so
stages can be developed, tested and replaced independently.

```
 1 Collect      connectors/          source config      → raw items
 2 Normalise    pipeline/ingest.py   raw items          → signal records
 3 Classify     pipeline/ingest.py   signals            → typed, tiered signals
 4 Themes       pipeline/themes.py   signals            → theme clusters
 5 Synthesise   pipeline/synthesis   clusters+taxonomy  → candidate spaces
 5b Enrich      pipeline/enrich.py   topics + signals   → more evidence per topic
 6 Curate+score synthesis/graph/scoring                 → ranked spaces
 6b Size        reference.py, sizing.py                 → market size per space
 6c Compete     competition.py                          → competitive intensity
 6d Describe    pipeline/describe.py                    → narrative + diagram spec
 7 Serve        readmodel.py, api.py, brief.py          → radar, briefs, PDF, API
```

A parallel, slower path maintains the **Orange Business Graph** (offers,
references, partners, certifications, analyst positions, capabilities). It joins
at stage 6, so right-to-win can be improved without re-running discovery.

```
src/radar/
  config.py       controlled vocabularies, crosswalks, validation-at-load
  db.py           SQLite schema — carries DR-01…DR-15 directly
  llm.py          provider-agnostic client (deepseek | openai | ollama | mock)
  embeddings.py   local sentence-transformers, TF-IDF fallback
  graph.py        business graph + L0–L4 linking + portfolio distance
  reference.py    Eurostat reference series (enterprise counts, adoption rates)
  sizing.py       bottom-up and procurement-observed market size, factor by factor
  competition.py  named competitors, evidence matching, NONE/LOW/MEDIUM/HIGH
  brief.py        the sales/presales PDF, including the solution diagram
  scoring.py      5 attractiveness components, right-to-win, horizon, lifecycle
  workflow.py     stage gate, per-role assessment, conviction, divergence
  readmodel.py    role-specific ranking, filtering, white space, coverage
  api.py          FastAPI read API
  cli.py          command line
  connectors/     13 sources: ted, boamp, eurlex, have-your-say, gdelt, news RSS
                  (EN/FR), hacker news, openalex, arxiv, cordis, nist, cert-fr
  pipeline/       ingest, themes, prompts, synthesis, actions, run
frontend/         React + Vite + TypeScript; polar radar, workflow board,
                  analytics charts, topic detail, filters
config/           taxonomies, weights, sources, business graph, crosswalks
```

### Configuration, not code (NFR-11)

Nothing in the package hard-codes a vertical, a weight or a threshold. All of it
lives in `config/` and is validated at load time — a dangling id is a startup
error, not a runtime surprise, because §4.5.2 warns that crosswalk errors
propagate silently into every downstream number.

| File | Contents |
|---|---|
| `config/taxonomy/*.yaml` | 15 verticals, 59 use cases, 38 technologies, 6 domains, 9 personas, 6 signal types |
| `config/settings.yaml` | Weight set, thresholds, lifecycle, horizon, curation |
| `config/strategy.yaml` | *Trust the future* ambitions — the strategic-relevance rubric |
| `config/sources.yaml` | Source catalogue (25 catalogued, 19 wired) with terms-of-use position |
| `config/source_tiers.yaml` | Four-tier scheme + publisher overrides |
| `config/business_graph/*.yaml` | Offers, references, partners, certifications, capabilities |
| `config/crosswalks/*.csv` | CPV → vertical / use case, vertical → NACE, technology → adoption series; versioned, confidence per row |
| `config/sizing.yaml` | Sizing scope, datasets, contract-value rules, uncertainty bands, share assumptions |
| `config/business_graph/competitors.yaml` | 65 named competitors with type, aliases and partner relationship |
| `config/role_modes.yaml` | Per-role ranking functions and link-type filters |

**Changing any weight requires a new `weight_set` id.** Scores across a version
boundary are not comparable, every score records the set that produced it
(SC-10), and the UI refuses to plot a trajectory across the boundary silently
(§4.6 calibration-drift guard).

---

## How the requirements are met

### Evidence before generation (§4.1)

The model never invents an opportunity space from its own knowledge. Four
hallucination defences, in the document's order of effectiveness (§4.4.4):

1. **Evidence binding** — every claim cites signal ids, validated to exist *in
   the cluster that produced the candidate*. Uncited claims are **stripped, not
   rewritten**.
2. **Closed-vocabulary output** — taxonomy values validated against the
   enumerations; a recognised synonym is repaired once, anything else is dropped.
3. **No model-generated numbers** — enforced in every system prompt and
   backstopped by a regex over generated claims.
4. **Entailment check** — a cheap second pass verifies each "why hot" claim is
   entailed by its cited span.

Plus an **adversarial critic pass** with a different system prompt (§4.4.3),
which in the live run rejected 119 of 254 candidates with specific reasons.

### Prolonged brainstorming, made systematic (§4.4.3)

All three mechanisms the document asks for are implemented:

* **Coverage-driven prompting.** The pipeline computes which taxonomy cells have
  evidence but no candidate yet and targets generation at exactly those. "This
  converts brainstorming from 'produce more ideas' into 'cover the evidenced
  grid', which terminates and is measurable."
* **Diversity by construction.** Each cluster is passed over
  `candidates_per_cluster` times at temperature 0.85, and each pass is given a
  different **evidence lens** — regulatory, procurement, technology-maturity,
  cross-vertical. §4.4.3 warns that an open-ended loop "elaborates around
  whatever it produced first", so passes need different starting points to
  explore rather than paraphrase. Passes and clusters both run concurrently.
* **Adversarial critique.** A separate critic prompt scores 1–5 as the *minimum*
  across five tests, so one failure caps the whole score.

The funnel over 27 clusters, live:

```
254 raw candidates          (27 clusters × 3 lensed passes)
  6 failed closed vocabulary
  7 failed evidence binding
119 failed the critic
 15 claims stripped by the entailment check
 62 merged as duplicates    ← multi-pass overlap, caught by triple + embedding
 60 accepted
```

That is a 24% yield, close to the document's "generate forty candidates and keep
eight". The 62 merges are the cost of over-producing and are exactly what the
canonical-triple identity rule (§4.4.5) exists to absorb.

### Two scores, never one (SC-12)

Attractiveness and right-to-win travel as separate fields end to end. In the UI
they occupy two different visual channels (marker size and marker colour) and
are never combined into a displayed number.

### Role modes fall out of the data (§4.5.3, FR-31)

Sales sees L0–L1, presales L0–L2, strategy L1–L4. The sales acceptance criterion
("only topics with enough internal content to credibly back up") has a
**computable** definition: a delivery link at L0/L1 **and** a published reference
in the vertical **and** no evidence gap.

**One deliberate extension beyond Table 26.** Every L0–L4 definition describes a
*delivery* capability. A certification, an analyst position, a published
reference and a capability pool are none of those — they are right-to-win
evidence. Typing them L0 would mean any topic in a regulated vertical scored as
a direct sell purely because Orange holds ISO 27001, which makes portfolio
distance meaningless. They are therefore typed `SUP` (supporting evidence):
linked, displayed and scored, but excluded from portfolio distance and from the
role-mode filter. See `graph.SUPPORTING`. **This is a design decision worth
confirming with the client.**

### Explainability (NFR-01, NFR-02, NFR-03)

Every score component stores the inputs that produced it (DR-05), so any number
is reproducible. Every artefact records pipeline, prompt and model version
(DR-10). Every link records its type, confidence, the evidence that justified it
and the confirming curator (DR-13). The topic detail view shows the breakdown
expanded rather than behind a tooltip, per §4.9.

### Evidence enrichment (§4.4.5)

Synthesis only attaches a signal to a topic when the model happens to cite it.
That left a gap: a topic created six weeks ago stayed frozen at the evidence it
was born with, even when a later refresh ingested signals that plainly belonged
to it. Thin evidence is not cosmetic — it suppresses a topic through the whole
chain, because signal volume, publisher diversity, momentum and the promotion
thresholds all count attached signals.

The `enrich` stage closes that gap, and does so as retrieval plus rules rather
than generation: embedding similarity **plus** an independent taxonomy
corroboration (a vocabulary term in the signal text, or a CPV crosswalk hit).
Similarity alone is refused, because embeddings happily rate two unrelated
security items as close and unchecked attachment would inflate exactly the
components that depend on the count. Enrichment never writes a claim — only
synthesis may do that, and only with citations.

### Collaboration workflow and team conviction (FR-25, §4.10)

§4.10 recommends "A + B + D, with C as a fast follower". Models A and C are
implemented, because they are the two that touch scoring.

**Model A — the stage gate.** Shortlisted → Demand-tested → Packaged → Live,
with ownership following the stage (strategist → sales → presales). §4.10's
named weakness is latency — "a topic can die waiting for a stage owner" — so
age-in-stage is computed and stalled cards are flagged rather than left for
someone to notice. Every transition records who moved it and why.

**Model C — distributed assessment.** Each role rates **only its own axis**:

| Role | Axis | Because |
|---|---|---|
| Strategist | Strategic fit | Owns where investment goes |
| Sales | Customer demand | Authoritative on whether customers are asking |
| Presales | Deliverability | Knows what it would actually take to build |

Ratings are 0–5 with **written anchors** per level, plus a separate confidence,
rather than a slider. §4.7.4: "People are unreliable at rating a topic 73 out of
100." Ratings are confidence-weighted, and a changed mind supersedes rather than
duplicates — the earlier opinion is kept, because a changed mind is itself a
label.

**How this affects scoring, and the line it does not cross.** Conviction is a
**third quantity**, never folded into either published score:

```
attractiveness   is the world moving          (external evidence)
right to win     can we play, can we win      (internal assets)
conviction       do our own people believe it (internal judgement)
```

SC-14 says internal data "adjusts but does not replace external discovery" and
SC-12 forbids collapsing scores, so conviction enters only the per-role
**ranking** function — which already exists to order a list and is never
displayed as a score. Every published number stays reproducible from evidence
alone. An unrated topic sits **neutral**, not last: treating "nobody has looked
yet" as "everybody hates it" would be a popularity bias, not a judgement.

**Divergence is the product.** §4.10: "disagreement becomes information rather
than friction." Where team conviction and the evidence-derived score disagree by
more than the configured threshold, the topic enters a review queue with a
written reading of what the gap might mean — either the radar is missing signal,
or enthusiasm is running ahead of it. It is flagged, never averaged away.

### Explaining a score, per topic

NFR-03 asks that "a reviewer outside the project can reconstruct why any topic
holds its rank", and DR-05 stores every component alongside the inputs used to
compute it precisely so that is possible. Every topic therefore carries a **How
was this calculated?** modal that shows the stored inputs and the arithmetic —
the weight table, the weighted total, and per component the actual evidence:
publisher entropy and the publishers counted, the tier distribution, the
per-period signal buckets the momentum slope was fitted to, the rubric level and
its rationale, the named offers and references behind right-to-win.

It is reachable from the topic detail, from every list row, and from the workflow
board, and it deep-links: `?explain=OS021`.

The same surface carries the reproducibility stamps — weight set, pipeline,
prompt and model version — because a number you cannot re-derive is not
explained, only displayed.

### Contextual help

Every dense concept in the interface has a `?` that opens an explanation of what
it is, why it works that way, and which requirement it comes from: portfolio
distance, conviction, divergence, evidence gap, source tiers, horizons, the
lifecycle, the exploration slot, weight sets. Content lives in one registry
(`frontend/src/help.ts`) rather than scattered through components. The dialogs
are real dialogs — Escape and backdrop close them, focus moves in and returns to
the trigger.

### Charts

Every chart picks its colour by the **job the data does**, not by taste, and all
palette values are taken verbatim from the reference instance in its documented
slot order — the order is the colourblind-safety mechanism, so nothing is
re-stepped or re-ordered.

| Chart | Data's job | Encoding |
|---|---|---|
| Radar (polar) | four dimensions at once | position + area + sequential hue |
| Vertical × domain heatmap | magnitude on a grid | sequential, **blue** — orange already means right-to-win, and reusing it would imply the same quantity |
| Conviction vs evidence | polarity | **diverging**, two poles + a neutral grey midpoint, so agreement reads as nothing |
| Stage funnel | position in a sequence | ordinal ramp — the reader sees the order in the colour |
| Portfolio distance | ordered buckets | ordinal ramp |
| Evidence over time | change over time | single hue; this is the series momentum is the slope *of* |
| Signal-type mix | identity — the series ARE the subject | the only categorical chart, ≤6 slots, with a legend **and** a table view (three light-mode slots sit below 3:1, so the relief rule applies) |
| KPI row | headline numbers | no chart at all |

### Market size, with the working shown (§4.3.4)

§4.3.4 is a warning before it is a requirement:

> the headline market-size figures circulating in press coverage almost always
> originate from paid research houses, are quoted without methodology, and
> frequently conflict by an order of magnitude. The radar should prefer a
> transparent bottom-up estimate — enterprise count in the vertical × adoption
> rate × plausible contract value — and show its working.

So every space carries a size that is **computed, never quoted**, by two
independent methods that are published side by side:

| Method | What it is | Where each factor comes from |
|---|---|---|
| **Bottom-up** | enterprises × adoption × annual engagement value | Eurostat SBS (`sbs_sc_ovw`), Eurostat enterprise ICT survey, median matching TED tender |
| **Observed tenders** | contracts that actually exist, annualised | TED notices whose CPV resolves to the space |

Two methods rather than one is the point: figures built from different data that
land in the same order of magnitude are an argument, and a figure with no method
is not. TAM is every adopter; **SAM is computed**, not discounted by a fudge
factor — the same estimate restricted to the size classes and geographies Orange
serves; SOM is the one genuinely modelled number, a share assumption anchored on
right-to-win and portfolio distance and labelled as such everywhere it appears.

Four decisions in that pipeline were load-bearing enough to be worth naming:

* **The denominator and the adoption rate must share a base.** Eurostat
  publishes enterprise ICT adoption for firms with 10+ employees only. Multiplied
  by an all-sizes enterprise count — roughly 90% micro-firms — every estimate
  would have been out by an order of magnitude.
* **The contract value has to come from the right kind of contract.** The CPV
  crosswalk says what a notice is *about*; it does not say whether it is the kind
  of contract Orange would bid for. A €188m hydroelectric turbine retrofit,
  correctly crosswalked to industrial asset management, was setting the price of
  a zero-trust deployment until eligibility was tested on the notice's **main
  object** rather than any of its lots.
* **A public tender is a large-organisation contract.** Applied flat it prices a
  twelve-person manufacturer's project at a ministry's budget, so engagement
  value is scaled per size class, anchored on the class the observed contracts
  came from. The weights are an assumption with an owner, printed in the brief.
* **Proxies widen the range; they never move the base.** The enterprise ICT
  survey measures cloud, AI, IoT and security practice well and enterprise
  connectivity not at all, and it excludes finance, health, public administration
  and mining outright. Where a series has to stand in for another, the substitution
  is declared, the uncertainty band widens from ±15% to ±40%, and the confidence
  grade drops.

The confidence grade — `observed`, `partial`, `modelled` — is the **worst** basis
among the factors, never an average, because an estimate is exactly as good as
its weakest input. Where nothing attributable exists, no number is published:
public administration has no enterprise count in Eurostat at all, so those spaces
are sized from observed procurement only.

Reference data lives in its own tables, not in `signals`. An annual statistical
series has no publisher diversity, no momentum and no relevance; pushing 56,000
Eurostat cells through the signal store would corrupt every component that counts
attached signals while adding nothing to discovery.

### Competitive intensity (§4.3.3)

§4.3.3 puts competition on the right-to-win side — "contract award notices
additionally reveal who is winning" — and Table 27 lists award concentration
among competitors as a procurement feature. Each space carries a level of
**NONE / LOW / MEDIUM / HIGH** over a named list, and the two are never conflated:
a level with no names is an opinion, and the names with their evidence are what a
salesperson can use and a colleague can correct.

Two kinds of presence are distinguished, because they are worth different things
in a meeting:

* **evidenced** — this space's own sources name the competitor. The signal id,
  publisher and date travel with the claim and are clickable.
* **structural** — the curated register says they sell this technology into this
  vertical. True, useful, and not proof they are in the deal.

The level is a band over a weighted count: category weight (a hyperscaler moves a
market more than a regional reseller) × how specifically the competitor matches
this space, doubled where the corpus actually names it. It is scored over the
**listed** competitors rather than the whole register — summing a fifty-entry tail
of weak domain matches would rate every cybersecurity space identically, which is
the same score-compression failure §4.6 warns about for the rubrics.

`relationship: both` is the field that makes the register honest for Orange
Business. Microsoft is a Gold partner and the default alternative in most AI
deals; Cisco is a Global Gold partner and sells managed SD-WAN directly. Recording
that is more useful than pretending either half is not true, and 5 of the 8
competitors listed against a typical security space are Orange partners.

Competitive intensity is a **fourth quantity**, beside attractiveness, right to win
and conviction, and kept as separate from them as they are from each other. A
crowded field and a weak Orange position are different facts; averaging them would
hide both.

### The detailed description, and what it is not allowed to say (FR-14)

Each space carries a long-form description written from its own evidence, its
linked Orange assets and its named competitors — and nothing else. It appears in
the detail pane and is the narrative half of the PDF brief.

Prose is where a model invents, so all four defences of §4.4.4 apply to it in the
same order of effectiveness as in synthesis:

1. **Evidence binding.** The factual sections (`what_is_changing`,
   `competitive_landscape`) must cite signal ids attached to *this* topic. A
   section that cannot is stripped, not rewritten — and what was stripped is
   listed in the UI rather than quietly omitted. Sections that describe what
   Orange would *do* are exempt: a proposal cannot be "supported by a source",
   and demanding a citation for one would only teach the model to attach one at
   random.
2. **Closed vocabulary**, applied to the diagram (below).
3. **No model-generated numbers.** A regex over every generated sentence. The
   brief's figures come from the sizing engine; a model sentence contradicting
   them is worse than a missing one.
4. **Named-entity check.** No customer, partner or competitor beyond the supplied
   lists. Naming a plausible account is the failure most likely to be repeated in
   a meeting as though it were a known Orange relationship.

A description records the topic version it was written against, so a topic that
has moved on is flagged as stale rather than left to mislead.

### The PDF brief, and its diagram (FR-18)

FR-18 was previously listed as not built, with the note that "the read API
exposes everything an exporter needs". This is that exporter: a six-page brief a
salesperson or presales engineer can take into a meeting — the opportunity, the
sized market with every factor and its source, the solution drawn as a diagram,
the named assets, the competitive field with its evidence, qualifying questions,
objections, the next action per role, and every source listed at the back.

Three kinds of content meet on the page and are kept visibly distinct, because a
reader has to know which is which:

| | Produced by | Reproducible from |
|---|---|---|
| **computed** | `scoring`, `sizing`, `competition` | stored inputs (DR-05) |
| **curated** | business graph, competitor register | config with a named owner (DR-11) |
| **written** | the model, under the §4.4.4 defences | its cited signals |

The last page carries the weight set, the sizing version, the register version
and the prompt and model that wrote the prose (DR-10). A brief that cannot be
traced is a brochure.

**The diagram is not drawn by the model.** It emits a *structure* — layers,
boxes, who provides each one, what flows where — which the renderer draws to the
same geometry every time. A model asked for SVG or drawing code produces
something that looks plausible and overlaps its own labels; a model asked for
structure produces something a renderer can guarantee. The closed-vocabulary rule
applies to it too: a box claiming to be an Orange asset that is not in the linked
graph is **demoted to third party rather than deleted** — the architecture still
needs that component — and the demotion is recorded in the brief.

reportlab renders it rather than an HTML-to-PDF pipeline: no browser dependency,
which matters for the sovereign deployment option (NFR-05).

### Three panes, sized by the reader

The middle pane now carries a document and the right pane carries a
decomposition, and which one a user wants larger changes by task. So the
boundary between them is a real separator: drag it, or focus it and use the
arrow keys, or double-click to reset; the width persists. The filter rail
collapses to a strip that still shows how many filters are active, and the detail
pane can be hidden entirely when the brief deserves the full width.

The detail pane answers §4.9's questions in the order they arrive, which is
correct and long — so it carries jump links rather than being reordered. A
presales engineer wants the assets and a strategist wants the sizing; both should
still pass the evidence on the way there.

### The interface, after an adversarial review

Seven independent reviewers went at the running app — three working the sales,
presales and strategist tasks end to end, one on keyboard and contrast, one on
information architecture, one on failure states, one on copy and first use —
and each finding was then handed to a separate reviewer whose job was to refute
it against the code. 82 findings, most confirmed, and the confirmed ones are
fixed. The ones worth naming, because each was a real failure rather than a
preference:

**Nobody could use the list with a keyboard.** Topic rows were `div`s with an
`onClick`. A keyboard or screen-reader user could reach the "how was this
calculated" button on a row but never the row itself, so the detail pane — the
market size, the competitors, the description — was unreachable from the primary
browsing surface. The statement is now a real button inside the row, which also
fixes the selected state: `aria-selected` on a role-less `div` is dropped by
every browser.

**The interface failed its own contrast bar, and worst where it mattered most.**
Measured rather than eyeballed: the evidence-gap warning (SC-13) sat at 2.57:1
in light mode and the "HIGH competition" marker at 2.66:1 in dark — the two marks
that exist to stop someone quoting a thin number were the least legible things on
the page. Status colours are now theme-aware tokens named for the judgement they
carry, every value computed against both surfaces of its own theme. The brand
orange stays on fills and marks, where 3:1 is the bar, and text takes a darkened
sibling: one orange cannot be both a 10px label and a brand colour. **10,056
rendered text elements across seven tabs and two themes now clear WCAG AA.**

**A 20-to-60 second generation finished in silence.** Building a brief swapped
the middle pane with no announcement and no elapsed time. There is now one polite
live region for the whole app, and the wait is counted out loud.

**The five largest sized opportunities were unreachable.** The view is capped at
24 (AC-05) and the only ordering was the role's ranking function, so a strategist
comparing market size could not get to them. There is now an order control —
market size, attractiveness, right to win, least contested, evidence, recency —
which re-orders **within** what the role may see and says so: a salesperson
sorting by market size still cannot reach white space (§4.5.3).

**The filter rail lied about its own counts.** They were computed from the 24
topics on screen, so "CISO: 0" meant "none on this page" while 37 matched. Counts
are now server-computed facets over the whole role-eligible set. Competition level
and "has a sales brief" became filters, filters and sort travel in the URL so a
prepared view can be sent to a colleague, and White space honours the rail
instead of ignoring it while looking interactive.

**Both radar encodings had collapsed.** Marker area spanned 17.8 to 19.9 pixels
and 17 of 26 marks shared one fill, because the scales mapped the nominal 0–100
range while the scores occupy 23–84 and 10–88. Both now map the band the data
actually uses, with the breaks at the measured quartiles; the legend prints them
and has moved above the plot, where it is visible without scrolling.

**The detail pane had grown to ten screenfuls with none of the four quantities in
the first one.** It now opens with attractiveness, right to win, serviceable
market and competitive intensity side by side — four numbers, never combined
(SC-12) — each linking to the section that derives it, followed by the role's own
next action, which had been at screen seven. Jump links cover every section, move
focus rather than only scrolling, and stick to the top of the pane.

**And below 1080px — which is what 200% browser zoom looks like to CSS — the
entire detail pane was `display: none` with no alternative.** Market size,
competition and the description simply vanished. The middle pane now takes it
over.

The full audit, its verdicts and what was refuted are reproducible: the workflow
script is in the session's `workflows/scripts/` directory.

### Serving the same data 18x faster

Assembling a view issued eleven database queries per topic — scores, links, node
labels, competition, size, workflow state, assessments twice, signal count and
two artefact checks. Across 167 topics that was about 1,670 round trips and 1.6
seconds of dead air on **every** filter change, role switch and tab change, and
it was invisible in any frontend profile.

The read model is a read model, so the fix was the obvious one: fetch each table
once for the whole set and index it in memory. `_assemble` reads from that
context when it is given one and queries when it is not, so the single-topic
detail path is untouched — and a test asserts the two paths produce byte-identical
topics, because two code paths for one object is how two surfaces start
disagreeing.

| | Before | After |
|---|---|---|
| `/api/view` | 1.69 s · 343 kB · ~1,670 queries | **0.05 s · 84 kB · 11 queries** |
| `/api/workflow/board` | 1.24 s · 2,151 kB | **0.04 s · 181 kB** |

The board was shipping every topic's links, score components and rank
explanation to render forty-word cards; it now sends what a card shows. The view
drops the fields only the detail page renders. A test guards the query count
against growing *with the number of topics*, which is the regression that would
make a list feel broken at 150 rows.

### Designed for the refresh, not the first run (§4.1)

Canonical identity is the taxonomy triple, enforced by a unique index. A
recurring topic is **updated**, not recreated (DR-03); new signals attach, the
score is recomputed, the previous score is retained. This is what makes momentum
measurable, and §4.4.5 calls it the requirement most often missed in a first
build.

### Leakage control (FR-35, §4.7.3)

Every connector takes a `reference_date` and rejects anything published after it
— filtering on the **publication** date, never the ingestion date. Raw archives
are retained so a replay needs no re-fetch. `radar replay --date 2024-06-01`
reconstructs the state of the world as of that date.

---

## Data sources

**19 of 25 catalogued sources are wired and fetching.** The remaining six are
catalogued in `config/sources.yaml` with the reason they are not — the catalogue
is the requirements record from Appendix A, not only runtime config.

Collection is **parallel**: sources are independent and network-bound, so they
run in a thread pool (`max_parallel_sources`, default 8). Twelve sources
complete in about 45 seconds; database writes stay serial because dedup is a
read-modify-write over the whole signal table.

| Source | Category | Signals | Notes |
|---|---|---|---|
| TED | Procurement | 827 | Above-threshold EU tenders with CPV, country, buyer, value |
| EC "Have your say" | Regulation | 167 | Consultations with their feedback **deadline** — feeds horizon derivation |
| OpenAlex | Technology | 142 | Carries an Orange-affiliation flag (§2.5) |
| Google News (FR) | Signals | 117 | French-language coverage |
| BOAMP | Procurement | 117 | French below-threshold tenders (§4.3.3) |
| Google News (EN) | Signals | 111 | |
| EUR-Lex | Regulation | 58 | Dated legal instruments, stage inferred |
| CORDIS | Technology | 48 | EU-funded projects — what Europe decided to fund |
| ANSSI / CERT-FR | Regulation | 36 | National regulator; also French-language |
| GDELT | Signals | 29 | Rate-limited, see below |
| Hacker News | Signals | 22 | Practitioner attention, tier 3 |
| arXiv | Technology | 12 | |
| NIST | Regulation | 10 | Standards timelines, post-quantum |
| **Total** | | **1,696** | 1,406 tier-1 · 234 French |

Not wired, with the reason: Ofcom (403 to automated clients), BNetzA and BIPT
(documented feed paths 404), ENISA (retired its RSS endpoints), 3GPP and ETSI
(publish HTML, not feeds), EPO OPS (needs registration), PatentsView and ACLED
(DNS failures), Eurostat and World Bank (reachable, but they are *reference*
data for bottom-up sizing rather than dated signals — see below).

### Three sampling bugs worth knowing about

Each of these produced a plausible-looking corpus that was quietly wrong. All
three were found by looking at what actually landed in the database.

* **TED returned 40 of 14,485 matching notices, all from one day.** The API
  accepts no sort parameter and returns publication-date ascending, so a single
  capped request samples only the oldest day in the window — 182 of 218 notices
  from one date. Momentum (§4.6) is the slope of signal volume over trailing
  periods, so that corpus made every procurement-driven momentum figure
  meaningless. Fixed by slicing the window into 14-day chunks and querying each:
  now 827 notices across 35 distinct dates spanning the full 90 days.
* **CORDIS returned nothing at all.** It leaks its own localisation template and
  emits dates as `1 {{month_11}} 2023`, which failed date parsing, so every
  project was rejected as undated (DR-04) — silently, with no error.
* **EUR-Lex yielded 20 distinct acts from 120 rows.** CELLAR returns one row per
  expression title and several titles share a work, so rows collapsed on URL
  dedup. The limit was raised to compensate; a EuroVoc-concept query is the
  proper Sprint 0 fix.

**GDELT caveat.** The connector is correct and does return data, but GDELT
applies an aggressive per-IP cooldown and 429'd most requests during the build.
It is paced at one request per 6s. Two guards keep one sick source from damaging
a refresh:

* **Graceful degradation** — a failing source is recorded in the refresh stats
  and never aborts the run.
* **Circuit breaker** — after two exhausted requests to a host, the rest of that
  host's requests are skipped and the host is reported in `collect.errors`.
  Without it, ten blocked GDELT queries cost eleven minutes for zero data. GDELT
  is the long pole in every refresh: everything else finishes in 45 seconds
  while it takes up to 11 minutes alone.

**Reference data is wired, on its own path.** Five Eurostat series feed market
sizing and are stored as reference observations rather than signals, for the
reason given in the sizing section above:

| Series | Dataset | Observations | What it gives |
|---|---|---|---|
| Structural business statistics | `sbs_sc_ovw` | 27,958 | Enterprise counts and turnover by NACE division, size class and country — the denominator |
| Enterprise cloud use | `isoc_cicce_usen2` | 6,885 | Paid cloud adoption by NACE aggregate |
| Enterprise AI use | `isoc_eb_ain2` | 11,440 | AI adoption by technology and NACE aggregate |
| Enterprise IoT use | `isoc_eb_iotn2` | 2,759 | IoT adoption by purpose |
| ICT security measures | `isoc_cisce_ran2` | 7,343 | Security practice by measure |

30 geographies (EU27 aggregate plus member states, Norway and Switzerland), the
last three published periods each, refetched only when older than the configured
age — these are annual statistics, not a feed. The AI series carries its own
trajectory, which the UI shows as an adoption trend: machine learning in EU
vehicle manufacturing went 3.2% (2023) → 4.8% (2024) → 7.8% (2025), which is a
dated, attributable growth statement rather than a generated one.

Still not wired: OECD, ITU, IEA, SEC EDGAR and the national statistics offices
from Table 19. They matter for topics outside the European business economy —
today those are sized on the covered subset and the shortfall is reported.

## Frontend

React + Vite + TypeScript, no chart library — the radar is hand-drawn SVG
because the encoding is specific to this product.

**The radar view** (§4.9): angular sector = business domain, radial distance =
time horizon (Now at the centre), marker **size** = attractiveness, marker
**colour** = right to win. Position carries identity, so no categorical hues are
needed. Colour encodes a magnitude, so it uses a single-hue sequential ramp,
validated for lightness monotonicity, adjacent step separation, single hue and
light-end contrast against its own surface in **both** light and dark mode.
Evidence-gap marks carry a `!` glyph as well as a border, so the warning never
depends on colour alone.

**The brief view** is the middle pane rendering the PDF inline, with Download,
Regenerate and a staleness warning when the topic has moved past the version the
brief was built against. Showing it beside the radar rather than only offering a
download is what makes anyone notice it is out of date.

**Market opportunity and competition** appear in the detail pane as the working,
not just the number: TAM/SAM/SOM with their ranges, every factor with its source,
year and basis badge, the caveats behind a disclosure, and per competitor the
signals that name them.

Deep links work: `?topic=OS012&role=presales&theme=dark`, and `?tab=brief` opens
the brief for the selected space.

---

## Deployment

The radar runs as a single Azure App Service: one process serving the read API
and the built React bundle from the same origin, which is what the CORS list in
`api.py` was always scoped for.

```bash
./scripts/deploy-azure.sh          # build, package, provision if needed, push
```

| | |
|---|---|
| Subscription | Azure for Students (`9ca89421…`), tenant `33ac9060…` |
| Resource group | `rg-railpulse-cloud` |
| Region | France Central |
| Plan / app | `plan-railpulse-cdb4ce` (F1, Linux, shared) / `web-orange-radar-1521f5` |
| Runtime | Python 3.13, `bash startup.sh` → gunicorn + uvicorn worker |

Three deployment decisions worth recording, because each is a constraint someone
will otherwise rediscover:

**Where it runs.** The subscription carries an `Allowed resource deployment
regions` policy — Italy North, France Central, Germany West Central, Poland
Central, Spain Central, all EU, which suits a product whose strategic frame is
sovereignty. The radar shares `plan-railpulse-cdb4ce` with the RailPulse app: a
Free plan hosts up to 21 sites and the two draw on the same 60 CPU-minutes a day.
Giving the radar its own plan means paying for one — B1 is about USD 13/month:

    RG=rg-orange-radar PLAN=plan-orange-radar SKU=B1 ./scripts/deploy-azure.sh

**Nothing may raise at import, and no bash wrapper.** These two are one lesson.
A container that exits is restarted, fifteen restarts exhaust the Free plan's
`WP stop requests` quota, and that quota **also disables Kudu** — so a crash loop
erases the logs that would explain it. Five deployments failed that way before
the design changed to make it impossible:

* The startup command names **no absolute path and no console script**:
  `python3 -m uvicorn main:app`. This is the one that cost five deployments, and
  the cause is not obvious. App Service does not run the deployed tree in place.
  Oryx builds it, compresses the result to `output.tar.zst`, and on *every*
  container start extracts that tarball to a fresh `/tmp/<hash>` which becomes
  the working directory. `/home/site/wwwroot` holds the tarball and nothing
  else, and the extraction path changes with each deploy — so no absolute path
  into `wwwroot` is ever valid at runtime, not for a startup script, not for
  `PYTHONPATH`, not for a module. Every such command exits **127** before
  printing anything. `python3 -m` resolves through `PYTHONPATH` (which Oryx
  points at the extracted virtualenv) rather than `PATH` (which it does not
  extend), and `main.py` puts its own sibling `src` on `sys.path`, so both
  resolve relative to wherever the tarball happened to land.
* Everything that wrapper used to do — seeding `/home/data/radar.db` from the
  package, converting its journal mode, copying the briefs — is in
  `radar/bootstrap.py`, which runs inside the app, inside the venv, and catches
  everything it can hit.
* `api.py` no longer dies when the database is unusable. It records the error
  and `/healthz` answers **503 with the reason**, so a bad deployment describes
  itself over HTTPS instead of disappearing.
* Briefs are resolved by **filename against the configured directory**, not by
  the absolute path recorded in `topic_briefs.path`. That column records the
  machine that *built* the PDF — a laptop the server has never seen — so taken
  literally every brief 404s in Azure and the UI reports that none were ever
  generated. `resolve_brief()` falls back to `RADAR_BRIEF_DIR`, and both the
  file route and the metadata payload go through it so they cannot disagree.

**Reading the logs when Kudu is 403.** The deadlock above is escapable without
waiting an hour. Point the startup command at a static server over the whole
persisted tree —

    az webapp config set -g $RG -n $APP \
      --startup-file "python3 -m http.server 8000 --directory /home"

— and the container stays up (so the restart quota stops draining) while
`/LogFiles/*_docker.log` becomes readable over plain HTTPS. That is what finally
produced the `exit code 127` and the `can't open file` line above, after five
attempts spent guessing. Reach for it early, not late.

**SQLite cannot use WAL on `/home`.** This one cost a night. `/home` is the only
path that survives a restart on Linux App Service, and it is an SMB mount:
Azure Files. WAL needs shared memory that SMB does not provide, so opening a WAL
database there fails — and because `api.py` calls `init_schema()` at import, the
failure takes the worker with it. The platform restarts the worker, the worker
fails again, and after fifteen restarts the plan's hourly `WP stop requests`
quota is spent. At that point the app returns 403 `QuotaExceeded`, **and so does
Kudu**, so the logs that would explain it are unreadable until the quota resets.

The symptom is easy to misread as a Free-tier limitation — a second app on the
plan was even stopped to "free a slot", which changed nothing: the F1 plan runs
both apps side by side. It is not a resource limit — CPU sat at
0% of its daily allowance throughout. `db.py` therefore takes
`RADAR_SQLITE_JOURNAL_MODE` (default `WAL`, set to `DELETE` in App Service),
`startup.sh` converts the seeded copy once, and it writes its own log to
`/home/LogFiles/radar-startup.log`, which survives a container that does not.

**What is not deployed.** The serving package carries no pipeline dependencies:
`radar.api` imports scikit-learn, sentence-transformers and the OpenAI client
only inside the functions that need them, so a serving instance never loads
torch. That is a 28 MB package instead of a multi-gigabyte one, and on the Free
tier it is the difference between starting and not. Discovery stays a local
batch job against the same SQLite file; deploying is the publish step.

**What persists.** `/home` is the only path that survives a restart or a
redeploy on Linux App Service, so the database and generated briefs live in
`/home/data`. `startup.sh` seeds it from the package on first boot and then
leaves it alone — feedback, assessments, descriptions and briefs created in
production are not thrown away by the next push. The replay archive
(`raw_items`) is dropped from the serving copy: it exists so the pipeline can be
re-run as of a past date (DR-14, FR-35), which is not something the API does,
and it is half the file. Every citation still resolves.

**Secrets** are App Settings, read from the local `.env` at deploy time and never
written into the package. The `.env` itself is excluded.

**If the site answers 403 and the portal says `QuotaExceeded`,** it is almost
certainly a crash loop rather than a resource limit. Check which quota before
assuming it is CPU:

```bash
az rest --method get --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/\
rg-railpulse-cloud/providers/Microsoft.Web/serverfarms/plan-railpulse-cdb4ce/usages?api-version=2022-03-01"
```

During this deployment the answer was `WP stop requests: 41 / 15` while CPU sat
at 0% — a container failing to boot, restarted until the cap was reached. It
clears on the hour. Redeploying to fix it makes it worse: stop the app first,
which ends the loop, then read `/home/LogFiles/radar-startup.log` once the quota
allows Kudu to answer again.

### Before this goes anywhere real

The deployed app is **public and unauthenticated**, which is fine for a
demonstration and not fine for anything else. Two things follow:

* The brief PDFs are stamped *Internal*, and the business graph, the competitor
  register and the reference density are Orange's own material. Anyone with the
  URL can read all of it.
* The generation endpoints (`POST /api/topics/{id}/description`, `POST
  /api/topics/{id}/brief`) call the configured model with the deployed key, so
  anyone with the URL can spend it. The key in question was shared in plaintext
  over chat during development and should be rotated regardless.

Either of these closes it, in one command:

```bash
# Only your address may reach it
az webapp config access-restriction add -g rg-orange-radar -n web-orange-radar-1521f5 \
  --rule-name office --priority 100 --action Allow --ip-address "$(curl -s ifconfig.me)/32"

# Or require a Microsoft Entra sign-in from the tenant
az webapp auth update -g rg-orange-radar -n web-orange-radar-1521f5 \
  --enabled true --action RedirectToLoginPage --redirect-provider AzureActiveDirectory
```

---

## Tests

```bash
python3 -m pytest tests/ -q      # 167 tests
```

They cover the invariants that would be expensive to discover late: score
reproducibility (SC-11), syndication collapse and tier-4 discounting (SC-03),
vendor-only evidence scoring low (SC-09), evidence binding stripping uncited
claims, specificity validation rejecting the briefing's named negative examples,
triple-based identity and merge, link typing and portfolio distance, horizon
derivation, the lifecycle state machine, evidence-gap warnings (SC-13), and
publication-date leakage control (FR-35).

The sizing, competition and brief suites (48 tests) hold the same kind of line:
that the denominator and the adoption rate share a size base; that a crosswalk's
per-row confidence reaches the arithmetic rather than sitting in the CSV; that
only a tender whose *main object* is an IT contract may price an engagement; that
a proxy widens the range without moving the base; that the confidence grade is
the worst factor rather than an average; that SAM never exceeds TAM; that an
uncited factual section is stripped; that a generated percentage or euro figure
kills the section carrying it; that an unsupplied organisation does the same; and
that a diagram box cannot claim an Orange asset the graph does not hold.

Several of these tests caught real bugs during the build:

* Shannon entropy is scale-invariant, so a uniform tier-4 discount cancelled out
  entirely — six vendor blogs scored identically to six independent outlets.
  Fixed by applying the discount to the effective publisher count.
* Certifications were typed L0, making portfolio distance meaningless for every
  topic in a regulated vertical.
* `build_graph` wiped `graph_nodes` while `opportunity_links` held a foreign key
  onto it, so a second rebuild failed. Fixed by upserting nodes and retiring the
  disappeared ones — which is also where LK-07 (withdrawn assets propagating to
  affected topics) now lives.
* The exploration slot (§4.7.6) drew from all filtered topics rather than
  role-eligible ones, so it could show a salesperson a topic with no proof point
  — bypassing the very filter §4.5.3 requires.

---

## What is deliberately not built

Matching the MVP exclusions in Table 15, plus what this pass did not reach:

| Not built | Why |
|---|---|
| CRM integration | Deferred by the briefing; public assets give a sufficient right-to-win proxy |
| Learned scoring models | No labels exist on day one. The MVP ships the transparent baseline and the capture/replay harness the learned models need (§4.7) |
| Patent connector | Needs EPO OPS registration or BigQuery credentials. Technology ownership currently uses a portfolio-level prior from `technologies.yaml` |
| Slide export | The PDF brief (FR-18) is built; a PowerPoint variant is not |
| Collaboration workflow (FR-25) | Priority C; depends on the collaboration model being agreed (§4.10) |
| Backtest evaluation harness | The replay path exists (FR-35); the metrics of §4.7.5 are not implemented |

---

## Open questions for Orange

§4.13 lists thirteen. The four that most affect the code as written:

1. **Refresh cadence** — drives connector design and cost more than any other
   decision. Currently `period_days: 14`.
2. **Sovereign deployment** — may an external model API be used during the MVP?
   The abstraction supports Ollama today; the question is whether it must be
   exercised now.
3. **Internal taxonomies** — the 59 use cases and 38 technologies are a drafted
   Sprint 0 deliverable. If an internal catalogue exists it should replace them.
4. **Who is the curator?** 173 links are currently unconfirmed. LK-06 requires a
   named human to adjudicate the first occurrence of each link pattern, and
   without one, quality drifts. The same question now applies twice over: the
   sizing assumptions in `config/sizing.yaml` (contract duration, size-class
   weights, obtainable share) and the 65-entry competitor register both carry
   `innovation-radar-curator` as a placeholder owner, and both will appear in
   front of customers.
5. **Is the four-year contract assumption right?** TED publishes a contract's
   whole value, and annualising it needs a duration. Four years is the figure
   used and printed; an Orange bid team will have a better one, and every size in
   the radar moves inversely with it.
6. **How wide is the private-sector proxy?** Contract values are observed from
   public procurement because that is the only attributable source available.
   Where Orange has its own won-deal distribution, substituting it would move
   these estimates off a proxy and onto evidence.

---

## Security note

`.env` is gitignored and holds the DeepSeek API key supplied for development.
That key was shared in plaintext over chat, so **rotate it before any wider
use**, and issue a separate key for CI.
