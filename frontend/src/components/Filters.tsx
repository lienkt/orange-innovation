import type { FilterState, Meta } from '../types'
import { EMPTY_FILTERS } from '../types'

/** AC-04 / FR-12: multi-select on at least vertical, geography, domain and
 * persona, plus free-text search over statements and signals (§4.9) — and, since
 * §4.3.3 and §4.3.4 gave every space a competitive intensity and a market size,
 * those too. A fact the radar computes and displays but cannot filter on is a
 * fact a strategist has to eyeball across 148 rows.
 *
 * Counts come from the SERVER, over every topic the role can see, not from the
 * capped page: a rail that showed "CISO 0" because none of the 24 visible rows
 * carried that persona — while 37 matched — trained people not to trust it.
 */

interface Props {
  meta: Meta
  /** True while the view request is in flight — "none matched" and "not here
   *  yet" are opposite messages and must not share a rendering. */
  loading?: boolean
  filters: FilterState
  onChange: (next: FilterState) => void
  geographies: string[]
  /** Server-computed facet counts for the current role and result set. */
  facets: Record<string, Record<string, number>>
  totalMatching: number
}

function MultiSelect({
  title, items, selected, onToggle, counts, hint,
}: {
  title: string
  items: { id: string; label: string }[]
  selected: string[]
  onToggle: (id: string) => void
  counts?: Record<string, number>
  hint?: string
}) {
  // A value that matches nothing is still shown, greyed, rather than hidden:
  // "there are none of these" is information, and a list that silently changes
  // length as you filter is disorienting.
  return (
    <div className="filter-group">
      <h3 title={hint}>{title}{selected.length > 0 && ` · ${selected.length}`}</h3>
      <div className="filter-list">
        {items.map((item) => {
          // An explicit 0 rather than a blank: a missing count reads as "this
          // filter is broken", where "0" reads as "none of these right now".
          const count = counts === undefined ? undefined : (counts[item.id] ?? 0)
          const empty = count === 0 && !selected.includes(item.id)
          return (
            <label className={`filter-item${empty ? ' filter-item-zero' : ''}`} key={item.id}
                   title={count === undefined ? item.label : `${item.label} — ${count} space${count === 1 ? '' : 's'}`}>
              <input
                type="checkbox"
                checked={selected.includes(item.id)}
                onChange={() => onToggle(item.id)}
              />
              <span>{item.label}</span>
              {count !== undefined && <span className="filter-count">{count}</span>}
            </label>
          )
        })}
      </div>
    </div>
  )
}

export default function Filters({ meta, filters, onChange, geographies, facets, totalMatching, loading }: Props) {
  const toggle = (key: keyof FilterState) => (id: string) => {
    const current = filters[key] as string[]
    onChange({
      ...filters,
      [key]: current.includes(id) ? current.filter((v) => v !== id) : [...current, id],
    })
  }

  const active =
    filters.vertical.length + filters.domain.length + filters.persona.length +
    filters.geography.length + filters.horizon.length + filters.competition.length +
    (filters.has_brief ? 1 : 0) + (filters.q ? 1 : 0)

  return (
    <>
      <div className="filter-group">
        <h3>Search</h3>
        <input
          className="search-input"
          type="search"
          placeholder="Statements and claims…"
          value={filters.q}
          onChange={(e) => onChange({ ...filters, q: e.target.value })}
        />
      </div>

      <div className="filter-summary" aria-live="polite">
        {loading ? 'Counting…' : `${totalMatching} space${totalMatching === 1 ? '' : 's'} match this role and filter`}
      </div>

      {active > 0 && (
        <button style={{ width: '100%', marginBottom: 16 }} onClick={() => onChange({ ...EMPTY_FILTERS })}>
          Clear {active} filter{active === 1 ? '' : 's'}
        </button>
      )}

      <MultiSelect
        title="Horizon"
        items={meta.horizons.map((h) => ({ id: h, label: h.toUpperCase() }))}
        selected={filters.horizon}
        onToggle={toggle('horizon')}
        counts={facets.horizon}
      />
      <MultiSelect
        title="Competition"
        hint="How crowded the field is (§4.3.3) — named competitors, scored"
        items={(meta.competition_levels ?? [{ id: 'none' }, { id: 'low' }, { id: 'medium' }, { id: 'high' }])
          .map((level) => ({ id: level.id, label: level.id.toUpperCase() }))}
        selected={filters.competition}
        onToggle={toggle('competition')}
        counts={facets.competition}
      />

      <div className="filter-group">
        <h3>Ready to sell</h3>
        <label className="filter-item">
          <input type="checkbox" checked={filters.has_brief}
                 onChange={() => onChange({ ...filters, has_brief: !filters.has_brief })} />
          <span>Has a sales brief</span>
          <span className="filter-count">{facets.with_brief?.true ?? 0}</span>
        </label>
      </div>

      <MultiSelect
        title="Vertical"
        items={meta.verticals}
        selected={filters.vertical}
        onToggle={toggle('vertical')}
        counts={facets.vertical}
      />
      <MultiSelect
        title="Domain"
        items={meta.domains}
        selected={filters.domain}
        onToggle={toggle('domain')}
        counts={facets.domain}
      />
      <MultiSelect
        title="Persona"
        items={meta.personas}
        selected={filters.persona}
        onToggle={toggle('persona')}
        counts={facets.persona}
      />
      {geographies.length > 0 && (
        <MultiSelect
          title="Geography"
          items={geographies.map((g) => ({ id: g, label: g }))}
          selected={filters.geography}
          onToggle={toggle('geography')}
          counts={facets.geography}
        />
      )}
    </>
  )
}
