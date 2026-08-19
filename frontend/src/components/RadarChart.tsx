import { useMemo, useState } from 'react'
import type { Topic, VocabItem } from '../types'
import { formatEur } from './MarketSize'

/** The signature visual (§4.9 Radar view).
 *
 * "A polar layout where angular sectors are business domains, radial distance is
 * time horizon (Now at the centre, Later at the rim), marker size is
 * attractiveness and marker colour is right-to-win. This encodes four dimensions
 * without a legend anyone has to study, and it makes the two questions the radar
 * exists to answer — should we bet on it, can we win — visible simultaneously."
 *
 * Encoding choices, and why:
 *   angle  = domain      → POSITION carries identity, so no categorical hues are
 *                          needed and the all-pairs CVD cap never binds.
 *   radius = horizon     → ordinal position, Now at the centre.
 *   area   = attractiveness → area, not radius, so the perceived size is linear
 *                          in the value rather than quadratic in it.
 *   colour = right-to-win → a MAGNITUDE, so a sequential one-hue ramp. The ramp
 *                          is validated (see theme.css); colour never encodes
 *                          identity here.
 *
 * SC-12 is preserved visually as well as structurally: the two scores stay on
 * two different channels and are never combined into one mark property.
 */

const SIZE = 560
const CX = SIZE / 2
const CY = SIZE / 2
const R_MAX = 232
const R_MIN = 54

// Sector labels sit outside R_MAX and read outward, so the drawing needs more
// horizontal room than the plot circle itself. The viewBox is padded rather
// than the circle shrunk, so the marks keep their area.
const PAD_X = 104
const PAD_Y = 34
const VIEW_W = SIZE + PAD_X * 2
const VIEW_H = SIZE + PAD_Y * 2

/** Greedy wrap so long domain names stack instead of overflowing the viewBox. */
function wrapLabel(text: string, maxChars = 13): string[] {
  const words = text.split(' ')
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    if (!current) current = word
    else if ((current + ' ' + word).length <= maxChars) current += ' ' + word
    else { lines.push(current); current = word }
  }
  if (current) lines.push(current)
  return lines
}

const RINGS: { horizon: string; label: string; r: number }[] = [
  { horizon: 'now', label: 'NOW', r: R_MIN + (R_MAX - R_MIN) * 0.22 },
  { horizon: 'next', label: 'NEXT', r: R_MIN + (R_MAX - R_MIN) * 0.58 },
  { horizon: 'later', label: 'LATER', r: R_MIN + (R_MAX - R_MIN) * 0.95 },
]

const RTW_STEPS = ['var(--rtw-1)', 'var(--rtw-2)', 'var(--rtw-3)', 'var(--rtw-4)']

/** Bucket right-to-win onto the four validated ordinal steps.
 *
 * The breaks are quartiles of the score distribution the scorer actually
 * produces (measured over the live corpus: p25 48, median 55, p75 66), not even
 * quarters of the 0-100 range. Even quarters put 106 of 174 topics in one
 * bucket and 61% of the marks in a single colour, which is an encoding that
 * encodes nothing. The scale stays ordinal, single-hue and light-to-dark; only
 * where it cuts has changed, and the legend prints the cuts.
 */
export const RTW_BREAKS = [48, 55, 66]

export function rtwColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'var(--rtw-none)'
  if (score < RTW_BREAKS[0]) return RTW_STEPS[0]
  if (score < RTW_BREAKS[1]) return RTW_STEPS[1]
  if (score < RTW_BREAKS[2]) return RTW_STEPS[2]
  return RTW_STEPS[3]
}

/** Area-proportional radius, floored at 7px so every mark stays clickable.
 *
 * The domain is the band attractiveness actually occupies (measured: 23 to 84,
 * with 80% of topics between 43 and 78), not the nominal 0-100. Mapping the
 * nominal range gave every mark a radius within one pixel of every other — the
 * channel was spent and carried nothing. Area rather than radius, so the
 * perceived size stays linear in the score.
 */
const ATTRACTIVENESS_DOMAIN = [30, 85]

function markRadius(attractiveness: number | null | undefined): number {
  const value = Math.max(0, Math.min(100, attractiveness ?? 0))
  const [low, high] = ATTRACTIVENESS_DOMAIN
  const normalised = Math.max(0, Math.min(1, (value - low) / (high - low)))
  return 7 + Math.sqrt(normalised) * 15
}

interface Props {
  topics: Topic[]
  domains: VocabItem[]
  selectedId: string | null
  onSelect: (id: string) => void
}

interface Placed {
  topic: Topic
  x: number
  y: number
  r: number
  fill: string
}

export default function RadarChart({ topics, domains, selectedId, onSelect }: Props) {
  const [hover, setHover] = useState<{ topic: Topic; x: number; y: number } | null>(null)

  const sectors = domains.length || 1
  const sweep = (Math.PI * 2) / sectors

  const placed = useMemo<Placed[]>(() => {
    // Deterministic placement: topics in the same (domain, horizon) cell are
    // spread evenly across their sector so they never sit on top of each other.
    // No randomness — the same data must always draw the same picture (SC-11).
    const cells = new Map<string, Topic[]>()
    for (const topic of topics) {
      const domain = topic.domains[0] ?? '__none'
      const key = `${domain}|${topic.horizon ?? 'later'}`
      const bucket = cells.get(key)
      if (bucket) bucket.push(topic)
      else cells.set(key, [topic])
    }

    const out: Placed[] = []
    for (const [key, members] of cells) {
      const [domain, horizon] = key.split('|')
      const index = domains.findIndex((d) => d.id === domain)
      const sectorIndex = index >= 0 ? index : sectors - 1
      const ring = RINGS.find((r) => r.horizon === horizon) ?? RINGS[2]

      members.forEach((topic, i) => {
        // Start at -90° so sector 0 begins at the top.
        const base = sectorIndex * sweep - Math.PI / 2
        const inset = sweep * 0.12
        const span = sweep - inset * 2
        const frac = members.length === 1 ? 0.5 : i / (members.length - 1)
        const angle = base + inset + span * frac
        // Alternate radial offset so crowded cells fan out rather than overlap.
        const jitter = members.length > 1 ? ((i % 3) - 1) * 13 : 0
        const radius = Math.max(R_MIN + 8, Math.min(R_MAX - 6, ring.r + jitter))
        out.push({
          topic,
          x: CX + Math.cos(angle) * radius,
          y: CY + Math.sin(angle) * radius,
          r: markRadius(topic.attractiveness?.score),
          fill: rtwColor(topic.right_to_win?.score),
        })
      })
    }
    // Draw the largest first so small marks land on top and stay clickable.
    return out.sort((a, b) => b.r - a.r)
  }, [topics, domains, sectors, sweep])

  return (
    <div className="radar-wrap">
      <svg
        width="100%"
        viewBox={`${-PAD_X} ${-PAD_Y} ${VIEW_W} ${VIEW_H}`}
        style={{ maxWidth: VIEW_W, height: 'auto', display: 'block' }}
        role="img"
        aria-label="Innovation radar: business domain by sector, time horizon by distance from centre, attractiveness by marker size, right to win by marker colour."
      >
        {/* horizon rings */}
        {RINGS.map((ring) => (
          <circle key={ring.horizon} cx={CX} cy={CY} r={ring.r}
                  fill="none" stroke="var(--grid)" strokeWidth={1} />
        ))}
        <circle cx={CX} cy={CY} r={R_MIN} fill="none" stroke="var(--grid-strong)" strokeWidth={1} />

        {/* sector dividers */}
        {domains.map((_, i) => {
          const angle = i * sweep - Math.PI / 2
          return (
            <line key={i}
                  x1={CX + Math.cos(angle) * R_MIN} y1={CY + Math.sin(angle) * R_MIN}
                  x2={CX + Math.cos(angle) * R_MAX} y2={CY + Math.sin(angle) * R_MAX}
                  stroke="var(--grid)" strokeWidth={1} />
          )
        })}

        {/* Ring labels on one radial spoke only, so they are not repeated six
            times. The surface-coloured halo lets them sit over the divider. */}
        {RINGS.map((ring) => (
          <text key={ring.horizon} x={CX + 7} y={CY - ring.r + 12} className="ring-label"
                stroke="var(--surface-1)" strokeWidth={3} paintOrder="stroke">
            {ring.label}
          </text>
        ))}

        {/* sector labels */}
        {domains.map((domain, i) => {
          const angle = i * sweep - Math.PI / 2 + sweep / 2
          const radius = R_MAX + 20
          const x = CX + Math.cos(angle) * radius
          const y = CY + Math.sin(angle) * radius
          const cos = Math.cos(angle)
          const anchor = Math.abs(cos) < 0.3 ? 'middle' : cos > 0 ? 'start' : 'end'
          // Strip the "OX: " / "CX: " / "EX: " prefix — the sector position
          // already carries the grouping, so the prefix is noise here.
          const lines = wrapLabel(domain.label.replace(/^[A-Z]{2}:\s*/, ''))
          // Vertically centre multi-line labels on the sector's mid-angle.
          const dy0 = -((lines.length - 1) * 11) / 2
          return (
            <text key={domain.id} x={x} y={y} textAnchor={anchor} className="sector-label">
              {lines.map((line, li) => (
                <tspan key={li} x={x} dy={li === 0 ? dy0 : 11}>{line}</tspan>
              ))}
            </text>
          )
        })}

        {/* topic marks */}
        {placed.map((p) => {
          const selected = p.topic.id === selectedId
          return (
            <g key={p.topic.id}>
              <circle
                className="dot"
                cx={p.x} cy={p.y} r={p.r}
                fill={p.fill}
                // 2px surface ring keeps overlapping marks separable.
                stroke={selected ? 'var(--text-primary)' : 'var(--surface-1)'}
                strokeWidth={selected ? 2.5 : 2}
                tabIndex={0}
                role="button"
                aria-label={`${p.topic.statement}. Attractiveness ${Math.round(p.topic.attractiveness?.score ?? 0)}, right to win ${Math.round(p.topic.right_to_win?.score ?? 0)}.`}
                onClick={() => onSelect(p.topic.id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(p.topic.id) } }}
                onMouseMove={(e) => setHover({ topic: p.topic, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHover(null)}
                onFocus={(e) => {
                  const box = (e.target as SVGCircleElement).getBoundingClientRect()
                  setHover({ topic: p.topic, x: box.left + box.width / 2, y: box.top })
                }}
                onBlur={() => setHover(null)}
              />
              {/* Evidence-gap marks carry a shape cue as well as a border, so the
                  warning never depends on colour alone (SC-13). */}
              {p.topic.evidence_gap_warning && (
                <text x={p.x} y={p.y + 3.5} textAnchor="middle" fontSize={10}
                      fill="var(--surface-1)" fontWeight={700} style={{ pointerEvents: 'none' }}>
                  !
                </text>
              )}
            </g>
          )
        })}

        {placed.length === 0 && (
          <text x={CX} y={CY} textAnchor="middle" fill="var(--text-muted)" fontSize={13}>
            No topics match these filters
          </text>
        )}
      </svg>

      {hover && (
        <div className="tooltip" style={{ left: Math.min(hover.x + 14, window.innerWidth - 320), top: hover.y + 14 }}>
          <div className="tt-title">{hover.topic.statement}</div>
          <div className="tt-row"><span>Attractiveness</span><b>{hover.topic.attractiveness?.score?.toFixed(1) ?? '—'}</b></div>
          <div className="tt-row"><span>Right to win</span><b>{hover.topic.right_to_win?.score?.toFixed(1) ?? '—'}</b></div>
          <div className="tt-row"><span>Horizon</span><b>{hover.topic.horizon ?? '—'}</b></div>
          <div className="tt-row"><span>Portfolio distance</span><b>L{hover.topic.portfolio_distance}</b></div>
          <div className="tt-row"><span>Signals</span><b>{hover.topic.signal_count}</b></div>
          {/* The radar encodes four dimensions in position, size and colour; the
              two the strategist added last — how big and how contested — had no
              channel left, so they live here rather than nowhere. */}
          <div className="tt-row">
            <span>Serviceable market</span>
            <b>{hover.topic.market_size_summary
              ? `${formatEur(hover.topic.market_size_summary.sam_base)}/yr`
              : 'not sized'}</b>
          </div>
          <div className="tt-row">
            <span>Competition</span>
            <b className="intensity" data-level={hover.topic.competition?.level ?? 'none'}>
              {hover.topic.competition?.level_label?.toUpperCase() ?? '—'}
            </b>
          </div>
          {hover.topic.has_brief && (
            <div className="tt-row"><span>Sales brief</span><b>ready</b></div>
          )}
          {hover.topic.evidence_gap_warning && (
            <div className="tt-row" style={{ marginTop: 5, color: 'var(--status-serious)' }}>
              <span>⚠ Evidence gap in this vertical</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function RadarLegend() {
  return (
    <div className="radar-legend">
      <div className="ramp">
        <span className="legend-title">Right to win</span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>low</span>
        {RTW_STEPS.map((step) => <i key={step} style={{ background: step }} />)}
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>high</span>
      </div>
      <div className="size-demo">
        <span className="legend-title">Attractiveness</span>
        {[35, 60, 85].map((v) => (
          <i key={v} style={{ width: markRadius(v) * 2, height: markRadius(v) * 2 }} />
        ))}
      </div>
      <div><span className="legend-title">Sector</span>business domain</div>
      {/* Not "Distance": that word already means portfolio distance (L0-L4)
          everywhere else in the product, and one word cannot mean two axes. */}
      <div><span className="legend-title">Ring</span>time horizon, Now → Later</div>
      <div style={{ color: 'var(--status-serious)' }}>
        <span className="legend-title">!</span>evidence gap
      </div>
    </div>
  )
}
