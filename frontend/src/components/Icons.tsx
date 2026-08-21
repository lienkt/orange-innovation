/** One line-icon set, drawn rather than imported.
 *
 * Why SVG and not emoji: an emoji is a full-colour picture the theme cannot
 * touch, it renders differently on every platform, and several of the obvious
 * candidates carry meanings this interface has already spent its colour budget
 * on — a red 🔥 beside "Why it is hot now" competes with the reserved status
 * scale, where red means an evidence gap or a crowded field and nothing else.
 * These take `currentColor`, so they inherit the muted heading colour in both
 * themes and stay decorative.
 *
 * Why not an icon library: fifteen icons at ~120 bytes each is smaller than the
 * import, and drawing them here keeps the metrics identical — one viewBox, one
 * stroke width, so a row of headings does not wobble.
 *
 * Every icon is `aria-hidden`. The label beside it is the accessible name, and
 * an icon that repeated it would make a screen reader say everything twice.
 * These decorate a heading that already says what the section is; they never
 * carry meaning on their own.
 */

type IconProps = { className?: string }

function svg(path: React.ReactNode) {
  return function Icon({ className = 'sec-icon' }: IconProps) {
    return (
      <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false"
           fill="none" stroke="currentColor" strokeWidth={1.7}
           strokeLinecap="round" strokeLinejoin="round">
        {path}
      </svg>
    )
  }
}

/* --- filter rail ------------------------------------------------------- */

export const IconSearch = svg(<><circle cx="11" cy="11" r="6" /><path d="m20 20-4.5-4.5" /></>)

/** Horizon — Now / Next / Later is time, and a clock says that without a metaphor. */
export const IconClock = svg(<><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5.2l3.2 2" /></>)

/** Competition — overlap, not a crowd of people: §4.3.3 is about how many
 *  players cover the same ground, which is what two intersecting sets show. */
export const IconVenn = svg(<><circle cx="9" cy="12" r="5.5" /><circle cx="15" cy="12" r="5.5" /></>)

/** Ready to sell — the brief is a document, and that is the whole point of it. */
export const IconDoc = svg(<>
  <path d="M14 3H7a1.6 1.6 0 0 0-1.6 1.6v14.8A1.6 1.6 0 0 0 7 21h10a1.6 1.6 0 0 0 1.6-1.6V7.6z" />
  <path d="M14 3v4.6h4.6M8.6 12.5h6.8M8.6 16.3h4.6" />
</>)

/** Vertical — a sector, drawn as the industry that defines it. */
export const IconBuilding = svg(<>
  <path d="M4 21h16M6 21V6.5l6-3 6 3V21" />
  <path d="M10 11.5h.01M14 11.5h.01M10 15.5h.01M14 15.5h.01" />
</>)

/** Domain — the layer of the portfolio a use case sits in. */
export const IconLayers = svg(<>
  <path d="m12 3 8.5 4.4L12 11.8 3.5 7.4z" /><path d="m3.5 12 8.5 4.4 8.5-4.4" />
  <path d="m3.5 16.6 8.5 4.4 8.5-4.4" />
</>)

/** Persona — the buyer, singular, because that is how the taxonomy names them. */
export const IconPerson = svg(<>
  <circle cx="12" cy="8" r="3.6" /><path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
</>)

export const IconGlobe = svg(<>
  <circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17" />
  <path d="M12 3.5c2.2 2.4 3.4 5.4 3.4 8.5S14.2 18.6 12 21c-2.2-2.4-3.4-5.4-3.4-8.5S9.8 5.9 12 3.5z" />
</>)

/* --- detail sections ---------------------------------------------------- */

/** Why it is hot now. A flame in one stroke weight, not a red emoji. */
export const IconFlame = svg(<>
  <path d="M12 3c.6 3.2-1.4 4.4-2.8 6.2A6.6 6.6 0 0 0 7.7 13a4.3 4.3 0 0 0 8.6 0c0-2.2-1-3.4-2.2-5" />
  <path d="M12 20.5a2.6 2.6 0 0 0 2.6-2.6c0-1.6-2.6-3.4-2.6-3.4s-2.6 1.8-2.6 3.4A2.6 2.6 0 0 0 12 20.5z" />
</>)

/** Market opportunity — a figure with a currency, since §4.3.4 is money. */
export const IconMoney = svg(<>
  <rect x="2.8" y="6" width="18.4" height="12" rx="2" /><circle cx="12" cy="12" r="2.6" />
  <path d="M6 12h.01M18 12h.01" />
</>)

/** Ask & answer — the qualifying questions and the objections. */
export const IconChat = svg(<>
  <path d="M20.5 12.6c0 3.9-3.8 7-8.5 7a9.8 9.8 0 0 1-2.6-.35L4 21l1.3-3.6a6.6 6.6 0 0 1-1.8-4.4c0-3.9 3.8-7 8.5-7s8.5 3.1 8.5 6.6z" />
  <path d="M12 14.4v-.5c0-1 1.7-1.3 1.7-2.7a1.7 1.7 0 0 0-3.4 0M12 16.6h.01" />
</>)

/** Where it delivers value, and for whom — buyers, plural. */
export const IconPeople = svg(<>
  <circle cx="9.5" cy="8.5" r="3.2" /><path d="M3.5 19.5a6 6 0 0 1 12 0" />
  <path d="M16 5.6a3.2 3.2 0 0 1 0 5.8M17 14a6 6 0 0 1 3.5 5.5" />
</>)

/** Can we play, can we win — named Orange assets, drawn as a component. */
export const IconCube = svg(<>
  <path d="m12 2.8 8 4.3v9.8l-8 4.3-8-4.3V7.1z" /><path d="m4 7.1 8 4.3 8-4.3M12 11.4V21" />
</>)

/** Score breakdown — a measured quantity with a needle, not a trend. */
export const IconGauge = svg(<>
  <path d="M4 17.5a8.5 8.5 0 1 1 16 0" /><path d="m12 17.5 4-5" /><circle cx="12" cy="17.5" r="1.1" />
</>)

/** Next action, by role. */
export const IconTarget = svg(<>
  <circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="0.6" />
</>)

/** Workflow — the stage board, as its columns. */
export const IconBoard = svg(<>
  <rect x="3.2" y="4.5" width="17.6" height="15" rx="1.8" />
  <path d="M9 4.5v15M15 4.5v15" />
</>)

/** Team conviction — several voices, scored. */
export const IconVoices = svg(<>
  <path d="M12 3.6l2.5 5.1 5.6.8-4 4 .9 5.6-5-2.6-5 2.6.9-5.6-4-4 5.6-.8z" />
</>)

/** Evidence over time — momentum is a trend, so it is a line. */
export const IconTrend = svg(<>
  <path d="M3.5 19.5h17" /><path d="m5.5 16 4.2-4.6 3.4 2.8L20 7" /><path d="M16.4 7H20v3.6" />
</>)

/** Is this useful? */
export const IconThumb = svg(<>
  <path d="M7.5 10.5 11 3.5a2.2 2.2 0 0 1 2.2 2.2v3.3h4.6a2 2 0 0 1 2 2.4l-1.4 6.5a2 2 0 0 1-2 1.6H7.5z" />
  <path d="M7.5 10.5v9H5a1.5 1.5 0 0 1-1.5-1.5V12A1.5 1.5 0 0 1 5 10.5z" />
</>)

/** Sources — the cited evidence, each one a link to a dated document. */
export const IconLink = svg(<>
  <path d="M10 13.6a3.6 3.6 0 0 0 5.2.3l2.8-2.8a3.7 3.7 0 0 0-5.2-5.2l-1.6 1.6" />
  <path d="M14 10.4a3.6 3.6 0 0 0-5.2-.3L6 12.9a3.7 3.7 0 0 0 5.2 5.2l1.6-1.6" />
</>)

/** Section id -> icon, so the jump bar and the heading it lands on carry the
 *  same mark. A jump bar whose entries look nothing like their destinations is
 *  a second vocabulary to learn. */
export const SECTION_ICONS: Record<string, (props: IconProps) => JSX.Element> = {
  'why-hot': IconFlame,
  market: IconMoney,
  competition: IconVenn,
  questions: IconChat,
  description: IconDoc,
  value: IconPeople,
  assets: IconCube,
  score: IconGauge,
  horizon: IconClock,
  action: IconTarget,
  workflow: IconBoard,
  conviction: IconVoices,
  timeline: IconTrend,
  feedback: IconThumb,
  sources: IconLink,
}
