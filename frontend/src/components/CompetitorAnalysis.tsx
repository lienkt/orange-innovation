import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { CompetitorAnalysis, CompetitorAnalysisEntry } from '../types'

/** The competitor analysis pane (§4.3.3 extension).
 *
 * `competition.py` answers "how crowded is this space" with a level over a
 * named list. This pane answers the two questions that follow and that a level
 * cannot: what is each of those competitors actually doing here, and what does
 * Orange say when the customer names one of them.
 *
 * Two registers are shown and never blended, on the same principle the rest of
 * the interface follows for computed-versus-written:
 *
 *   FROM THEIR OWN PAGES   a join over stored data — their claims, filtered to
 *                          this taxonomy cell, each carrying the page it came
 *                          from. Free, reproducible, always present.
 *   WRITTEN COMPARISON     a model comparing two companies. Costs a call, so it
 *                          is absent until asked for, and it is labelled.
 *
 * The differentiation paragraph is the part a salesperson actually uses, so it
 * gets the strongest visual treatment — and the strictest rule behind it: it may
 * only name Orange assets linked to this topic, and where none are linked it has
 * to say Orange would be competing on price and delivery instead. A fabricated
 * advantage is not caught in review, it is caught in the meeting.
 */

const STATUS_NOTE: Record<string, string> = {
  blocked: 'Their site refuses automated clients, so their published position is unread. '
    + 'We record that rather than working around it.',
  unreachable: 'Their site could not be reached from our network, so their published position is unread.',
  no_pages: 'Nothing on their site survived filtering, so their published position is unread.',
  unread: 'Not profiled yet — their site has not been read.',
}

function CoverageBar({ analysis }: { analysis: CompetitorAnalysis }) {
  const c = analysis.coverage ?? {}
  const reg = c.register
  const unread = (c.blocked ?? 0) + (c.unread ?? 0)
  return (
    <div className="ca-coverage">
      <span>
        <strong>{c.profiled ?? 0}</strong> of <strong>{c.on_topic ?? 0}</strong> competitors on this
        space have been read from their own site
      </span>
      {unread > 0 && (
        <span className="ca-gap">
          {unread} unread — the comparison below is that much thinner, and says so per competitor
        </span>
      )}
      {reg && (
        <span className="ca-muted">
          register {reg.register_version} · {reg.profiled}/{reg.register_total} profiled
          {reg.blocked > 0 && ` · ${reg.blocked} refuse automated clients`}
        </span>
      )}
    </div>
  )
}

function Entry({ entry, expanded, onToggle }: {
  entry: CompetitorAnalysisEntry
  expanded: boolean
  onToggle: () => void
}) {
  const w = entry.written
  const overlap = entry.register_overlap ?? { vertical: false, use_case: false, technology: false }
  const matched = [
    overlap.technology && 'technology',
    overlap.vertical && 'vertical',
    overlap.use_case && 'use case',
  ].filter(Boolean) as string[]

  return (
    <div className="ca-entry" data-basis={entry.basis}>
      <div className="ca-entry-head">
        <div>
          <span className="ca-name">{entry.label}</span>
          <span className="tag">{entry.type_label}</span>
          {entry.relationship === 'both' && (
            <span className="tag partner" title="Orange partner in one motion and a competitor in another">
              also an Orange partner
            </span>
          )}
          <span className={`tag ${entry.basis === 'evidenced' ? 'evidenced' : ''}`}
                title={entry.basis === 'evidenced'
                  ? "This space's own sources name them, with a dated signal behind it"
                  : 'The register says they sell this into this vertical — true, and not proof they are in the deal'}>
            {entry.basis}
          </span>
        </div>
        {entry.website && (
          <a className="ca-site" href={entry.website} target="_blank" rel="noreferrer noopener">
            their site ↗
          </a>
        )}
      </div>

      {matched.length > 0 && (
        <p className="ca-muted">Register match on {matched.join(', ')}.</p>
      )}

      {entry.profile_status !== 'profiled' && (
        <p className="ca-unread">{STATUS_NOTE[entry.profile_status] ?? entry.profile_reason}</p>
      )}

      {entry.positioning && <p className="ca-positioning">{entry.positioning}</p>}

      {w?.activity?.text && (
        <div className="ca-block">
          <h5>What they are doing here</h5>
          <p>{w.activity.text}</p>
          {w.activity.pages.length > 0 && (
            <p className="ca-cite">from {w.activity.pages.length} of their own page(s)</p>
          )}
        </div>
      )}

      {w?.differentiation && (
        <div className="ca-block ca-diff">
          <h5>How Orange differentiates against {entry.label}</h5>
          <p>{w.differentiation}</p>
          {w.orange_assets.length > 0 && (
            <p className="ca-assets">
              Anchored on: {w.orange_assets.join(' · ')}
            </p>
          )}
        </div>
      )}

      {w?.concession && (
        <div className="ca-block ca-concession">
          <h5>What they do better</h5>
          <p>{w.concession}</p>
        </div>
      )}

      {entry.relevant_claims.length > 0 && (
        <details open={expanded} onToggle={onToggle}>
          <summary>
            {entry.relevant_claims.length} claim(s) from their own pages
            {entry.pages_used > 0 && ` · ${entry.pages_used} pages read`}
          </summary>
          <ul className="ca-claims">
            {entry.relevant_claims.map((claim, i) => (
              <li key={i}>{claim.claim}</li>
            ))}
          </ul>
          {entry.named_offers.length > 0 && (
            <p className="ca-muted">Their named offers: {entry.named_offers.join(', ')}</p>
          )}
        </details>
      )}

      {entry.mentions?.length > 0 && (
        <p className="ca-muted">
          Named in {entry.mentions.length} of this space's own sources.
        </p>
      )}
    </div>
  )
}

export default function CompetitorAnalysisPanel({ topicId, refreshKey, onHelp }: {
  topicId: string
  refreshKey?: number
  onHelp?: (topic: string) => void
}) {
  const [data, setData] = useState<CompetitorAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [writing, setWriting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const reload = useCallback(() => {
    let live = true
    api.competitorAnalysis(topicId)
      .then((d) => { if (live) { setData(d); setError(null) } })
      .catch((e) => { if (live) setError(String(e.message ?? e)) })
      .finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [topicId])

  useEffect(() => {
    setLoading(true)
    setError(null)
    return reload()
  }, [reload, refreshKey])

  /** Compute the intensity assessment this pane is built on, then reload. */
  const assess = useCallback(async () => {
    setWriting(true)
    setError(null)
    try {
      await api.recomputeCompetition(topicId)
      setData(await api.competitorAnalysis(topicId))
    } catch (e: any) {
      setError(String(e.message ?? e))
    } finally {
      setWriting(false)
    }
  }, [topicId])

  const generate = useCallback(async (force: boolean) => {
    setWriting(true)
    setError(null)
    try {
      setData(await api.generateCompetitorAnalysis(topicId, force))
    } catch (e: any) {
      setError(String(e.message ?? e))
    } finally {
      setWriting(false)
    }
  }, [topicId])

  if (loading) return <p className="ca-muted">Loading the competitive picture…</p>

  // A FAILED request must not render as a statement about the market.
  //
  // This branch used to fall through to "no competitor is matched to this
  // space", because `!data` is true whether the analysis is empty or the fetch
  // threw. The result was the most confident possible sentence about the
  // competitive field being printed when the truth was that the server never
  // answered — which is the exact failure this product exists to avoid,
  // reproduced in its own interface.
  if (error) {
    return (
      <div className="ca-empty">
        <p className="ca-error"><b>The competitor analysis could not be loaded.</b></p>
        <p className="ca-muted">{error}</p>
        <p className="ca-muted">
          This says nothing about whether competitors exist on this space — the request failed
          before that could be established.
        </p>
        <button className="fs-enter" onClick={() => { setLoading(true); setError(null); reload() }}>
          Try again
        </button>
      </div>
    )
  }

  if (!data || data.entries.length === 0) {
    // Two different causes, two different messages. Only the second is a claim
    // about the register.
    if (data && data.competition_assessed === false) {
      return (
        <div className="ca-empty">
          <p>Competitive intensity has not been computed for this space yet.</p>
          <p className="ca-muted">
            The competitor analysis is built on top of that assessment, so it has nothing to
            work from until it exists. This is a gap in processing, not a finding about the market.
          </p>
          <button className="fs-enter" disabled={writing} onClick={() => assess()}>
            {writing ? 'Assessing…' : 'Assess competitive intensity now'}
          </button>
        </div>
      )
    }
    return (
      <div className="ca-empty">
        <p>No competitor from the register is matched to this space.</p>
        <p className="ca-muted">
          That is reported as unverified rather than as an empty field: it may only mean the
          register has a gap in this vertical.
        </p>
      </div>
    )
  }

  return (
    <div className="ca-pane">
      <div className="ca-head">
        <div>
          <h4>
            Competitor analysis
            {onHelp && (
              <button className="help-btn" aria-label="About competitor analysis"
                      onClick={() => onHelp('competition')}>?</button>
            )}
          </h4>
          <CoverageBar analysis={data} />
        </div>
        <button className="fs-enter" disabled={writing}
                onClick={() => generate(data.has_narrative)}
                title={data.has_narrative
                  ? 'Rewrite the comparison against the current profiles and assets'
                  : 'Write the comparison — one model call'}>
          {writing ? 'Writing…' : data.has_narrative ? 'Rewrite comparison' : 'Write the comparison'}
        </button>
      </div>

      {error && <p className="ca-error">{error}</p>}

      {!data.has_narrative && !writing && (
        <p className="ca-notice">
          The structural join below is computed from stored data and is always current. The
          written comparison — what each competitor is doing here, and how Orange differentiates
          against each of them — costs one model call and has not been made yet.
        </p>
      )}

      {data.narrative?.field && (
        <div className="ca-field">
          <h5>The shape of the field</h5>
          <p>{data.narrative.field}</p>
        </div>
      )}

      {data.entries.map((entry) => (
        <Entry key={entry.id} entry={entry}
               expanded={expanded === entry.id}
               onToggle={() => setExpanded(expanded === entry.id ? null : entry.id)} />
      ))}

      {data.stripped?.length > 0 && (
        <details className="ca-stripped">
          <summary>{data.stripped.length} passage(s) removed by evidence binding</summary>
          <ul>
            {data.stripped.map((s, i) => (
              <li key={i}><strong>{s.competitor}</strong> — {s.reason}</li>
            ))}
          </ul>
        </details>
      )}

      <p className="ca-provenance">
        Join computed {data.computed_at?.slice(0, 10)} · register {data.register_version}
        {data.prompt_version && ` · prompt ${data.prompt_version}`}
        {data.model_version && ` · model ${data.model_version}`}
      </p>
    </div>
  )
}
