import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useAnnounce } from './Announcer'
import type { BriefMeta, Topic } from '../types'

/** The PDF brief, in the middle pane (FR-18).
 *
 * Shown inline rather than only offered as a download, because the brief is the
 * artefact a salesperson actually reads — and reading it beside the radar is
 * how they notice it is out of date. The same file is what the Download button
 * sends, so what gets forwarded is byte-identical to what was reviewed.
 */

export default function BriefView({ topic, onHelp, recent = [], onSelectTopic }: {
  topic: Topic | null
  onHelp?: (topic: string) => void
  /** Spaces whose brief already exists — otherwise this tab is a dead end. */
  recent?: { id: string; statement: string }[]
  onSelectTopic?: (id: string) => void
}) {
  const [meta, setMeta] = useState<BriefMeta | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  // A model call takes tens of seconds. A spinner alone reads as "hung" after
  // about ten of them, so the wait is counted out loud.
  const [elapsed, setElapsed] = useState(0)
  const announce = useAnnounce()

  useEffect(() => {
    if (!busy) { setElapsed(0); return }
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [busy])

  const topicId = topic?.id ?? null

  useEffect(() => {
    setMeta(null)
    setError(null)
    setLoaded(false)
    if (!topicId) return
    let cancelled = false
    api.brief(topicId)
      .then((m) => { if (!cancelled) { setMeta(m); setLoaded(true) } })
      .catch(() => { if (!cancelled) setLoaded(true) })
    return () => { cancelled = true }
  }, [topicId])

  const generate = useCallback((force: boolean) => {
    if (!topicId) return
    setBusy(true)
    setError(null)
    announce(force ? 'Rebuilding the brief. This takes up to a minute.'
                   : 'Building the brief. This takes up to a minute.')
    api.generateBrief(topicId, force)
      .then((result) => {
        setMeta(result)
        announce(`Brief ready for ${topicId}, ${Math.round((result.bytes ?? 0) / 1024)} kilobytes. `
                 + 'It is shown in the middle pane and can be downloaded.')
      })
      .catch((e) => {
        setError(String(e.message ?? e))
        announce(`Brief generation failed: ${String(e.message ?? e)}`)
      })
      .finally(() => setBusy(false))
  }, [topicId, announce])

  if (!topic) {
    return (
      <div className="panel">
        <div className="panel-head">
          <h2>Opportunity brief</h2>
          {onHelp && (
            <button className="help-btn" aria-label="What a brief is"
                    onClick={() => onHelp('brief')}><span aria-hidden>?</span></button>
          )}
          <span className="sub">A PDF you can take into a customer meeting</span>
        </div>
        <div className="brief-empty">
          <p style={{ maxWidth: 520, margin: '0 auto 14px' }}>
            A brief is a six-page PDF for one opportunity space: the sized market with its working,
            the solution drawn as a diagram, the named Orange assets, the competitive field, the
            questions to ask, and every source at the back.
          </p>
          {recent.length > 0 ? (
            <>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Briefs already built:</p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
                {recent.map((entry) => (
                  <button key={entry.id} onClick={() => onSelectTopic?.(entry.id)}
                          title={entry.statement}>
                    {entry.id} · {entry.statement.slice(0, 48)}…
                  </button>
                ))}
              </div>
            </>
          ) : (
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Select a space on the radar or in the list to build one.
            </p>
          )}
        </div>
      </div>
    )
  }

  const exists = Boolean(meta?.exists)

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Opportunity brief</h2>
        {onHelp && (
          <button className="help-btn" aria-label="About the brief" onClick={() => onHelp('brief')}>?</button>
        )}
        <span className="sub">
          {topic.id} · {topic.labels.vertical} × {topic.labels.use_case} × {topic.labels.technology}
        </span>
      </div>

      <div className="brief-toolbar">
        {exists ? (
          <>
            {/* A real link, not a button in a link: the browser's own download
                path is more reliable than a scripted one, and it keeps the
                right-click menu working. */}
            <a className="btn-link" href={api.briefDownloadUrl(topic.id)}>Download PDF</a>
            <button onClick={() => generate(true)} disabled={busy}>
              {busy ? <><span className="spinner" /> Rebuilding… {elapsed}s</> : 'Regenerate'}
            </button>
            <a href={api.briefUrl(topic.id, meta?.content_hash)} target="_blank" rel="noreferrer"
               style={{ fontSize: 11.5 }}>Open in a new tab</a>
            <span className="spacer" />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--text-muted)' }}>
              {Math.round((meta?.bytes ?? 0) / 1024)} kB · built {meta?.generated_at?.slice(0, 16).replace('T', ' ')} ·
              {' '}weights {meta?.weight_set} · sizing {meta?.sizing_version}
            </span>
          </>
        ) : (
          <>
            <button onClick={() => generate(false)} disabled={busy}>
              {busy ? <><span className="spinner" /> Building the brief… {elapsed}s</> : 'Generate the brief'}
            </button>
            <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
              Assembles the computed figures, the named assets and competitors, and a written
              narrative with its solution diagram. One model call, so it takes a few seconds.
            </span>
          </>
        )}
      </div>

      {meta?.stale && exists && (
        <div style={{ padding: '8px 14px' }}>
          <div className="stale-note" style={{ margin: 0 }}>
            <b>Out of date:</b> {meta.stale_reason ?? 'the topic has changed since this was built'}.
            {meta.topic_version !== topic.version
              && ` Built against v${meta.topic_version}, the topic is now v${topic.version}.`}
            {' '}Regenerate before sending it to anyone.
          </div>
        </div>
      )}

      {error && (
        <div style={{ padding: '8px 14px' }}>
          <div className="stale-note" style={{ margin: 0 }}>{error}</div>
        </div>
      )}

      {exists ? (
        <object className="brief-frame" data={api.briefUrl(topic.id, meta?.content_hash)}
                type="application/pdf" aria-label={`Opportunity brief for ${topic.id}`}>
          {/* Browsers without an inline PDF viewer get a link rather than a blank box. */}
          <div className="brief-empty">
            Your browser will not display the PDF inline.{' '}
            <a href={api.briefDownloadUrl(topic.id)}>Download it instead</a>.
          </div>
        </object>
      ) : (
        <div className="brief-empty">
          {busy ? `Building — sizing, competitors, narrative, diagram, then the PDF. `
                  + `${elapsed}s elapsed; a first build usually takes 20 to 60 seconds.`
                : loaded ? 'No brief has been generated for this space yet.'
                         : 'Checking…'}
        </div>
      )}
    </div>
  )
}
