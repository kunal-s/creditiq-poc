// Structure recovery, the cheap way: split a long document into numbered
// units with regexes tuned to legal and standards drafting conventions, so the model
// can be asked to triage a compact index instead of reading everything.
//
//   Acts / Rules / Regulations:  "4.", "4A.", "12B." at line start, then a heading
//   Circulars / Master Directions: "4.2", "7.3.1" dotted paragraph numbers
//   Explicit labels: "Section 4", "Rule 3", "Regulation 12", "Para 7", "Clause 5.1"

export interface Section {
  id: string // 'Section 4A' | 'Para 7.3' | 'Rule 3' | 'Entry 18' | 'Section 3 (Amdt. 2)'
  heading: string // first line after the number, trimmed
  text: string // the provision text including its number line
  pages: string // 'p. 5' | 'pp. 5–6'
  /** Where the provision sits in a compiled document: the principal instrument, a schedule, or a later amending instrument. */
  part: 'principal' | 'schedule' | 'amendment'
}

// A compiled document is: principal Act → its schedules → amendment Acts (each restarting
// at "1. Short title"), each possibly with schedules. Section numbers repeat across
// these parts, so the splitter tracks which part it is in and labels accordingly.
const SCHEDULE_START = /^\s*(?:THE\s+)?(?:FIRST\s+|SECOND\s+|THIRD\s+)?SCHEDULE\b/i
const SHORT_TITLE = /^\s*(?:[A-Za-z][A-Za-z,'’-]*\s+){0,3}1\.\s*\(?[1I]?\)?\s*(?:This|These)\s+(?:Act|Rules|Regulations)\s+may\s+be\s+called/i

const LABELLED = /^\s*(Section|Sec\.|Rule|Regulation|Reg\.|Para(?:graph)?|Clause|Article)\s+(\d{1,3}[A-Z]{0,2}(?:\.\d{1,2})*)\b/i
// "4A. Employer's liability …" — OCR'd Acts often carry a marginal note before the number
// ("Payment 8. (1) The tax …"), so up to three leading words are tolerated.
const ACT_STYLE = /^\s*(?:[A-Za-z][A-Za-z,'’-]*\s+){0,3}(\d{1,3}[A-Z]{0,2})\.\s+(?=[A-Z(\[])/
const DOTTED = /^\s*(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+(?=\S)/ // "7.3 …" / "7.3.1 …"

function detectStart(line: string, mode: 'act' | 'dotted' | 'labelled'): string | null {
  if (mode === 'labelled') {
    const m = line.match(LABELLED)
    return m ? `${normLabel(m[1])} ${m[2]}` : null
  }
  if (mode === 'act') {
    const m = line.match(ACT_STYLE)
    return m ? `Section ${m[1]}` : null
  }
  const m = line.match(DOTTED)
  return m ? `Para ${m[1]}` : null
}

function normLabel(l: string): string {
  const s = l.toLowerCase()
  if (s.startsWith('sec')) return 'Section'
  if (s.startsWith('reg')) return 'Regulation'
  if (s.startsWith('para')) return 'Para'
  return l[0].toUpperCase() + l.slice(1).toLowerCase()
}

function pagesOf(text: string, fallback: string): string {
  const marks = [...text.matchAll(/\[\[page (\d+)\]\]/g)].map((m) => Number(m[1]))
  if (!marks.length) return fallback
  const a = Math.min(...marks)
  const b = Math.max(...marks)
  return a === b ? `p. ${a}` : `pp. ${a}–${b}`
}

/** Split into provisions. Returns [] when no convention yields a usable split. */
export function splitSections(text: string): Section[] {
  const lines = text.split('\n')
  let best: Section[] = []
  for (const mode of ['act', 'labelled', 'dotted'] as const) {
    const out: Section[] = []
    let cur: { id: string; lines: string[]; startPage: string; part: Section['part'] } | null = null
    let lastPage = 'p. 1'
    let part: Section['part'] = 'principal'
    let actNo = 1 // 1 = principal; 2.. = amendment Acts in order of appearance
    let seenShortTitle = false
    for (const line of lines) {
      const pm = line.match(/\[\[page (\d+)\]\]/)
      if (pm) lastPage = `p. ${pm[1]}`
      if (mode === 'act') {
        if (SHORT_TITLE.test(line)) {
          if (seenShortTitle) {
            actNo += 1
            part = 'amendment'
          } else {
            seenShortTitle = true
            part = 'principal'
          }
        } else if (SCHEDULE_START.test(line)) {
          part = 'schedule'
        }
      }
      let id = detectStart(line, mode)
      if (id && mode === 'act') {
        const n = id.replace(/^Section /, '')
        id = part === 'schedule' ? `Entry ${n}` : part === 'amendment' ? `Section ${n} (Amdt. ${actNo - 1})` : `Section ${n}`
      }
      if (id) {
        if (cur) out.push(finish(cur))
        cur = { id, lines: [line], startPage: lastPage, part }
      } else if (cur) {
        cur.lines.push(line)
      }
    }
    if (cur) out.push(finish(cur))
    // Prefer the convention that produced the most sections with real bodies.
    const usable = out.filter((s) => s.text.length > 80)
    if (usable.length > best.length) best = usable
  }
  return best

  function finish(c: { id: string; lines: string[]; startPage: string; part: Section['part'] }): Section {
    const body = c.lines.join('\n').trim()
    const first = c.lines[0].replace(LABELLED, '').replace(ACT_STYLE, '').replace(DOTTED, '').trim()
    const heading = (first || c.lines.find((l) => l.trim() && !/\[\[page/.test(l))?.trim() || '').slice(0, 120)
    return { id: c.id, heading, text: body, pages: pagesOf(body, c.startPage), part: c.part }
  }
}

/** A compact index for the triage call: one line per section. */
export function sectionIndex(sections: Section[], snippet = 160): string {
  return sections
    .map((s, i) => {
      const gist = s.text.replace(/\[\[page \d+\]\]/g, ' ').replace(/\s+/g, ' ').slice(0, snippet)
      return `#${i} ${s.id} (${s.pages}) — ${gist}`
    })
    .join('\n')
}
