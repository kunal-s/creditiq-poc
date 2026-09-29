// Spreadsheets (F-07.1, F-11.1): read cell by cell. Each worksheet is one
// page; each row is one line; each cell is placed in its own column band so
// the word index keeps the grid (x from the column, y from the row).
import ExcelJS from 'exceljs'
import { lineOf } from './layout.js'
import { COLUMN_GAP, type FileRead, type Line, type PageRead, type Word } from './types.js'

function cellText(v: ExcelJS.CellValue): string {
  if (v === null || v === undefined) return ''
  if (v instanceof Date) {
    const d = v.toISOString().slice(0, 10).split('-')
    return `${d[2]}/${d[1]}/${d[0]}`
  }
  if (typeof v === 'object') {
    const o = v as { richText?: { text: string }[]; text?: string; result?: unknown; formula?: string; error?: string }
    if (o.richText) return o.richText.map((r) => r.text).join('')
    if (o.text !== undefined) return String(o.text)
    if (o.result !== undefined) return cellText(o.result as ExcelJS.CellValue)
    if (o.error) return ''
    return ''
  }
  return String(v)
}

/** A grid of cell strings to a page: rows are lines, columns are bands. */
export function gridToPage(n: number, grid: string[][]): PageRead {
  const rows = grid.length
  const cols = Math.max(1, ...grid.map((r) => r.length))
  const lines: Line[] = []
  const words: Word[] = []
  grid.forEach((row, r) => {
    const lineWords: Word[] = []
    row.forEach((cell, c) => {
      const s = cell.replace(/\s+/g, ' ').trim()
      if (!s) return
      const parts = s.split(' ')
      const total = s.length
      let pos = 0
      for (const p of parts) {
        const x0 = (c + (0.9 * pos) / total) / cols
        const x1 = (c + (0.9 * (pos + p.length)) / total) / cols
        lineWords.push({ text: p, x0, y0: r / rows + 0.1 / rows, x1, y1: (r + 0.9) / rows })
        pos += p.length + 1
      }
    })
    if (!lineWords.length) return
    // Cells are separate columns: rebuild the line text with an explicit gap between cells.
    const line = lineOf(lineWords)
    let text = ''
    const offsets: number[] = []
    let prevCol = -1
    for (const w of line.words) {
      const col = Math.floor(w.x0 * cols + 1e-9)
      if (offsets.length) text += col !== prevCol ? COLUMN_GAP : ' '
      offsets.push(text.length)
      text += w.text
      prevCol = col
    }
    lines.push({ ...line, text, offsets })
    words.push(...lineWords)
  })
  return { n, route: 'sheet', words, lines, text: lines.map((l) => l.text).join('\n'), ocrConfidence: null, metrics: {} }
}

export async function readXlsx(buf: Uint8Array): Promise<FileRead> {
  const wb = new ExcelJS.Workbook()
  try {
    await wb.xlsx.load(Buffer.from(buf) as unknown as ArrayBuffer)
  } catch (e) {
    return { kind: 'sheet', pages: [], error: { code: 'corrupt', detail: `The workbook cannot be opened (${e instanceof Error ? e.message.slice(0, 120) : 'unknown error'}).` } }
  }
  const pages: PageRead[] = []
  let n = 0
  wb.eachSheet((ws) => {
    const grid: string[][] = []
    ws.eachRow({ includeEmpty: true }, (row, r) => {
      const cells: string[] = []
      row.eachCell({ includeEmpty: true }, (cell, c) => { cells[c - 1] = cellText(cell.value) })
      grid[r - 1] = Array.from(cells, (x) => x ?? '')
    })
    for (let i = 0; i < grid.length; i++) grid[i] ??= []
    n += 1
    pages.push(gridToPage(n, grid))
  })
  return { kind: 'sheet', pages }
}

export function readCsv(buf: Uint8Array): FileRead {
  const text = new TextDecoder('utf-8').decode(buf)
  const grid: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++ } else if (ch === '"') quoted = false
      else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === ',') { row.push(cell); cell = '' } else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++
      row.push(cell); grid.push(row); row = []; cell = ''
    } else cell += ch
  }
  if (cell || row.length) { row.push(cell); grid.push(row) }
  return { kind: 'sheet', pages: [gridToPage(1, grid)] }
}
