"""Prompt construction (§4.4.2, §4.4.3).

Prompts are built from configuration rather than written as literals wherever
the content comes from a controlled vocabulary (NFR-11), so extending the
taxonomy extends the prompt automatically.

Prompt versions are constants here and are written onto every artefact the
prompt produces (DR-10, NFR-02). Changing a prompt means bumping its version —
otherwise the lineage claim in NFR-02 is false.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import Config

PROMPT_VERSION_SYNTHESIS = "synth-v1"
PROMPT_VERSION_CRITIC = "critic-v1"
PROMPT_VERSION_RELEVANCE_RUBRIC = "strategic-relevance-v1"
PROMPT_VERSION_NEXT_ACTION = "next-action-v1"
PROMPT_VERSION_ENTAILMENT = "entail-v1"
PROMPT_VERSION_DESCRIPTION = "describe-v1"


# The six worked examples from the briefing. §4.4.2 calls these "unusually good
# few-shot anchors because they were written by the client and encode the
# intended granularity precisely".
POSITIVE_EXAMPLES = [
    "Private 5G plus edge vision for safety compliance in mining",
    "Agentic AI for claims deflection in insurance contact centres",
    "Digital product passports and traceability for materials producers",
    "Network-as-a-sensor security analytics for banking WANs",
    "Predictive worker-safety wearables for chemicals plants",
    "Sovereign cloud and AI enclaves for government citizen data",
]

# §4.4.2 negative examples, with the reason each fails.
NEGATIVE_EXAMPLES = [
    ("AI", "a technology, not an opportunity: no vertical, no use case, nothing to sell"),
    ("Cloud", "a delivery model, not an opportunity"),
    ("Cybersecurity", "a domain, not an opportunity"),
    ("Digital transformation in retail", "a vertical plus a slogan: no specific use case or technology"),
    ("AI in industry", "generic on both axes; a salesperson could not open a meeting with it"),
]


def orange_context_block(cfg: Config) -> str:
    """System context: who Orange Business is (§4.4.2 element 1)."""
    strategy = cfg.strategy
    ambitions = "\n".join(
        f"  - {a['label']}: {a['content'].strip()}\n    Radar implication: {a['radar_implication'].strip()}"
        for a in strategy["ambitions"]
    )
    privileged = ", ".join(strategy.get("privileged_verticals", {}))
    scale = cfg.assets.get("scale_reference", {})
    return f"""You are working for Orange Business, the enterprise division of the Orange Group.

WHO ORANGE BUSINESS IS
Orange Business positions itself simultaneously as operator, integrator and platform
player. Revenue €{scale.get('ob_revenue_2025_eur_bn')}bn (2025), {scale.get('ob_employees'):,} employees,
{scale.get('ob_b2b_customers'):,}+ B2B customers, coverage in {scale.get('countries_covered')}+ countries
with teams in {scale.get('countries_with_teams')}.

STRATEGIC FRAME — "{strategy['plan']}" ({strategy['period']})
{ambitions}

An opportunity space that connects to NONE of these three ambitions is, by the
Group's own definition, not strategically relevant. Discard it.

PRIVILEGED VERTICALS: {privileged}. Orange created dedicated divisions for these.

TRUST AND SOVEREIGNTY are a cross-cutting axis, not one topic among others. A
topic deliverable on sovereign, certified infrastructure is worth more to Orange
than the same topic delivered generically.

DIVISIONAL GUIDANCE: the division is expected to shift mix toward trusted,
higher-value services rather than to grow volume. Favour topics with a credible
margin story over topics that merely add revenue."""


def vocabulary_block(cfg: Config) -> str:
    """Controlled vocabularies (§4.4.2 element 2)."""
    return f"""CONTROLLED VOCABULARIES — you may emit ONLY these ids. Any other value fails
validation and the candidate is discarded.

VERTICALS ({len(cfg.verticals)}):
{cfg.verticals.prompt_block()}

USE CASES ({len(cfg.use_cases)}):
{cfg.use_cases.prompt_block()}

TECHNOLOGIES ({len(cfg.technologies)}):
{cfg.technologies.prompt_block()}

BUSINESS DOMAINS ({len(cfg.domains)}):
{cfg.domains.prompt_block(include_definitions=False)}

CUSTOMER PERSONAS ({len(cfg.personas)}):
{cfg.personas.prompt_block(include_definitions=False)}"""


def examples_block() -> str:
    positives = "\n".join(f"  GOOD: {e}" for e in POSITIVE_EXAMPLES)
    negatives = "\n".join(f"  BAD: \"{text}\" — {why}" for text, why in NEGATIVE_EXAMPLES)
    return f"""WHAT SPECIFICITY MEANS
These were written by the client and encode the intended granularity exactly:
{positives}

These fail and must never be emitted:
{negatives}

The test: could a salesperson open a customer meeting on Thursday with this
sentence, and would the customer know it was about them?"""


def synthesis_system_prompt(cfg: Config) -> str:
    """The core synthesis prompt (§4.4.2)."""
    return f"""MOCK_KIND=synthesis
{orange_context_block(cfg)}

YOUR TASK
You are given a cluster of dated, attributable evidence. Produce candidate
OPPORTUNITY SPACES, each defined as exactly:

    Vertical  x  Use Case  x  Technology

plus a human-readable opportunity statement.

{vocabulary_block(cfg)}

{examples_block()}

ABSOLUTE RULES — violating any of these invalidates the candidate
1. EVIDENCE ONLY. The evidence block is the only factual material you may use.
   You are reorganising retrieved evidence, not recalling what you know. If the
   evidence does not support a candidate, do not produce that candidate.
2. EVERY CLAIM IS CITED. Each entry in `why_hot` must carry a non-empty
   `signals` array of signal ids drawn from the evidence block. An uncited claim
   is stripped, not rewritten.
3. CLOSED VOCABULARY. `vertical`, `use_case` and `technology` must each be
   exactly one id from the lists above. Not two. Not a new one.
4. NO NUMBERS. Never state a market size, growth rate, percentage or monetary
   value. If the evidence contains one, you may cite the signal, but express the
   magnitude qualitatively.
5. FEWER, BETTER. Produce only candidates the evidence genuinely supports. An
   empty list is a valid and often correct answer.

OUTPUT — a single JSON object:
{{
  "candidates": [
    {{
      "vertical": "<vertical id>",
      "use_case": "<use case id>",
      "technology": "<technology id>",
      "statement": "<one specific sentence, 40-180 characters>",
      "domains": ["<domain id>", ...],
      "personas": ["<persona id>", ...],
      "geographies": ["<ISO 3166-1 alpha-2 code or EU>", ...],
      "why_hot": [
        {{"claim": "<one sentence, no invented numbers>", "signals": ["SIG-...", ...]}}
      ],
      "why_specific": "<why this is not a generic theme>"
    }}
  ]
}}"""


def synthesis_user_prompt(cluster: dict[str, Any], target_cells: list[dict[str, str]] | None = None,
                          lens: str | None = None) -> str:
    """Evidence block (§4.4.2 element 3), optionally targeted at empty grid cells.

    `lens` steers one generation pass toward a particular kind of evidence.
    §4.4.3: an open-ended loop "elaborates around whatever it produced first",
    so several passes over the same cluster need different starting points to
    explore rather than paraphrase.
    """
    lines = [
        f"THEME CLUSTER {cluster['cluster_id']}: {cluster.get('label') or '(unlabelled)'}",
        f"Keyphrases: {cluster.get('keyphrases')}",
        "",
        "EVIDENCE — these are the only facts you may use:",
    ]
    for signal in cluster["signals"]:
        geographies = signal.get("geographies") or "[]"
        lines.append(
            f"- [{signal['id']}] ({signal['published_at']}, {signal['publisher']}, "
            f"tier {signal['tier']}, type {signal.get('signal_type') or 'unclassified'}, geo {geographies})\n"
            f"  {signal['title']}\n"
            f"  {signal['extract'][:500]}"
        )

    if target_cells:
        # §4.4.3 coverage-driven prompting: the pipeline knows which taxonomy
        # cells have evidence and no candidate yet, and targets generation at
        # exactly those cells. This turns brainstorming from "produce more
        # ideas" into "cover the evidenced grid", which terminates.
        lines += [
            "",
            "COVERAGE TARGETS — these taxonomy cells have evidence but no candidate yet.",
            "If and only if this cluster's evidence supports them, prioritise:",
        ]
        lines += [
            f"  - {c['vertical']} x {c['use_case']} x {c['technology']}" for c in target_cells[:10]
        ]

    if lens:
        lines += ["", f"THIS PASS'S LENS: {lens}",
                  "Other passes cover other angles, so do not try to be exhaustive here — "
                  "follow this lens and let it take you somewhere specific."]

    lines += [
        "",
        "Produce candidate opportunity spaces grounded strictly in the evidence above.",
        "Return JSON only.",
    ]
    return "\n".join(lines)


def critic_system_prompt(cfg: Config) -> str:
    """Adversarial critique pass (§4.4.3).

    "In practice the critic pass improves output quality more than any amount of
    prompt refinement on the generator." A different system prompt is the point:
    the critic is not the generator being asked to check itself.
    """
    return f"""MOCK_KIND=critic
You are a hostile reviewer of proposed innovation topics for Orange Business.
Your job is to REJECT weak candidates, not to be helpful. Assume the candidate
is generic until it proves otherwise.

{examples_block()}

Score the candidate 1-5 against ALL of these tests. The score is the MINIMUM of
your per-test judgements — one failure caps the whole score.

  A. SPECIFIC ENOUGH FOR A CIO. Could a salesperson put this in front of a CIO
     and have them recognise their own situation? "AI in industry" fails.
  B. EVERY CLAIM CITED. Is every `why_hot` claim supported by a cited signal id
     that actually appears in the evidence? An uncited claim fails this test.
  C. DISTINGUISHABLE. Is this meaningfully different from its neighbouring
     candidates, or is it the same topic with a synonym swapped?
  D. ACTIONABLE. Would a salesperson know what to actually say? Would a presales
     person know what to assemble?
  E. NO INVENTED FACTS. Does any claim state a number, date or fact absent from
     the evidence?

Scoring anchors:
  5 — as good as the client's own worked examples; ship it
  4 — specific and actionable, minor wording issues
  3 — borderline: real topic, but the statement is vague or a claim is thin
  2 — generic, or a claim is uncited
  1 — a technology theme wearing an opportunity's clothes, or contains invention

Return JSON:
{{"score": 1-5, "verdict": "accept"|"revise"|"reject",
  "issues": ["<specific, actionable>", ...],
  "revised_statement": "<only if verdict is revise; else null>"}}"""


def strategic_relevance_prompt(cfg: Config) -> str:
    """Rubric-scored strategic relevance (Table 23, §4.6).

    §4.6 score-compression guard: models asked to rate on 0-100 cluster their
    answers in a narrow band, so the rubric uses a small number of discrete
    levels with anchor examples, mapped to numbers afterwards.
    """
    strategy = cfg.strategy
    ambitions = "\n".join(f"  - {a['label']}: {a['content'].strip()}" for a in strategy["ambitions"])
    privileged = ", ".join(strategy.get("privileged_verticals", {}))
    return f"""MOCK_KIND=relevance
You score how strategically relevant an opportunity space is to Orange Business.

"{strategy['plan']}" ambitions:
{ambitions}

Privileged verticals (dedicated divisions): {privileged}
Cross-cutting: trust, sovereignty and compliance raise relevance wherever the
topic can be delivered on sovereign or certified infrastructure.
Divisional guidance: prefer a credible margin story over pure revenue volume.

Score on this DISCRETE 0-5 scale. Do not use intermediate values.
  5 — Squarely inside Innovative growth: a trusted B2B service, cyberdefence,
      trusted cloud or trusted AI, ideally in a privileged vertical.
  4 — Clearly serves one ambition with a credible Orange delivery story.
  3 — Plausibly connected to an ambition, but the connection needs an argument.
  2 — Adjacent: Orange could sell it, but it advances no stated ambition.
  1 — Weakly connected; would be a distraction from the plan.
  0 — Connects to none of the three ambitions. By the Group's own definition,
      not strategically relevant.

Return JSON:
{{"level": 0-5,
  "ambitions": ["<ambition id: customer_intimacy|innovative_growth|excellence_at_scale>", ...],
  "sovereignty_relevant": true|false,
  "rationale": "<two sentences, no invented numbers>"}}"""


def next_action_prompt(cfg: Config) -> str:
    """Role-specific next action (FR-17, AC-03, Table 23)."""
    modes = "\n".join(
        f"  - {m['id']} ({m['label']}): {m['description']} Primary action: {m['primary_action']}."
        for m in cfg.role_modes_raw["modes"]
    )
    return f"""You write the single next action a named role should take on an opportunity space.

ROLES
{modes}

Rules:
  - One sentence per role. Imperative. Concrete.
  - Ground it in the named Orange assets supplied to you. If none are supplied
    for a role, say what to find out, not what to claim.
  - Never invent a number, an offer name or a partner tier.
  - NEVER NAME A CUSTOMER OR PROSPECT ORGANISATION that is not in the supplied
    asset list. Naming a plausible-sounding account is the most damaging failure
    here, because a salesperson may repeat it as though it were a known Orange
    relationship.
      BAD:  "In a meeting with the head of security at Heathrow, say…"
            (Heathrow was never supplied — invented account)
      GOOD: "In a meeting with a major airport operator's head of security, say…"
      GOOD: "Reach out to Saint-Gobain Glass…"  (only if supplied as a reference)
  - Refer to unnamed prospects by ROLE AND SEGMENT instead: "a European airport
    operator", "a tier-1 automotive supplier".
  - The sales action must be something a person could actually say out loud in a
    customer meeting.

Return JSON:
{{"strategist": "...", "sales": "...", "presales": "...",
  "assets_named": ["<each Orange asset or customer organisation you named, verbatim>"]}}

`assets_named` is validated against the supplied list. Listing something that
was not supplied causes the action to be rejected, so name nothing you were not
given."""


def entailment_prompt() -> str:
    """Entailment check on key claims (§4.4.4 defence 4).

    "For the 'why hot' sentence, a cheap second-model pass verifies that the
    claim is entailed by the cited span. Cost is low because the text is short."
    """
    return """You verify whether a claim is supported by an evidence span.

Answer strictly on what the span says. Do not use outside knowledge. If the span
is merely ABOUT the same topic but does not state the claim, that is "unsupported".

Return JSON: {"supported": true|false, "reason": "<short>"}"""


def format_candidate_for_critic(candidate: dict[str, Any], evidence: list[dict[str, Any]],
                               neighbours: list[str]) -> str:
    lines = [
        "CANDIDATE",
        json.dumps(
            {k: candidate.get(k) for k in
             ("vertical", "use_case", "technology", "statement", "why_hot", "why_specific")},
            ensure_ascii=False, indent=2,
        ),
        "",
        "EVIDENCE AVAILABLE (cited ids must appear here):",
    ]
    for signal in evidence:
        lines.append(f"- [{signal['id']}] {signal['title']} ({signal['publisher']}, {signal['published_at']})")
        lines.append(f"  {signal['extract'][:300]}")
    if neighbours:
        lines += ["", "NEIGHBOURING CANDIDATES (test C — is this distinguishable?):"]
        lines += [f"  - {n}" for n in neighbours[:5]]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Long-form description and sales brief (FR-14, FR-17, FR-18)
# ---------------------------------------------------------------------------

#: Sections that assert something about the world, and therefore must cite the
#: evidence they were written from. The others describe what Orange would do or
#: ask — a proposal and a question cannot be "supported by a source", and
#: demanding a citation for them would only teach the model to attach one at
#: random (§4.4.4's binding rule works precisely because it is not decorative).
CITED_SECTIONS = ("what_is_changing", "competitive_landscape")

DESCRIPTION_SECTIONS = {
    "summary": "Two or three sentences a salesperson could read out. What the opportunity is, "
               "for whom, and why it exists now.",
    "what_is_changing": "What has changed in the market to open this. Regulation, technology "
                        "maturity, buying behaviour. EVERY claim cited.",
    "who_buys_and_why": "Which role signs, which role feels the pain, and what event triggers "
                        "them to act. Be concrete about the pain in operational terms.",
    "what_orange_would_deliver": "The shape of the engagement, built ONLY from the named Orange "
                                 "assets supplied. What is assembled, in what order.",
    "why_orange_can_win": "The specific reason Orange rather than the alternatives — named assets "
                          "only. If the assets are thin, say so plainly instead of inflating them.",
    "competitive_landscape": "Who else sells into this and how the customer will frame the "
                             "comparison. ONLY the competitors supplied, and say what each is "
                             "strong at. Cite the evidence where a competitor was named in it.",
    "risks_and_unknowns": "What would make this fail or stall, and what is genuinely not known "
                          "yet. A brief a salesperson trusts is one that admits something.",
}


def description_system_prompt(cfg: Config) -> str:
    """Long-form topic description (§4.9, FR-18).

    §4.9 says the topic page should answer the user's questions "in the order
    they arrive", and §4.13 asks the brief to be something a salesperson can act
    on. That needs prose — but prose is exactly where a model starts inventing,
    so the same four defences as synthesis apply (§4.4.4), plus the named-entity
    rule from the next-action prompt: naming a customer or a competitor that was
    not supplied is the failure most likely to be repeated in a meeting as if it
    were fact.
    """
    sections = "\n".join(f"  - {name}: {guidance}" for name, guidance in DESCRIPTION_SECTIONS.items())
    return f"""{orange_context_block(cfg)}

YOUR TASK
Write the detailed description of ONE opportunity space, for an Orange Business
sales and presales audience preparing a real customer conversation.

SECTIONS
{sections}

Plus a SOLUTION DIAGRAM and two practical blocks:
  - qualifying_questions: 4 to 6 questions to ask in a first meeting that would
    establish whether this customer actually has this problem. Specific enough
    that the answer changes what you do next. No generic discovery questions.
  - objection_handling: 2 to 4 objections this specific proposition will meet,
    each with a response that concedes what is true before answering.
  - diagram: the solution, drawn as layers. You are NOT drawing it — you are
    describing its structure, and the brief renders it. Three to five layers,
    ordered from the customer's business outcome at the top down to the field,
    site or device at the bottom. One to four boxes per layer. `provider` says
    who supplies each box: "orange" ONLY for a supplied Orange asset, named
    exactly as supplied; "partner" for a supplied partner; "customer" for
    something the customer already owns; "third_party" otherwise. Flows connect
    two boxes by their exact labels and say what moves between them.

ABSOLUTE RULES — a violation invalidates the section
1. EVIDENCE ONLY. The supplied evidence, Orange assets and competitor list are
   the only factual material you may use. You are organising what you were
   given, not recalling what you know.
2. CITE THE FACTUAL SECTIONS. {', '.join(CITED_SECTIONS)} must each carry a
   non-empty `signals` array of signal ids taken from the evidence block. An
   uncited factual section is discarded, not rewritten.
3. NO NUMBERS. Never state a market size, growth rate, percentage, monetary
   value or headcount. The brief carries computed figures from the sizing
   engine; anything you write would contradict them and be wrong.
4. NAME NOTHING YOU WERE NOT GIVEN. No customer, prospect, partner or competitor
   beyond the supplied lists. Refer to unnamed prospects by role and segment —
   "a European airport operator", "a tier-1 automotive supplier".
5. NO FILLER. If a section has nothing substantive behind it, write one honest
   sentence saying what is missing rather than three vague ones.

OUTPUT — a single JSON object:
{{
  "sections": {{
    "<section name>": {{"text": "<prose, 2-5 sentences>", "signals": ["SIG-...", ...]}}
  }},
  "qualifying_questions": ["<question>", ...],
  "objection_handling": [{{"objection": "<what they will say>", "response": "<answer>"}}],
  "diagram": {{
    "title": "<4-8 words>",
    "layers": [
      {{"label": "<layer name, 2-4 words>",
        "nodes": [{{"label": "<2-5 words>", "provider": "orange|partner|customer|third_party"}}]}}
    ],
    "flows": [{{"from": "<exact node label>", "to": "<exact node label>", "label": "<1-4 words>"}}],
    "caption": "<one sentence: what this picture tells a customer>"
  }},
  "entities_named": ["<every organisation you named, verbatim>"]
}}

`entities_named` is validated against the supplied lists. Naming something that
was not supplied causes that section to be dropped, so name nothing you were not
given."""


def format_topic_for_description(topic: dict[str, Any], signals: list[dict[str, Any]],
                                 assets: dict[str, list[str]], competition: dict[str, Any] | None,
                                 labels: dict[str, str]) -> str:
    """The evidence block for one topic (§4.4.2 element 3)."""
    lines = [
        f"OPPORTUNITY SPACE {topic['id']}",
        f"Statement: {topic['statement']}",
        f"Vertical: {labels['vertical']}",
        f"Use case: {labels['use_case']}",
        f"Technology: {labels['technology']}",
        f"Time horizon: {topic.get('horizon')} (basis: {topic.get('horizon_basis')})",
        f"Lifecycle state: {topic.get('state')}",
        "",
        "EVIDENCE — the only facts you may use. Cite by id:",
    ]
    for signal in signals[:20]:
        lines.append(
            f"- [{signal['id']}] ({signal['published_at']}, {signal['publisher']}, tier {signal['tier']})\n"
            f"  {signal['title']}\n  {signal['extract'][:420]}"
        )

    lines += ["", "EVIDENCE-BOUND CLAIMS ALREADY ESTABLISHED FOR THIS TOPIC:"]
    for claim in topic.get("why_hot") or []:
        lines.append(f"  - {claim.get('claim')}  [{', '.join(claim.get('signals', []))}]")

    lines += ["", "NAMED ORANGE ASSETS LINKED TO THIS TOPIC — the only assets you may name:"]
    if assets:
        for kind, values in sorted(assets.items()):
            lines.append(f"  {kind}: {', '.join(values[:6])}")
    else:
        lines.append("  (none linked — say plainly that there is no proof point yet)")

    if competition and competition.get("competitors"):
        lines += ["", f"COMPETITORS — the only competitors you may name. "
                      f"Assessed intensity: {competition['level_label'].upper()}."]
        for entry in competition["competitors"]:
            relationship = {"both": " (also an Orange partner)", "partner": " (Orange partner)"}.get(
                entry.get("relationship"), ""
            )
            mentioned = (" — named in evidence " + ", ".join(m["signal_id"] for m in entry.get("mentions", [])[:3])
                         if entry.get("basis") == "evidenced" else "")
            lines.append(f"  - {entry['label']} [{entry.get('type_label')}]{relationship}: "
                         f"{entry.get('why', '')}{mentioned}")
    else:
        lines += ["", "COMPETITORS: none identified. Say that the field looks open and that this "
                      "is worth verifying, rather than asserting there is no competition."]

    lines += [
        "",
        "For the diagram: the boxes marked `orange` must be assets from the list above, named "
        "exactly as they appear there. If no Orange asset is listed, mark every box `third_party` "
        "or `customer` and let the picture show honestly what would have to be assembled.",
        "",
        "Write the description. Return JSON only.",
    ]
    return "\n".join(lines)
