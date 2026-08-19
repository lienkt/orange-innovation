import { useRef } from 'react'
import { useFocusTrap } from './Help'
import type { ScoreBlock, Topic } from '../types'

/** "How was this number calculated?" — for one specific topic.
 *
 * NFR-03 asks that "a reviewer outside the project can reconstruct why any
 * topic holds its rank", and DR-05 stores every component together with the
 * inputs used to compute it precisely so that is possible. This modal is that
 * promise made good: it shows the stored inputs, the arithmetic and the weight
 * applied — not a restatement of the score.
 *
 * §3.8 is the governing constraint: "the scoring model must not produce only a
 * number — it must explain the number, and if a user cannot explain why a topic
 * is ranked where it is, the scoring is not good enough."
 */

const COMPONENT_LABELS: Record<string, string> = {
  market_signal_strength: 'Market signal strength',
  source_diversity: 'Source diversity',
  evidence_quality: 'Evidence quality',
  novelty_momentum: 'Novelty and momentum',
  strategic_relevance: 'Strategic relevance',
  offer_match: 'Offer match',
  reference_density: 'Reference density',
  partner_coverage: 'Partner coverage',
  compliance_fit: 'Compliance fit',
  capability_depth: 'Capability depth',
  external_validation: 'External validation',
  technology_ownership: 'Technology ownership',
}

const QUESTION: Record<string, string> = {
  market_signal_strength: 'How visible is this topic in external sources, relative to everything else on the radar?',
  source_diversity: 'Does this appear across genuinely independent publishers, or is it one story repeated?',
  evidence_quality: 'How credible are the sources carrying it?',
  novelty_momentum: 'Is attention rising, flat, or falling?',
  strategic_relevance: 'Does it connect to a Trust the future ambition?',
  offer_match: 'Does an existing Orange offer address this?',
  reference_density: 'Do we have published proof points in this vertical?',
  partner_coverage: 'Can a partner supply the technology, and at what tier?',
  compliance_fit: 'Do we hold the certifications this vertical demands?',
  capability_depth: 'Do we have the people, at scale?',
  external_validation: 'Do analysts already recognise us here?',
  technology_ownership: 'Have we been building this ourselves?',
}

function num(value: unknown, digits = 2): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return Number.isInteger(value) ? String(value) : value.toFixed(digits)
}

function list(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return 'none'
  return value.map((v) => String(v).replace(/^[a-z_]+:/, '')).join(', ')
}

/** Turn the stored inputs into the sentence a reviewer actually needs. */
function explain(component: string, inputs: Record<string, any> | undefined) {
  if (!inputs) return <p className="se-note">No inputs were recorded for this component.</p>

  const row = (label: string, value: React.ReactNode) => (
    <div className="se-row" key={label}><span>{label}</span><b>{value}</b></div>
  )

  switch (component) {
    case 'market_signal_strength':
      return (
        <>
          <p className="se-note">
            Signal count is <b>log-compressed</b> so one noisy topic cannot saturate the scale, then
            normalised against the busiest topic on the radar. It measures relative visibility, not
            raw volume.
          </p>
          {row('Signals in the trailing window', num(inputs.signal_count))}
          {row('Busiest topic on the radar', num(inputs.corpus_max_signal_count))}
          {inputs.formula && row('Formula', <code>{String(inputs.formula)}</code>)}
          {inputs.note && <p className="se-note">{String(inputs.note)}</p>}
        </>
      )

    case 'source_diversity':
      return (
        <>
          <p className="se-note">
            Shannon entropy over the publisher distribution. Twenty outlets syndicating one press
            release count as <b>one</b> source, and vendor publishers count at a discount — so this
            resists the echo-chamber effect rather than rewarding it.
          </p>
          {row('Distinct publishers', num(inputs.distinct_publishers))}
          {row('Effective publishers (after tier discount)', num(inputs.effective_publishers))}
          {row('Syndicated copies collapsed', num(inputs.syndicated_collapsed))}
          {row('Entropy', `${num(inputs.shannon_entropy_bits)} of ${num(inputs.max_entropy_bits)} bits`)}
          {row('Breadth factor', num(inputs.breadth_factor))}
          {inputs.publishers && (
            <div className="se-sub">
              <div className="se-sub-title">Publishers counted</div>
              <div className="se-chips">
                {Object.entries(inputs.publishers as Record<string, number>).map(([p, w]) => (
                  <span className="se-chip" key={p}>{p} <b>{num(w)}</b></span>
                ))}
              </div>
            </div>
          )}
          {inputs.note && <p className="se-note">{String(inputs.note)}</p>}
        </>
      )

    case 'evidence_quality':
      return (
        <>
          <p className="se-note">
            A tier-weighted mean of the contributing signals. Tier 1 is authoritative (regulators,
            official statistics, procurement notices); tier 4 is an interested party (vendor
            marketing) and its contribution is <b>capped</b>, not merely discounted.
          </p>
          {inputs.tier_distribution && (
            <div className="se-sub">
              <div className="se-sub-title">Signals by tier</div>
              <div className="se-chips">
                {Object.entries(inputs.tier_distribution as Record<string, number>).map(([t, n]) => (
                  <span className="se-chip" key={t}>Tier {t} <b>{n}</b></span>
                ))}
              </div>
            </div>
          )}
          {row('Tier-weighted mean', num(inputs.tier_weighted_mean))}
          {row('Tier-4 share', num(inputs.tier4_share))}
          {inputs.tier4_cap_applied ? row('Tier-4 cap applied', 'yes') : null}
          {inputs.no_tier1_or_tier2_penalty_applied && (
            <p className="se-warn">
              No tier-1 or tier-2 evidence at all — a penalty of {num(inputs.penalty)} was applied.
              This is the “vendor-specific” case the requirements say must score low.
            </p>
          )}
        </>
      )

    case 'novelty_momentum':
      return (
        <>
          <p className="se-note">
            The slope of recency-weighted signal volume across the trailing periods. 50 is flat;
            above 50 attention is rising. Momentum is simply the trajectory of signal accretion,
            which is why it is checkable rather than asserted.
          </p>
          {Array.isArray(inputs.buckets_oldest_first) && (
            <div className="se-sub">
              <div className="se-sub-title">
                Signals per period (oldest → newest, {num(inputs.period_days)} days each)
              </div>
              <div className="se-spark">
                {(inputs.buckets_oldest_first as number[]).map((n, i) => {
                  const max = Math.max(...(inputs.buckets_oldest_first as number[]), 1)
                  return (
                    <div key={i} title={`${n} signal(s)`}>
                      <div style={{ height: `${(n / max) * 100}%` }} />
                      <span>{n}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          {row('Slope per period', num(inputs.slope_per_period))}
          {Number(inputs.first_appearance_bonus) > 0 &&
            row('First-appearance bonus', `+${num(inputs.first_appearance_bonus)}`)}
          {Number(inputs.long_flat_history_penalty) > 0 &&
            row('Long flat history penalty', `−${num(inputs.long_flat_history_penalty)}`)}
          {inputs.first_seen && row('First seen', String(inputs.first_seen))}
        </>
      )

    case 'strategic_relevance':
      return (
        <>
          <p className="se-note">
            Scored against the three <i>Trust the future</i> ambitions using a written rubric with
            anchored levels — discrete levels rather than a free 0–100 ask, because models asked to
            rate on a wide scale cluster their answers in a narrow band.
          </p>
          {row('Rubric level', `${num(inputs.rubric_level)} of 5`)}
          {row('Base from rubric level', num(inputs.base_from_rubric_level))}
          {inputs.rubric_ambitions && row('Ambitions matched', list(inputs.rubric_ambitions))}
          {inputs.privileged_vertical &&
            row('Privileged vertical', `${inputs.privileged_vertical} (+${num(inputs.privileged_bonus)})`)}
          {Number(inputs.sovereignty_bonus) > 0 &&
            row('Sovereignty bonus', `+${num(Number(inputs.sovereignty_bonus) * 100)}`)}
          {Array.isArray(inputs.sovereign_evidence) && inputs.sovereign_evidence.length > 0 && (
            <div className="se-sub">
              <div className="se-sub-title">Sovereign delivery evidence</div>
              <div className="se-chips">
                {(inputs.sovereign_evidence as string[]).map((e) => (
                  <span className="se-chip" key={e}>{e}</span>
                ))}
              </div>
            </div>
          )}
          {inputs.rubric_rationale && <p className="se-quote">“{String(inputs.rubric_rationale)}”</p>}
          {inputs.rubric_source && <p className="se-warn">{String(inputs.rubric_source)}</p>}
        </>
      )

    case 'offer_match':
      return (
        <>
          <p className="se-note">
            A graph lookup, not a model judgement. An offer scores full marks only when it addresses
            the use case <b>and</b> provides the technology.
          </p>
          {row('Direct offers (L0)', list(inputs.direct_offers))}
          {row('Bundle offers (L1)', list(inputs.bundle_offers))}
        </>
      )

    case 'reference_density':
      return (
        <>
          <p className="se-note">
            Published customer stories in this vertical, apportioned from the corpus. The
            distribution is very uneven, so this is a first-class input rather than something
            averaged away.
          </p>
          {row('Vertical', String(inputs.vertical ?? '—'))}
          {row('Published stories', num(inputs.published_story_count, 1))}
          {row('Gap threshold', num(inputs.threshold))}
          {row('Named references linked', list(inputs.named_references_linked))}
          {inputs.evidence_gap_warning && (
            <p className="se-warn">
              Below threshold — this topic carries an evidence-gap warning. A customer conversation
              here has no proof point behind it.
            </p>
          )}
        </>
      )

    case 'partner_coverage':
      return (
        <>
          <p className="se-note">
            Partner tier is an edge property in the graph and decays — tiers change, so links are
            re-validated on the catalogue refresh cycle.
          </p>
          {row('Partners providing the technology', list(inputs.partners))}
          {row('Best partner', String(inputs.best_partner ?? '—').replace('partner:', ''))}
          {row('Best tier rank', num(inputs.best_tier_rank))}
        </>
      )

    case 'compliance_fit':
      return (
        <>
          <p className="se-note">
            Certifications Orange holds that this vertical demands. Sovereign certifications count
            extra, because trust and sovereignty are a cross-cutting axis rather than one topic
            among others.
          </p>
          {row('Certifications', list(inputs.certifications))}
          {row('Of which sovereign', list(inputs.sovereign_certifications))}
        </>
      )

    case 'capability_depth':
      return (
        <>
          <p className="se-note">
            Expert headcount on a log scale — 7,000 experts is not seventeen times better than 400.
          </p>
          {row('Capability pools', list(inputs.pools))}
          {row('Total headcount', num(inputs.total_headcount))}
        </>
      )

    case 'external_validation':
      return (
        <>
          <p className="se-note">Analyst recognition covering this technology or use case.</p>
          {row('Analyst positions', list(inputs.analyst_positions))}
        </>
      )

    case 'technology_ownership':
      return (
        <>
          <p className="se-note">
            Whether Orange holds a named asset in this technology. Orange's own research precedes
            market signals by years, which is a stronger right-to-win statement than a CRM overlap
            count.
          </p>
          {row('Technology', String(inputs.technology ?? '—'))}
          {row('Orange asset', inputs.orange_asset ? 'yes' : 'no')}
          {inputs.note && <p className="se-warn">{String(inputs.note)}</p>}
        </>
      )

    default:
      return <pre className="se-raw">{JSON.stringify(inputs, null, 2)}</pre>
  }
}

function ScoreSection({ title, block, weights, subtitle }: {
  title: string; block: ScoreBlock | null; weights: Record<string, number>; subtitle: string
}) {
  if (!block) return null
  const entries = Object.entries(block.components).sort((a, b) => b[1] - a[1])
  const total = entries.reduce((sum, [k, v]) => sum + v * (weights[k] ?? 0), 0)
  return (
    <section className="se-section">
      <div className="se-head">
        <h4>{title}</h4>
        <span className="se-total">{block.score.toFixed(1)}</span>
      </div>
      <p className="se-sub-note">{subtitle}</p>

      <table className="se-table">
        <thead>
          <tr>
            <th>Component</th><th className="num">Value</th><th className="num">Weight</th>
            <th className="num">Contribution</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key}>
              <td>{COMPONENT_LABELS[key] ?? key}</td>
              <td className="num">{value.toFixed(1)}</td>
              <td className="num">×{weights[key] ?? 0}</td>
              <td className="num">{(value * (weights[key] ?? 0)).toFixed(1)}</td>
            </tr>
          ))}
          <tr className="se-sum">
            <td colSpan={3}>Weighted total</td>
            <td className="num">{total.toFixed(1)}</td>
          </tr>
        </tbody>
      </table>

      {entries.map(([key, value]) => (
        <details className="se-detail" key={key}>
          <summary>
            <b>{COMPONENT_LABELS[key] ?? key}</b> — {value.toFixed(1)}
            <span className="se-q">{QUESTION[key]}</span>
          </summary>
          <div className="se-body">{explain(key, block.inputs?.[key])}</div>
        </details>
      ))}
    </section>
  )
}

export default function ScoreExplainModal({ topic, weights, onClose }: {
  topic: Topic | null
  weights: { attractiveness: Record<string, number>; right_to_win: Record<string, number> }
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)

  // The same trap as the help dialog: Tab must not escape behind the backdrop.
  useFocusTrap(Boolean(topic), ref, onClose)

  if (!topic) return null

  return (
    <div className="help-backdrop" onClick={onClose} role="presentation">
      <div className="help-modal se-modal" role="dialog" aria-modal="true"
           aria-labelledby="se-title" tabIndex={-1} ref={ref}
           onClick={(e) => e.stopPropagation()}>
        <div className="help-head">
          <div>
            <h3 id="se-title">How this score was calculated</h3>
            <div className="se-topic">{topic.id} · {topic.statement}</div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="help-body">
          <p className="se-note" style={{ marginBottom: 14 }}>
            Every number below was computed from the stored inputs shown — nothing here is a
            restatement of the score. Expand a component to see the evidence it used. The two scores
            are deliberately <b>never combined</b>: they answer different questions and are owned by
            different people.
          </p>

          <ScoreSection
            title="Attractiveness"
            subtitle="Is the world moving? Computed from external evidence only."
            block={topic.attractiveness}
            weights={weights.attractiveness} />

          <ScoreSection
            title="Right to win"
            subtitle="Can we play, can we win? Computed from the Orange Business Graph as named query results — never asserted by a language model."
            block={topic.right_to_win}
            weights={weights.right_to_win} />

          {topic.conviction && topic.conviction.assessed > 0 && (
            <section className="se-section">
              <div className="se-head">
                <h4>Team conviction</h4>
                <span className="se-total">{topic.conviction.score?.toFixed(1) ?? '—'}</span>
              </div>
              <p className="se-sub-note">
                What the three roles say. This is a <b>third</b> quantity — it never alters either
                score above, and only changes what surfaces first for each role.
              </p>
              {Object.entries(topic.conviction.axes).map(([axis, block]) => (
                <div className="se-row" key={axis}>
                  <span>
                    {block.label}{' '}
                    <i style={{ color: 'var(--text-muted)' }}>
                      (n={block.n}{block.contested ? ', contested' : ''})
                    </i>
                  </span>
                  <b>{block.score.toFixed(0)}</b>
                </div>
              ))}
            </section>
          )}

          <section className="se-section">
            <div className="se-head"><h4>Reproducibility</h4></div>
            <p className="se-sub-note">
              Identical inputs and identical configuration produce identical output. These stamps are
              what make that checkable — and why a trajectory is never plotted across a weight-set
              boundary without saying so.
            </p>
            <div className="se-row"><span>Weight set</span><b>{topic.attractiveness?.weight_set ?? '—'}</b></div>
            <div className="se-row"><span>Pipeline version</span><b>{topic.provenance?.pipeline_version ?? '—'}</b></div>
            <div className="se-row"><span>Prompt version</span><b>{topic.provenance?.prompt_version ?? '—'}</b></div>
            <div className="se-row"><span>Model version</span><b>{topic.provenance?.model_version ?? '—'}</b></div>
            <div className="se-row"><span>Computed at</span><b>{topic.attractiveness?.computed_at ?? '—'}</b></div>
          </section>
        </div>
      </div>
    </div>
  )
}
