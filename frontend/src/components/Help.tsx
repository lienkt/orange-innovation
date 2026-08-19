import { useEffect, useRef } from 'react'
import { HELP } from '../help'

/** A "?" affordance that opens an explanation.
 *
 * The dialog is a real dialog: Escape closes it, the backdrop closes it, focus
 * moves into it on open and returns to the trigger on close, and it is labelled
 * for screen readers. A help system that traps keyboard users is worse than no
 * help system.
 */

export function HelpButton({ topic, onOpen, label }: {
  topic: string
  onOpen: (topic: string) => void
  label?: string
}) {
  const entry = HELP[topic]
  return (
    <button
      type="button"
      className="help-btn"
      aria-label={`Help: ${entry?.title ?? topic}`}
      title={entry?.title ?? 'Help'}
      onClick={(e) => { e.stopPropagation(); onOpen(topic) }}
    >
      {/* The glyph is hidden from the accessibility tree: these buttons sit
          INSIDE headings, and a heading's accessible name is the concatenation
          of its contents — "Market opportunity ?" announced as one heading, with
          the button's own label glued on after it. */}
      <span aria-hidden="true">{label ?? '?'}</span>
    </button>
  )
}

/** Renders **bold** and `code` without pulling in a markdown dependency for
 *  what is a handful of inline spans. */
function inline(text: string, key: number) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return (
    <p key={key}>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i}>{part.slice(2, -2)}</strong>
        }
        if (part.startsWith('`') && part.endsWith('`')) {
          return <code key={i}>{part.slice(1, -1)}</code>
        }
        return <span key={i}>{part}</span>
      })}
    </p>
  )
}

/** Keep Tab inside a dialog while it is open.
 *
 * `aria-modal` tells a screen reader the rest of the page is inert; it does not
 * stop Tab. Without a trap the second Tab lands on whatever is behind the
 * backdrop, where the reader can neither see what has focus nor close the thing
 * they are inside. Exported because both dialogs need identical behaviour.
 */
export function useFocusTrap(open: boolean, ref: React.RefObject<HTMLElement>, onClose: () => void) {
  const restoreTo = useRef<Element | null>(null)
  useEffect(() => {
    if (!open) return
    restoreTo.current = document.activeElement
    ref.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { onClose(); return }
      if (event.key !== 'Tab' || !ref.current) return
      const focusable = ref.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (focusable.length === 0) { event.preventDefault(); return }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement
      if (event.shiftKey && (active === first || active === ref.current)) {
        event.preventDefault(); last.focus()
      } else if (!event.shiftKey && active === last) {
        event.preventDefault(); first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      ;(restoreTo.current as HTMLElement | null)?.focus?.()
    }
  }, [open, ref, onClose])
}

export function HelpModal({ topic, onClose }: { topic: string | null; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusTrap(Boolean(topic), ref, onClose)

  if (!topic) return null
  const entry = HELP[topic]
  if (!entry) return null

  return (
    <div className="help-backdrop" onClick={onClose} role="presentation">
      <div
        className="help-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-title"
        tabIndex={-1}
        ref={ref}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="help-head">
          <h3 id="help-title">{entry.title}</h3>
          <button type="button" onClick={onClose} aria-label="Close help">✕</button>
        </div>
        <div className="help-body">
          {entry.body.map((paragraph, i) => inline(paragraph, i))}
        </div>
        {entry.ref && (
          <div className="help-ref">
            Requirements reference: <code>{entry.ref}</code>
          </div>
        )}
      </div>
    </div>
  )
}
