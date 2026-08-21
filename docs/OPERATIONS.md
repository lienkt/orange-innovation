# Operations runbook

*How to run the pipeline, in what order, and what to do when a stage misbehaves.*

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env                 # then fill in the provider key
PYTHONPATH=src python3 -m radar.cli check
```

`check` validates every configuration file and cross-reference and prints the
vocabulary sizes. **A dangling identifier is a startup error, not a runtime
surprise** — that is the whole point of running it first.

The `radar` entry point is installed by `pip install -e .`; every example below
also works as `PYTHONPATH=src python3 -m radar.cli …`.

---

## The order things run in

Stages are independent and each reads what its predecessor wrote to the
database, so any subset can be re-run alone. That is how the system is
developed, tested and repaired.

```
radar refresh --since-days 60
```

runs all thirteen stages. The pieces, in dependency order:

| # | Stage | Needs | Model? | Notes |
|---|---|---|---|---|
| 1 | `collect` | network | no | Parallel, 8 hosts at a time |
| 2 | `normalise` | 1 | no | URL dedup is a read-modify-write, so writes stay serial |
| 3 | `classify` | 2 | **yes** | Batched 12 per request, temperature 0 |
| 4 | `themes` | 3 | no | Deterministic clustering — no randomised init (SC-11) |
| 5 | `synthesise` | 4 | **yes** | 3 lensed passes per cluster, 4 clusters concurrent |
| 5b | `enrich` | 5 | no | Embeddings + taxonomy corroboration |
| 6 | `graph` | config | no | Rebuilds the business graph from YAML |
| 6b | `link` | 5, 6 | no | Typing and portfolio distance — no model at all |
| 6c | `score` | 6b | **yes** | One rubric call per topic; the rest is arithmetic |
| 6d | `actions` | 6c | **yes** | One call per topic |
| 6e | `reference` | network | no | Eurostat; annual data, refetched on age |
| 6f | `size` | 6e | no | No model anywhere on this path |
| 6g | `competition` | register | no | Arithmetic over the competitor register |
| 7 | `describe` | 6f, 6g | **yes** | Capped at 40 per refresh |

Subsets:

```bash
radar refresh --stages collect,classify
radar refresh --stages score,actions
radar refresh --stages size,competition --no-llm
```

### Competitor intelligence

Runs on its own cadence, not inside `refresh` — the sites change slowly and the
crawl is slow.

```bash
radar competitor-scrape                    # ~15-20 min, robots-aware
radar competitor-profile                   # 1 model call per competitor
radar competitor-analysis --no-llm         # the join, free, every topic
radar competitor-analysis --limit 40       # comparisons, capped
```

`--force` on either of the last two rebuilds even when nothing moved. Both skip
work that is still current: profiles compare a `corpus_hash`, analyses compare
the topic version, the prompt version and the register version.

### Outputs

```bash
radar describe --limit 40
radar brief OS012 --open
radar brief --all
```

---

## Serving

```bash
radar serve                                # 127.0.0.1:8000
npm --prefix frontend run dev              # 5173, proxying to 8000
```

For production the API also serves the built bundle from the same origin:

```bash
npm --prefix frontend run build
radar serve --host 0.0.0.0 --port 8000
```

> **The failure you will hit at least once.** `radar serve` does not reload. If
> you add an endpoint and the frontend calls it, the running server answers
> `200 text/html` (the app shell, via the SPA catch-all) rather than 404. The
> frontend detects this and says *"the running server is older than the bundle
> it is serving"* — restart it, or use `--reload` while developing.

---

## Inspecting without the UI

```bash
radar topics --role sales --limit 20
radar show OS012                    # full decomposition: claims, links, score inputs
radar whitespace                    # high attractiveness, no portfolio path
radar orphan-offers                 # offers with no live topic
radar coverage                      # language / geography / tier / competitor coverage
```

---

## Curation

```bash
radar confirm-link "offer:live_objects|use_case:asset_tracking" \
      --decision confirmed --curator alice
radar internal add --author bob --kind customer_conversation \
      --title "Airport asked about counter-drone" --vertical transport_logistics
radar internal pending
radar internal moderate INT-0001
radar internal promote
```

Internal signals are **inert until moderated**. External evidence arrives with a
publisher and a date a reviewer can check; an internal note arrives with neither,
so the moderation step is what keeps NFR-02 true for a class of evidence whose
attribution is a colleague rather than a publication. They enter at **tier 3**.

---

## Replay

```bash
radar replay --date 2024-06-01 --since-days 90
```

Every connector rejects anything published after the reference date, filtering on
the **publication** date and never the ingestion date. `raw_items` is retained so
a replay needs no re-fetch.

---

## Troubleshooting

### A source returned nothing

Check the refresh row first, not the logs:

```bash
radar coverage
sqlite3 data/radar.db "select id, stats from refreshes order by started_at desc limit 1"
```

`stats.collect.errors` names the hosts that failed and the ones whose circuit
breaker tripped. A failing source is recorded and never aborts the run.

**The circuit breaker is deliberately twitchy** — two exhausted requests to a
host and the rest of that host's requests are skipped, because ten blocked GDELT
queries otherwise cost eleven minutes for zero data. For a rarely-run job like
the competitor crawl that is too aggressive; raise `failure_budget` and
`min_interval` and re-run the affected ids.

### A model call failed on invalid JSON

Almost always truncation, not malformed output — the response hit the completion
budget mid-string. The symptom is `Unterminated string starting at:` and the loss
of the whole artefact rather than its tail. Raise `max_tokens` on that call site.
Both the profile call (6000) and the analysis call (8000) were raised for exactly
this reason after failing on the largest inputs.

### The competitor tab is empty

Three different causes, and the interface distinguishes them:

| What you see | Cause | Fix |
|---|---|---|
| "could not be loaded" + an error | The request failed | Usually a stale server — restart it |
| "Competitive intensity has not been computed" | No `topic_competition` row | Press the button, or `radar competition --topics OS123` |
| "No competitor from the register is matched" | Assessed, matched nobody | A statement about the register, not a bug |

### A brief is marked incomplete

It was rendered before a section that current briefs carry existed. That is
different from **stale**, which means it was correct when built and has been
overtaken. Only a rebuild fixes incomplete:

```bash
radar brief OS012          # or the Regenerate button in the Brief tab
```

### Scores look wrong after a config change

Changing any weight requires a **new `weight_set` id**. Scores across a version
boundary are not comparable, every score records the set that produced it, and
the interface refuses to plot a trajectory across the boundary silently.

---

## Regenerating the documentation

```bash
# diagrams (matplotlib, no external tooling)
python3 docs/build_diagrams.py

# API and data-model references, generated from the running code
python3 docs/build_reference.py
```

Both are regenerated from the code and the live schema, so they cannot drift.
The FDD and Technical Architecture `.docx` files are built by
`docs/build_docs.py`, which embeds the diagrams.

---

## Deployment

```bash
./scripts/deploy-azure.sh
```

Three constraints that will otherwise be rediscovered:

* **The Free App Service tier allows one plan per subscription, not per region.**
  A second plan is created without complaint and then sits at `QuotaExceeded`
  forever, in any region.
* **`/home` is the only path that survives a redeploy**, and it is an SMB mount.
  SQLite's WAL needs shared memory SMB cannot provide, so the seeded database is
  converted to `DELETE` journal mode once at boot.
* **A crash loop destroys its own evidence.** Fifteen restarts exhaust the plan's
  quota, which disables the log endpoints that would explain the first failure.
  `startup.sh` therefore never uses `set -e`, tees its output to `/home/LogFiles`,
  and falls back to a diagnostic server rather than exiting.

Before anything real: the deployed app is **public and unauthenticated**, and the
two generation endpoints spend the deployed model key. See the Technical
Architecture, section 16.
