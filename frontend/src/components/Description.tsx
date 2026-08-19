import { useState } from 'react'
import { api } from '../api'
import { useAnnounce } from './Announcer'
import type { Signal, TopicDescription } from '../types'

/** The generated long-form description (FR-14, FR-18).
 *
 * Three things travel with the prose, because prose is the part of this system
 * a reader is most likely to over-trust:
 *   the signal ids each factual section was written from, as links;
 *   what the evidence-binding and no-numbers checks REMOVED, rather than a
 *   silently shorter page;
 *   whether the topic has moved on since the text was written.
 */

/** The four providers, in the words the brief uses. A box that claimed to be an
 *  Orange asset without one behind it was already demoted server-side; this is
 *  only the display. */
const PROVIDER_LABEL: Record<string, string> = {
  orange: 'Orange asset',
  partner: 'Partner',
  customer: 'Customer already owns',
  third_party: 'Third party — to be sourced',
}

function Cites({ ids, signals }: { ids: string[]; signals?: Signal[] }) {
  if (!ids || ids.length === 0) return null
  const byId = new Map((signals ?? []).map((s) => [s.id, s]))
  return (
    <div className="desc-cites">
      {ids.map((id) => {
        const signal = byId.get(id)
        return (
          <a className="sig-chip" key={id} href={signal?.url ?? '#'} target="_blank" rel="noreferrer"
             title={signal ? `${signal.publisher} · ${signal.published_at} · tier ${signal.tier}\n${signal.title}` : id}>
            {id}{signal ? ` · t${signal.tier}` : ''}
          </a>
        )
      })}
    </div>
  )
}

export default function DescriptionPanel({ topicId, description, signals, onRegenerated, onHelp }: {
  topicId: string
  description: TopicDescription | null | undefined
  signals?: Signal[]
  onRegenerated?: () => void
  onHelp?: (topic: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const announce = useAnnounce()

  const generate = (force: boolean) => {
    setBusy(true)
    setError(null)
    announce('Writing the detailed description. This takes up to a minute.')
    api.generateDescription(topicId, force)
      .then((written) => {
        onRegenerated?.()
        const stripped = written?.stripped?.length ?? 0
        announce(`Description ready for ${topicId}.`
                 + (stripped ? ` ${stripped} section removed by the evidence checks.` : ''))
      })
      .catch((e) => {
        setError(String(e.message ?? e))
        announce(`Description generation failed: ${String(e.message ?? e)}`)
      })
      .finally(() => setBusy(false))
  }

  if (!description) {
    return (
      <div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 0 }}>
          No detailed description yet. It is written from this topic's own evidence and its named
          Orange assets and competitors — nothing else.
        </p>
        <button onClick={() => generate(false)} disabled={busy}>
          {busy ? <><span className="spinner" /> Writing…</> : 'Write the detailed description'}
        </button>
        {error && <p className="stale-note" style={{ marginTop: 8 }}>{error}</p>}
      </div>
    )
  }

  return (
    <div className={busy ? 'busy' : undefined}>
      {description.stale && (
        <div className="stale-note">
          Written against v{description.topic_version} of this topic, which has since changed.
          Regenerate before taking it to a customer.
        </div>
      )}

      {description.section_order.map((name) => {
        const section = description.sections[name]
        if (!section) return null
        return (
          <div className="desc-section" key={name}>
            <h5>{description.section_titles[name] ?? name}</h5>
            <p>{section.text}</p>
            <Cites ids={section.signals} signals={signals} />
          </div>
        )
      })}

      {description.diagram && (
        <div className="desc-section">
          <h5>Solution shape</h5>
          <p style={{ fontSize: 12.3, color: 'var(--text-secondary)' }}>{description.diagram.caption}</p>
          {/* Who provides each box is the whole point of the picture — it is the
              difference between "Orange delivers this" and "someone has to".
              The text version dropped it, which made the pane say less than the
              PDF about the one thing presales needs. */}
          <div className="diagram-layers">
            {description.diagram.layers.map((layer) => (
              <div className="diagram-layer" key={layer.label}>
                <div className="diagram-layer-label">{layer.label}</div>
                <div className="diagram-nodes">
                  {layer.nodes.map((node) => (
                    <span className="diagram-node" data-provider={node.provider} key={node.label}
                          title={PROVIDER_LABEL[node.provider]}>
                      {node.label}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="diagram-legend">
            {Object.entries(PROVIDER_LABEL).map(([provider, label]) => (
              <span key={provider}>
                <span className="diagram-swatch" data-provider={provider} aria-hidden /> {label}
              </span>
            ))}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Drawn with its flows in the PDF brief.
          </div>
        </div>
      )}

      {description.stripped.length > 0 && (
        <details style={{ marginBottom: 8 }}>
          <summary style={{ fontSize: 11.5, color: 'var(--text-muted)', cursor: 'pointer' }}>
            {description.stripped.length} section(s) removed by the evidence checks
          </summary>
          <ul className="qa-list" style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4 }}>
            {description.stripped.map((entry, index) => (
              <li key={index}><b>{entry.section}</b> — {entry.reason}</li>
            ))}
          </ul>
        </details>
      )}

      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <button onClick={() => generate(true)} disabled={busy}>
          {busy ? <><span className="spinner" /> Rewriting…</> : 'Regenerate'}
        </button>
        {onHelp && (
          <button className="help-btn" aria-label="How this description is written"
                  onClick={() => onHelp('description')}>?</button>
        )}
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-muted)' }}>
          {description.provenance.prompt_version} · {description.provenance.model_version} ·{' '}
          {description.generated_at.slice(0, 10)}
        </span>
      </div>
      {error && <p className="stale-note" style={{ marginTop: 8 }}>{error}</p>}
    </div>
  )
}
