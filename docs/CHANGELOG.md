# Changelog

Notable changes to the Innovation Radar, most recent first. Defects are recorded
alongside features, because several of the defects are more instructive than the
features that exposed them.

---

## Competitor intelligence

**Added.** A subsystem that reads what each competitor publishes about itself and
turns it into per-topic competitive analysis. Full detail in
[COMPETITOR_INTELLIGENCE.md](COMPETITOR_INTELLIGENCE.md).

* `competitor_intel.py` — robots-aware, sitemap-guided crawler and profile
  builder. **1,745 pages across 53 of 65 competitors**; the other 12 recorded
  with a reason.
* `competitor_analysis.py` — the per-topic join (arithmetic, always present) and
  the written comparison (one model call, absent until asked for).
* **A differentiation paragraph per competitor** — how Orange differentiates
  against *that* company for *this* opportunity, anchored on an Orange asset
  actually linked to the topic, with a concession of what they do better.
* Three new tables: `competitor_pages`, `competitor_profiles`,
  `topic_competitor_analysis`.
* Three new CLI commands: `competitor-scrape`, `competitor-profile`,
  `competitor-analysis`.
* Three new endpoints: `/api/competitors`, `/api/competitors/{id}`,
  `/api/topics/{id}/competitor-analysis` (GET and POST).
* A third tab on the full-screen space view, between the space and the brief.
* A **competitor analysis section in the PDF brief**, per competitor.
* A **competitive picture** section in the Coverage view: three progress bars and
  the unread competitors named individually.
* A fifth synthesis lens — *competitor movement* — plus cell targeting: where two
  or more profiled competitors sell into a taxonomy cell the radar has no topic
  for, that cell is promoted to the front of the target list.

**Register.** All 65 competitors gained a `website` and a `scrape` status.

**Schema.** `topic_briefs.brief_schema`, applied by the first additive migration
(`db.MIGRATIONS`) so an existing database — including the deployed one — gains
the column without being recreated.

### Defects found and fixed

| Defect | Consequence | Fix |
|---|---|---|
| **Model echoed the vocabulary list.** Asked for OVHcloud's technologies it returned the first eight ids *in vocabulary order* — every one valid, so closed-vocabulary validation passed all eight. OVHcloud's pages mention 5G zero times. | Wrong tags fed topic seeding and the per-topic join. | Vocabulary tags now require corroboration in the source text, word-boundary matched, minimum four characters. All 53 profiles rebuilt. |
| **A citation proved a page was read, not that it said this.** "Accenture LED Flashlight" arrived as a named offer with a page id attached. | Fabricated product names in a competitive briefing. | Offer names must also appear in the corpus. |
| **Lens rotation never reached the last lens.** `index % len(LENSES)` with 3 passes over 4 lenses meant the cross-vertical lens **never fired, for the life of the pipeline** — and the new competitor lens would have been dead on arrival. | A quarter of the designed generation diversity was unreachable. | The lens window is offset per cluster. |
| **A failed crawl recorded no status.** Eight competitors looked identical to never-attempted. | Coverage counted a refusal as a pending gap. | Every failed crawl records why; the eight were re-run patiently and four recovered. |
| **A failed request rendered as a finding.** The competitor pane checked `!data \|\| entries.length === 0` before checking `error`, so a request that never completed printed *"No competitor from the register is matched to this space"*. | The product's core failure mode, reproduced in its own interface. | Error state renders first, with the message; "not assessed yet" is distinguished from "assessed, matched nobody". |
| **Truncated JSON lost whole artefacts.** Large inputs hit the completion budget mid-string. Two profiles and 23 analyses failed. | The whole artefact was lost rather than its tail. | `max_tokens` raised on both call sites (6000 / 8000); all failures re-run. |
| **Locale detection was too eager.** Any two-letter path segment was treated as a locale, so `/ai/platform` collapsed to `/platform`. | Two genuinely different pages merged into one. | An allowlist of unambiguous language codes; `ai`, `it`, `id`, `is`, `no` are deliberately excluded. |

**Tests.** `tests/test_competitor_intel.py` — 23 tests, including a regression
for each defect above.

---

## Documentation

**Added.** [`API.md`](API.md), [`DATA_MODEL.md`](DATA_MODEL.md),
[`OPERATIONS.md`](OPERATIONS.md), [`DECISIONS.md`](DECISIONS.md),
[`COMPETITOR_INTELLIGENCE.md`](COMPETITOR_INTELLIGENCE.md), this changelog, and a
[docs index](README.md).

`API.md` and `DATA_MODEL.md` are generated from the running application and the
live schema, so they cannot drift from the code.

**Updated.** The Functional Design Document and the Technical Architecture, both
regenerated with the competitor subsystem, the new tables and current figures.
The README.

---

## Earlier

### Documentation set

The Functional Design Document and Technical Architecture were written as Word
documents with 21 programmatically generated diagrams, including a full
crow's-foot ERD across four subject areas. Speaker notes for the deck were
produced from the recorded walkthrough.

### Sources and generation

* Source catalogue grew to **42 catalogued, 33 enabled**, across 17 connector
  types.
* `pipeline/query_grid.py` — collection queries are now derived from the
  taxonomy rather than hand-written literals. `config/sources.yaml` had claimed
  this was already true; it was not, and the first corpus showed it: whole
  branches of a 59-use-case vocabulary had no query at all.
* `connectors/demand.py` — SEC EDGAR full-text search and Adzuna job postings.
  Demand-side leading indicators that precede a tender rather than report it.
* `generation.py` and the Generate screen — on-demand, constrained synthesis
  bounded to a slice of the taxonomy, scoped so that serving five new spaces does
  not re-score the whole radar.
* `internal.py` — internal signal intake with a moderation gate, entering at
  tier 3.

### Serving and deployment

* `bootstrap.py` — a serving instance that cannot open its database now starts,
  says so, and keeps answering. A readable 503 is worth more than an invisible
  restart loop, and on a Free plan a crash loop destroys the evidence of its own
  first failure.
* The read model was rewritten to fetch each table once for the whole set:
  `/api/view` went from **1.69 s and ~1,670 queries to 0.05 s and 11**.

### Interface

Seven independent adversarial reviewers, 82 findings, each handed to a separate
reviewer to refute against the code. Confirmed findings fixed — keyboard
reachability of the primary browsing surface, contrast measured rather than
eyeballed across 10,056 rendered text elements in both themes, server-computed
facet counts, and both radar encodings rescaled to the band the data actually
occupies.
