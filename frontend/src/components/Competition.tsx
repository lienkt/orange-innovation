import { useState } from 'react'
import type { Competition } from '../types'

/** §4.3.3 competitive landscape.
 *
 * Two things are shown and never conflated: the computed intensity level, and
 * the named list behind it. A level with no names is an opinion; the names with
 * their evidence are what a salesperson can actually use, and what a colleague
 * can correct when the register is wrong.
 */

export function IntensityBadge({ competition, onHelp }: {
  competition: Competition | null | undefined
  onHelp?: (topic: string) => void
}) {
  if (!competition) return null
  return (
    <span className="intensity" data-level={competition.level} title={competition.meaning}>
      {competition.level_label.toUpperCase()}
      <span style={{ fontSize: 10.5, fontWeight: 400, color: 'var(--text-muted)' }}>
        competition
      </span>
      {onHelp && (
        <button className="help-btn" aria-label="About competitive intensity"
                onClick={() => onHelp('competition')}>?</button>
      )}
    </span>
  )
}

export default function CompetitionPanel({ competition, onHelp }: {
  competition: Competition | null | undefined
  onHelp?: (topic: string) => void
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  if (!competition) {
    return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Not assessed yet.</div>
  }
  const { counts } = competition

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <IntensityBadge competition={competition} onHelp={onHelp} />
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {counts.evidenced} of {counts.listed} are named in this space's own sources
          {counts.partners_who_also_compete > 0 &&
            ` · ${counts.partners_who_also_compete} are also Orange partners`}
        </span>
      </div>
      <p style={{ fontSize: 11.5, color: 'var(--text-secondary)', margin: '4px 0 8px' }}>
        {competition.meaning}
      </p>

      {competition.competitors.map((entry) => (
        <div className="competitor-row" key={entry.id}>
          <div>
            <div className="competitor-name">
              {entry.label}
              {entry.relationship === 'both' && <span className="tag partner" style={{ marginLeft: 6 }}>also a partner</span>}
              {entry.relationship === 'partner' && <span className="tag partner" style={{ marginLeft: 6 }}>partner</span>}
            </div>
            <div className="competitor-why">{entry.type_label} · {entry.why}</div>
            {expanded === entry.id && (
              <div style={{ marginTop: 5 }}>
                {entry.note && <div className="competitor-why" style={{ marginBottom: 4 }}>{entry.note}</div>}
                {entry.mentions.length === 0 ? (
                  <div className="competitor-why">
                    None of this space's sources mention them. They are listed because Orange's own
                    competitor register says they sell this technology into this sector — true, and
                    not the same as proof they are in the deal.
                  </div>
                ) : (
                  entry.mentions.map((mention) => (
                    <div key={mention.signal_id} style={{ marginBottom: 5 }}>
                      <a className="sig-chip" href={mention.url} target="_blank" rel="noreferrer"
                         title={mention.title}>
                        {mention.signal_id} · {mention.publisher} · {mention.published_at}
                      </a>
                      <div className="competitor-why" style={{ marginTop: 2 }}>…{mention.quote}…</div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', gap: 5, alignItems: 'start' }}>
            <span className={`tag ${entry.basis === 'evidenced' ? 'evidenced' : ''}`}>
              {entry.basis === 'evidenced'
                ? `${entry.mentions.length} source${entry.mentions.length === 1 ? '' : 's'}`
                : 'no source yet'}
            </span>
            <button className="help-btn" aria-expanded={expanded === entry.id}
                    aria-label={`${expanded === entry.id ? 'Hide' : 'Show'} the evidence for ${entry.label}`}
                    title={entry.basis === 'evidenced'
                      ? 'Show the sources that name them'
                      : 'Why they are listed without a source'}
                    onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}>
              {expanded === entry.id ? '−' : '+'}
            </button>
          </div>
        </div>
      ))}

      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-muted)', marginTop: 8 }}>
        register {competition.register_version} · score {competition.score.toFixed(1)}
        {competition.inputs?.matched_but_not_listed
          ? ` · ${competition.inputs.matched_but_not_listed} further matches not listed`
          : ''}
      </div>
    </div>
  )
}
