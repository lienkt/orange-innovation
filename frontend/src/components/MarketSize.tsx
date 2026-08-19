import { useState } from 'react'
import type { MarketSize, SizeFactor } from '../types'

/** §4.3.4 market opportunity.
 *
 * The section's job is not to show a number — it is to show a number you can
 * argue with. §4.3.4 is explicit that headline market figures "are quoted
 * without methodology and frequently conflict by an order of magnitude", so
 * every factor is on screen with its source, its year and whether it was
 * observed, proxied or assumed. The working is the product; the figure is a
 * by-product of it.
 */

export function formatEur(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const abs = Math.abs(value)
  if (abs >= 1e9) return `€${(value / 1e9).toFixed(1)}bn`
  if (abs >= 1e6) return `€${(value / 1e6).toFixed(value / 1e6 >= 100 ? 0 : 1)}m`
  if (abs >= 1e3) return `€${(value / 1e3).toFixed(0)}k`
  return `€${Math.round(value).toLocaleString()}`
}

function factorValue(factor: SizeFactor): string {
  if (factor.unit.includes('EUR')) return formatEur(factor.value)
  if (factor.unit.startsWith('%')) return `${factor.value.toFixed(1)}%`
  return Math.round(factor.value).toLocaleString()
}

function Band({ label, band, note, modelled }: {
  label: string
  band: { low: number | null; base: number | null; high: number | null }
  note?: string
  modelled?: boolean
}) {
  return (
    <div className={`size-cell${modelled ? ' modelled' : ''}`} title={note}>
      <div className="k">{label}</div>
      <div className="v">{formatEur(band.base)}</div>
      <div className="r">{formatEur(band.low)} – {formatEur(band.high)}</div>
      {note && <div className="n">{note}</div>}
    </div>
  )
}

function Factor({ factor }: { factor: SizeFactor }) {
  const [open, setOpen] = useState(false)
  const source = factor.source ?? {}
  const origin = [source.publisher, source.dataset, source.indicator].filter(Boolean).join(' · ')
  return (
    <div style={{ borderBottom: '1px solid var(--border)', padding: '7px 0' }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12.5, fontWeight: 550 }}>{factor.label}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{factorValue(factor)}</span>
        <span className={`basis ${factor.basis}`}>{factor.basis}</span>
        {/* Five buttons all named "?" are five identical stops in a screen
            reader's element list; the name has to say which factor it opens. */}
        <button className="help-btn" aria-expanded={open}
                aria-label={`${open ? 'Hide' : 'Show'} where the ${factor.label.toLowerCase()} figure comes from`}
                title="Where this number comes from"
                onClick={() => setOpen((v) => !v)}>{open ? '−' : '?'}</button>
      </div>
      <div className="factor-note">
        {origin || '—'}{source.period ? ` · ${source.period}` : ''}
      </div>
      {open && (
        <div style={{ marginTop: 5 }}>
          {factor.note && <p className="factor-note" style={{ marginBottom: 4 }}>{factor.note}</p>}
          {factor.low !== null && factor.high !== null && (
            <p className="factor-note">
              Range used: {factorValue({ ...factor, value: factor.low })} – {factorValue({ ...factor, value: factor.high })}
            </p>
          )}
          {source.url && (
            <p className="factor-note">
              <a href={source.url} target="_blank" rel="noreferrer">{source.dataset ?? 'source'}</a>
              {source.licence ? ` — ${source.licence}` : ''}
            </p>
          )}
          {Array.isArray(factor.detail?.examples) && factor.detail.examples.length > 0 && (
            <div className="scroll-x" style={{ marginTop: 4 }}>
              <table className="data">
                <thead><tr><th>Contract</th><th className="num">Value</th><th>Date</th></tr></thead>
                <tbody>
                  {factor.detail.examples.slice(0, 4).map((row: any) => (
                    <tr key={row.signal_id}>
                      <td><a href={row.url} target="_blank" rel="noreferrer">{row.title}</a></td>
                      <td className="num">{formatEur(row.value_eur)}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{row.published_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {Array.isArray(factor.detail?.trend) && factor.detail.trend.length > 0 && (
            <p className="factor-note">
              Adoption trend:{' '}
              {factor.detail.trend.slice(0, 2).map((t: any, i: number) => (
                <span key={i}>
                  {i > 0 && '; '}
                  {t.nace} {t.from.rate_pc}% ({t.from.period}) → {t.to.rate_pc}% ({t.to.period})
                </span>
              ))}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function MarketSizePanel({ sizes, onHelp }: {
  sizes: MarketSize[]
  onHelp?: (topic: string) => void
}) {
  const [method, setMethod] = useState(0)
  if (!sizes || sizes.length === 0) {
    return (
      <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        Not sized. The reference data covers the European business economy; a space outside it, or
        one whose technology has no published adoption series, is left unsized rather than
        estimated (§4.3.4).
      </div>
    )
  }
  const size = sizes[Math.min(method, sizes.length - 1)]
  const outside = size.coverage?.outside_reference_data ?? []
  // Modelling choices are declared, not graded: they are assumptions by design.
  const MODELLED = ['obtainable_share', 'size_mix']
  const evidenceFactors = size.factors.filter((f) => !MODELLED.includes(f.name))
  const modelledFactors = size.factors.filter((f) => MODELLED.includes(f.name))
  const observedCount = evidenceFactors.filter((f) => f.basis === 'observed').length

  return (
    <div>
      {sizes.length > 1 && (
        <div className="tabs" role="group" aria-label="Sizing method" style={{ marginBottom: 8 }}>
          {sizes.map((entry, index) => (
            <button key={entry.method} aria-pressed={index === method} onClick={() => setMethod(index)}
                    style={{ fontSize: 11.5 }}
                    title={entry.method === 'bottom_up_adoption'
                      ? 'Enterprises x adoption rate x contract value (§4.3.4)'
                      : 'Contracts that actually exist, annualised — a floor, not a market'}>
              {entry.method === 'bottom_up_adoption' ? 'Bottom-up' : 'Observed tenders'}
            </button>
          ))}
        </div>
      )}

      <div className="size-head">
        <span className="size-figure">{formatEur(size.sam.base)}</span>
        <span className="size-range">serviceable, per year</span>
        {/* The grade describes the EVIDENCE going in — enterprises, adoption,
            contract value. The two modelling choices (size-class weighting, and
            the obtainable share) are assumptions by construction and are excluded
            from it, which reads as a contradiction unless it is said out loud
            next to the badge rather than buried in a help modal. */}
        <span className={`basis ${size.confidence}`}
              title={`Grade of the EVIDENCE: ${observedCount} of ${evidenceFactors.length} `
                + `input factors observed. The worst basis wins — never an average. `
                + `The modelling choices below are assumptions by design and are not graded.`}>
          {size.confidence} evidence
        </span>
        {onHelp && (
          <button className="help-btn" aria-label="About market sizing" title="How is this sized?"
                  onClick={() => onHelp('market_size')}>?</button>
        )}
      </div>

      <div className="size-grid">
        <Band label="Total (TAM)" band={size.tam} note="every adopter in scope" />
        <Band label="Serviceable (SAM)" band={size.sam} note="the part Orange serves" />
        <Band label="Obtainable (SOM)" band={size.som} modelled
              note={`a planning assumption: SAM × ${
                (size.factors.find((f) => f.name === 'obtainable_share')?.value ?? 0).toFixed(1)
              }%, keyed to right to win`} />
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
        {size.method_label} · geography {(size.coverage?.used ?? []).join(', ') || '—'}
        {outside.length > 0 && ` · ${outside.length} declared geography(ies) outside the reference data`}
      </div>

      <details>
        <summary style={{ fontSize: 11.5, color: 'var(--text-muted)', cursor: 'pointer', marginBottom: 6 }}>
          Show the working — {evidenceFactors.length} measured input
          {evidenceFactors.length === 1 ? '' : 's'}, {modelledFactors.length} modelling choice
          {modelledFactors.length === 1 ? '' : 's'}
        </summary>
        <div className="factor-group">
          <h6>Measured — this is what the grade is about</h6>
          {evidenceFactors.map((factor) => <Factor key={factor.name} factor={factor} />)}
        </div>
        {modelledFactors.length > 0 && (
          <div className="factor-group">
            <h6>Modelled — declared assumptions, owned in config, not evidence</h6>
            {modelledFactors.map((factor) => <Factor key={factor.name} factor={factor} />)}
          </div>
        )}
      </details>

      {size.caveats.length > 0 && (
        <details>
          <summary style={{ fontSize: 11.5, color: 'var(--text-muted)', cursor: 'pointer', margin: '8px 0 4px' }}>
            Read before quoting the number — {size.caveats.length} caveats
          </summary>
          <ul className="qa-list" style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
            {size.caveats.map((caveat, index) => <li key={index}>{caveat}</li>)}
          </ul>
        </details>
      )}

      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-muted)', marginTop: 8 }}>
        sizing {size.sizing_version} · computed {size.computed_at.slice(0, 10)}
      </div>
    </div>
  )
}
