import type { ScoreBlock } from '../types'

/** NFR-01: every displayed number decomposes into named components.
 *
 * §3.8: "the scoring model must not produce only a number — it must explain the
 * number." §4.9 is explicit that the breakdown is "expanded rather than hidden
 * behind a tooltip", so it renders inline, always.
 *
 * The weight set is shown next to the score because §4.6's calibration-drift
 * guard makes scores from different weight sets incomparable — the reader has to
 * be able to see which one produced this number.
 */

const LABELS: Record<string, string> = {
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

interface Props {
  title: string
  block: ScoreBlock | null
  weights?: Record<string, number>
}

export default function ScoreBreakdown({ title, block, weights }: Props) {
  if (!block) {
    return (
      <div className="score-block">
        <div className="score-name">{title}</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Not yet scored.</div>
      </div>
    )
  }
  const entries = Object.entries(block.components).sort((a, b) => b[1] - a[1])
  return (
    <div className="score-block">
      <div className="score-head">
        <span className="score-value">{block.score.toFixed(1)}</span>
        <span className="score-name">{title}</span>
        <span className="badge" style={{ marginLeft: 'auto' }} title="Weight set that produced this score (SC-10)">
          {block.weight_set}
        </span>
      </div>
      {entries.map(([key, value]) => {
        const weight = weights?.[key]
        return (
          <div className="component" key={key}>
            <div>
              <div className="component-label">
                {LABELS[key] ?? key}
                {weight !== undefined && (
                  <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: 10 }}>
                    {' '}×{weight}
                  </span>
                )}
              </div>
              <div className="component-track">
                <div className="component-fill" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
              </div>
            </div>
            <div className="component-num">{value.toFixed(0)}</div>
          </div>
        )
      })}
    </div>
  )
}
