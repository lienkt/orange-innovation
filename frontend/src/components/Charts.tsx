import { useMemo, useState } from 'react'
import { HelpButton } from './Help'

/** Chart primitives.
 *
 * Every chart here picks its colour by the JOB the data does, not by taste:
 *
 *   magnitude (how much)      -> sequential, one hue, light->dark
 *   position in a sequence    -> ordinal, one hue, monotone steps
 *   polarity (which side)     -> diverging, two hues + a NEUTRAL grey midpoint
 *   identity (which series)   -> categorical, fixed slot order, never cycled
 *
 * Palette values live in theme.css and are taken verbatim from the reference
 * instance in its documented order. Where a categorical chart uses slots that
 * sit below 3:1 on the light surface, it ships a legend AND a table view — the
 * relief rule, not an optional extra.
 */

export const CAT = ['var(--cat-1)', 'var(--cat-2)', 'var(--cat-3)',
                    'var(--cat-4)', 'var(--cat-5)', 'var(--cat-6)']
const SEQ = ['var(--seq-1)', 'var(--seq-2)', 'var(--seq-3)',
             'var(--seq-4)', 'var(--seq-5)', 'var(--seq-6)']
const ORD = ['var(--ord-1)', 'var(--ord-2)', 'var(--ord-3)', 'var(--ord-4)', 'var(--ord-5)']

export function Kpi({ value, label, sub }: { value: string | number; label: string; sub?: string }) {
  return (
    <div className="kpi">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

export function ChartCard({ title, note, children, help, onHelp, wide = false }: {
  title: string; note?: string; children: React.ReactNode
  help?: string; onHelp?: (topic: string) => void
  /** Take the whole row of the chart grid.
   *
   * For a chart whose width is structural rather than cosmetic: a bar list
   * reads fine in a 330px column, a fifteen-by-six matrix does not, and the
   * alternative to giving it the row is making the reader scroll sideways
   * through its own columns. */
  wide?: boolean
}) {
  return (
    <div className={`chart-card${wide ? ' chart-card-wide' : ''}`}>
      <h3 className="chart-title">
        {title}
        {help && onHelp && <HelpButton topic={help} onOpen={onHelp} />}
      </h3>
      {note && <p className="chart-note">{note}</p>}
      {children}
    </div>
  )
}

/** Horizontal bars for a magnitude comparison. One hue — bar length already
 *  encodes the value, so spending the identity channel on it would be waste. */
export function BarList({ data, ordinal = false, max, format }: {
  data: { label: string; value: number; hint?: string }[]
  ordinal?: boolean
  max?: number
  /** Money and counts are both magnitudes, but "6466326944" is not a label a
   *  reader can compare at a glance — the caller supplies its own formatter. */
  format?: (value: number) => string
}) {
  const ceiling = max ?? Math.max(...data.map((d) => d.value), 1)
  return (
    <div>
      {data.map((d, i) => (
        <div className="bar-row" key={d.label} title={d.hint}>
          <span style={{ color: 'var(--text-secondary)' }}>{d.label}</span>
          <div className="bar-track">
            <div className="bar-fill"
                 style={{
                   width: `${(d.value / ceiling) * 100}%`,
                   background: ordinal ? ORD[Math.min(i, ORD.length - 1)] : 'var(--seq-4)',
                 }} />
          </div>
          <span className="bar-num">{format ? format(d.value) : d.value}</span>
        </div>
      ))}
    </div>
  )
}

/** Stacked bar for part-to-whole across a small set of named series.
 *  Categorical is correct here — the series ARE the subject. */
export function StackedBar({ data }: { data: { label: string; value: number }[] }) {
  const [showTable, setShowTable] = useState(false)
  const total = data.reduce((a, b) => a + b.value, 0) || 1
  return (
    <div>
      <div className="bar-track" style={{ height: 22 }}>
        {data.map((d, i) => (
          <div key={d.label}
               className="bar-fill"
               title={`${d.label}: ${d.value}`}
               style={{
                 width: `${(d.value / total) * 100}%`,
                 background: CAT[i % CAT.length],
                 // 2px surface gap keeps adjacent segments separable.
                 marginRight: i < data.length - 1 ? 2 : 0,
               }} />
        ))}
      </div>
      {/* Identity is never colour-alone: legend always, table on demand. */}
      <div className="legend">
        {data.map((d, i) => (
          <span key={d.label}>
            <i style={{ background: CAT[i % CAT.length] }} />
            {d.label} <b style={{ fontFamily: 'var(--mono)' }}>{d.value}</b>
          </span>
        ))}
      </div>
      <button style={{ marginTop: 8, fontSize: 11, padding: '3px 8px' }}
              onClick={() => setShowTable((v) => !v)}>
        {showTable ? 'Hide' : 'Show'} table
      </button>
      {showTable && (
        <table className="data" style={{ marginTop: 8 }}>
          <thead><tr><th>Series</th><th className="num">Count</th><th className="num">Share</th></tr></thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.label}>
                <td>{d.label}</td>
                <td className="num">{d.value}</td>
                <td className="num">{((d.value / total) * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/** Vertical × domain occupancy. Magnitude on a grid -> heatmap, sequential.
 *  This is §4.5.5's white-space map as a picture rather than a document. */
export function Heatmap({ grid, onSelect }: {
  grid: {
    verticals: { id: string; label: string }[]
    domains: { id: string; label: string }[]
    cells: Record<string, { count: number; best_attractiveness: number; gap: boolean }>
    max_count: number
  }
  onSelect?: (vertical: string, domain: string) => void
}) {
  // The fill's step index, not just its colour: the label has to know which
  // step it is sitting on. Deciding the label from `count > max/2` while the
  // fill came from a six-step ramp put dark text on step 4 — measured at 2.18:1,
  // which is the count itself becoming unreadable on the cell it describes.
  const stepIndex = (count: number) => {
    if (count === 0) return 0
    const ratio = count / Math.max(grid.max_count, 1)
    return Math.min(SEQ.length - 1, Math.floor(ratio * (SEQ.length - 1)) + 1)
  }
  const step = (count: number) => (count === 0 ? 'var(--grid)' : SEQ[stepIndex(count)])

  return (
    <div>
      {/* `minmax(0, 1fr)`, not a pixel floor. A floor plus `overflow-x: auto` is
          how a grid ends up scrolling sideways inside a card that has room for
          it: the columns refuse to shrink, so the container gives up instead.
          Six columns of whatever is available always fits, and the row header
          scales with the card rather than holding 116px on a phone. */}
      <div className="heat-grid"
           style={{ gridTemplateColumns:
             `clamp(72px, 18%, 132px) repeat(${grid.domains.length}, minmax(0, 1fr))` }}>
        <div />
        {grid.domains.map((d) => (
          <div className="heat-head" key={d.id} title={d.label}>
            {/* Two short lines beat one clipped line: the column is ~52px and
                these labels are long, so a single truncated string collides
                with its neighbour and reads as noise. */}
            {d.label.replace(/^[A-Z]{2}:\s*/, '').split(' ').slice(0, 2).map((word, i) => (
              <span key={i}>{word}</span>
            ))}
          </div>
        ))}
        {grid.verticals.map((v) => (
          <>
            <div className="heat-rowhead" key={`h-${v.id}`} title={v.label}>
              <span>{v.label}</span>
            </div>
            {grid.domains.map((d) => {
              const cell = grid.cells[`${v.id}|${d.id}`]
              const n = cell?.count ?? 0
              return (
                <div className="heat-cell"
                     data-step={stepIndex(n)}
                     key={`${v.id}-${d.id}`}
                     onClick={() => n > 0 && onSelect?.(v.id, d.id)}
                     title={n === 0 ? `${v.label} × ${d.label}: no topics — unevidenced or unexplored`
                                    : `${v.label} × ${d.label}: ${n} topic(s), best attractiveness ${cell.best_attractiveness.toFixed(0)}${cell.gap ? ' — evidence gap' : ''}`}
                     style={{
                       background: step(n),
                       // Which ink to use is a property of the PALETTE, not of
                       // this component: the sequential ramp runs light-to-dark
                       // in the light theme and dark-to-light in the dark one,
                       // so the step goes out as a data attribute and theme.css
                       // decides. Hardcoding it here got the dark theme exactly
                       // backwards.
                       outline: cell?.gap ? '1.5px solid var(--status-serious)' : 'none',
                       outlineOffset: -1.5,
                     }}>
                  {/* The count gets its own ground rather than sitting directly
                      on the fill. One step of the sequential ramp (#2a78d6) is
                      exactly in the middle — white reads 4.42:1 on it and black
                      4.29:1, so NEITHER ink clears AA — and the ramp itself may
                      not be re-stepped: its documented order is the
                      colourblind-safety mechanism. A small plate fixes the
                      label's contrast without touching the encoding. */}
                  {n ? <span className="heat-count">{n}</span> : ''}
                </div>
              )
            })}
          </>
        ))}
      </div>
      <div className="legend">
        <span>Topics per cell</span>
        {SEQ.slice(1).map((c) => <i key={c} style={{ background: c, width: 16 }} />)}
        <span style={{ color: 'var(--status-serious)' }}>▢ evidence gap</span>
      </div>
    </div>
  )
}

/** Internal conviction vs the external score. Polarity -> DIVERGING, centred on
 *  zero with a neutral grey midpoint, so "we agree" reads as nothing at all. */
export function DivergenceChart({ rows, onSelect }: {
  rows: {
    id: string; statement: string
    divergence: { flags: { axis_label: string; delta: number; internal: number; external: number; external_label: string; reading: string }[] }
  }[]
  onSelect?: (id: string) => void
}) {
  const flat = useMemo(
    () => rows.flatMap((r) => r.divergence.flags.map((f) => ({ ...f, id: r.id, statement: r.statement }))),
    [rows],
  )
  if (flat.length === 0) {
    return (
      <p style={{ color: 'var(--text-muted)', fontSize: 12.5, margin: 0 }}>
        No topic yet shows a material gap between what the evidence says and what the team says.
        Divergence appears here once roles have assessed enough topics — it is the review queue,
        not an error state.
      </p>
    )
  }
  const scale = Math.max(...flat.map((f) => Math.abs(f.delta)), 50)
  return (
    <div>
      {flat.slice(0, 14).map((f, i) => {
        const pct = (Math.abs(f.delta) / scale) * 50
        const positive = f.delta > 0
        return (
          <div className="div-row" key={`${f.id}-${f.axis_label}-${i}`}
               onClick={() => onSelect?.(f.id)} style={{ cursor: 'pointer' }} title={f.reading}>
            <span style={{ textAlign: 'right', color: 'var(--text-secondary)', overflow: 'hidden',
                           textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {f.id} · {f.axis_label}
            </span>
            <div className="div-bar">
              <div className="div-axis" />
              <div className="div-seg"
                   style={{
                     background: positive ? 'var(--div-pos)' : 'var(--div-neg)',
                     left: positive ? '50%' : `${50 - pct}%`,
                     width: `${pct}%`,
                   }} />
            </div>
            <span className="bar-num" style={{ textAlign: 'left' }}>
              {f.delta > 0 ? '+' : ''}{f.delta}
            </span>
          </div>
        )
      })}
      <div className="legend">
        <span><i style={{ background: 'var(--div-neg)' }} />team rates BELOW the evidence</span>
        <span><i style={{ background: 'var(--div-pos)' }} />team rates ABOVE the evidence</span>
      </div>
    </div>
  )
}

/** Signal accretion over time — momentum made visible.
 *  §4.6 computes momentum as the slope of this series, so showing the shape
 *  lets a reader check the number rather than trust it. */
export function EvidenceTimeline({ months }: { months: { month: string; n: number }[] }) {
  if (!months.length) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No dated evidence attached yet.</p>
  }
  const max = Math.max(...months.map((m) => m.n), 1)
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 70 }}>
        {months.map((m) => (
          <div key={m.month} title={`${m.month}: ${m.n} signal(s)`}
               style={{ flex: 1, minWidth: 6, display: 'flex', flexDirection: 'column',
                        justifyContent: 'flex-end', height: '100%' }}>
            <div style={{
              height: `${(m.n / max) * 100}%`,
              background: 'var(--seq-4)',
              borderRadius: '3px 3px 0 0',
              minHeight: 2,
            }} />
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4,
                    fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
        <span>{months[0].month}</span>
        <span>{months[months.length - 1].month}</span>
      </div>
    </div>
  )
}

/** Stage-gate funnel. Stages are an ORDERED sequence, so the colour ramp is
 *  ordinal — the reader sees the order in the colour. */
export function StageFunnel({ stages }: { stages: { id: string; label: string; count: number }[] }) {
  const max = Math.max(...stages.map((s) => s.count), 1)
  return (
    <div>
      {stages.map((s, i) => (
        <div className="bar-row" key={s.id}>
          <span style={{ color: 'var(--text-secondary)' }}>{s.label}</span>
          <div className="bar-track">
            <div className="bar-fill"
                 style={{ width: `${(s.count / max) * 100}%`, background: ORD[Math.min(i, ORD.length - 1)] }} />
          </div>
          <span className="bar-num">{s.count}</span>
        </div>
      ))}
    </div>
  )
}
