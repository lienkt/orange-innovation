import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

/** One polite live region for the whole app.
 *
 * Generating a brief takes twenty to sixty seconds and then quietly swaps the
 * middle pane. A sighted user sees the PDF appear; a screen-reader user gets
 * nothing at all, and a spinner that stops is not an announcement. Everything
 * that finishes on its own schedule — generation, regeneration, a filter that
 * changed the result count — says so here.
 *
 * `polite` rather than `assertive` throughout: none of this is urgent enough to
 * interrupt someone mid-sentence, and an assertive region that fires on every
 * filter keystroke is worse than silence.
 */
const AnnouncerContext = createContext<(message: string) => void>(() => {})

export function useAnnounce() {
  return useContext(AnnouncerContext)
}

export function Announcer({ children }: { children: React.ReactNode }) {
  const [message, setMessage] = useState('')
  const timer = useRef<number | undefined>(undefined)

  const announce = useCallback((text: string) => {
    // Clearing first makes a repeated message re-announce: setting the same
    // string twice is a no-op to the accessibility tree, so "brief ready" would
    // be silent the second time.
    window.clearTimeout(timer.current)
    setMessage('')
    timer.current = window.setTimeout(() => setMessage(text), 60)
  }, [])

  const value = useMemo(() => announce, [announce])
  return (
    <AnnouncerContext.Provider value={value}>
      {children}
      <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
        {message}
      </div>
    </AnnouncerContext.Provider>
  )
}
