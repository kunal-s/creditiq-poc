// One page layout, rendered two ways: a digital PDF (pdf-lib, text layer)
// and a page image (@napi-rs/canvas) that can be degraded like a scan or a
// phone photograph. Coordinates are points on an A4 page, top-left origin,
// y at the text baseline.
import { existsSync } from 'node:fs'
import { GlobalFonts, createCanvas, type Canvas } from '@napi-rs/canvas'
import { PDFDocument, PDFHexString, PDFName, StandardFonts, rgb } from 'pdf-lib'

export const A4 = { w: 595.28, h: 841.89 }

export interface Run { x: number; y: number; text: string; size: number; bold: boolean; right: boolean }
export interface Rule { x1: number; y1: number; x2: number; y2: number }
export interface PageSpec { runs: Run[]; rules: Rule[] }

export class Page implements PageSpec {
  runs: Run[] = []
  rules: Rule[] = []
  text(x: number, y: number, text: string, o: { size?: number; bold?: boolean; right?: boolean } = {}): this {
    this.runs.push({ x, y, text, size: o.size ?? 10, bold: o.bold ?? false, right: o.right ?? false })
    return this
  }
  rule(x1: number, y1: number, x2: number, y2 = y1): this { this.rules.push({ x1, y1, x2, y2 }); return this }
}

const FIXED_DATE = new Date('2025-01-01T00:00:00Z')

export async function toPdf(pages: PageSpec[]): Promise<Uint8Array> {
  const doc = await PDFDocument.create()
  doc.setCreationDate(FIXED_DATE)
  doc.setModificationDate(FIXED_DATE)
  doc.setProducer('fixture')
  doc.setCreator('fixture')
  const regular = await doc.embedFont(StandardFonts.Helvetica)
  const bold = await doc.embedFont(StandardFonts.HelveticaBold)
  for (const p of pages) {
    const page = doc.addPage([A4.w, A4.h])
    for (const r of p.runs) {
      const font = r.bold ? bold : regular
      const width = font.widthOfTextAtSize(r.text, r.size)
      page.drawText(r.text, { x: r.right ? r.x - width : r.x, y: A4.h - r.y, size: r.size, font, color: rgb(0, 0, 0) })
    }
    for (const l of p.rules) page.drawLine({ start: { x: l.x1, y: A4.h - l.y1 }, end: { x: l.x2, y: A4.h - l.y2 }, thickness: 0.6, color: rgb(0.2, 0.2, 0.2) })
  }
  return doc.save({ useObjectStreams: false })
}

let fontsReady = false
function fonts(): string {
  if (!fontsReady) {
    const dir = '/usr/share/fonts/truetype/liberation'
    if (existsSync(`${dir}/LiberationSans-Regular.ttf`)) {
      GlobalFonts.registerFromPath(`${dir}/LiberationSans-Regular.ttf`, 'FxSans')
      GlobalFonts.registerFromPath(`${dir}/LiberationSans-Bold.ttf`, 'FxSans')
    }
    fontsReady = true
  }
  return GlobalFonts.has('FxSans') ? 'FxSans' : 'sans-serif'
}

/** Render a page to a canvas at `dpi`. */
export function toCanvas(p: PageSpec, dpi: number): Canvas {
  const s = dpi / 72
  const c = createCanvas(Math.round(A4.w * s), Math.round(A4.h * s))
  const ctx = c.getContext('2d')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, c.width, c.height)
  ctx.fillStyle = '#111111'
  ctx.textBaseline = 'alphabetic'
  const family = fonts()
  for (const r of p.runs) {
    ctx.font = `${r.bold ? 'bold ' : ''}${(r.size * s).toFixed(2)}px ${family}`
    const w = ctx.measureText(r.text).width
    ctx.fillText(r.text, r.right ? r.x * s - w : r.x * s, r.y * s)
  }
  ctx.strokeStyle = '#333333'
  ctx.lineWidth = Math.max(1, 0.6 * s)
  for (const l of p.rules) { ctx.beginPath(); ctx.moveTo(l.x1 * s, l.y1 * s); ctx.lineTo(l.x2 * s, l.y2 * s); ctx.stroke() }
  return c
}

/** A small deterministic generator for noise. */
function prng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export interface Degrade { blur?: number; skewDeg?: number; shadow?: number; noise?: number; seed?: number }

/** Scanner and camera effects: box blur (down-then-up scaling), rotation, a side shadow, speckle. */
export function degrade(src: Canvas, d: Degrade): Canvas {
  let c = src
  if (d.blur && d.blur > 1) {
    const small = createCanvas(Math.max(1, Math.round(c.width / d.blur)), Math.max(1, Math.round(c.height / d.blur)))
    const sctx = small.getContext('2d')
    sctx.imageSmoothingEnabled = true
    sctx.drawImage(c, 0, 0, small.width, small.height)
    const back = createCanvas(c.width, c.height)
    const bctx = back.getContext('2d')
    bctx.imageSmoothingEnabled = true
    bctx.drawImage(small, 0, 0, back.width, back.height)
    c = back
  }
  if (d.skewDeg) {
    const out = createCanvas(c.width, c.height)
    const ctx = out.getContext('2d')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, out.width, out.height)
    ctx.translate(out.width / 2, out.height / 2)
    ctx.rotate((d.skewDeg * Math.PI) / 180)
    ctx.drawImage(c, -c.width / 2, -c.height / 2)
    c = out
  }
  if (d.shadow) {
    const out = createCanvas(c.width, c.height)
    const ctx = out.getContext('2d')
    ctx.drawImage(c, 0, 0)
    const g = ctx.createLinearGradient(0, 0, out.width * 0.7, out.height * 0.3)
    g.addColorStop(0, `rgba(0,0,0,${d.shadow})`)
    g.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, out.width, out.height)
    c = out
  }
  if (d.noise) {
    const ctx = c.getContext('2d')
    const img = ctx.getImageData(0, 0, c.width, c.height)
    const rnd = prng(d.seed ?? 7)
    for (let i = 0; i < img.data.length; i += 4) {
      const n = (rnd() - 0.5) * 2 * d.noise
      for (let k = 0; k < 3; k++) img.data[i + k] = Math.max(0, Math.min(255, img.data[i + k] + n))
    }
    ctx.putImageData(img, 0, 0)
  }
  return c
}

export async function jpeg(c: Canvas, quality = 85): Promise<Uint8Array> { return new Uint8Array(await c.encode('jpeg', quality)) }
export async function png(c: Canvas): Promise<Uint8Array> { return new Uint8Array(await c.encode('png')) }

/** A scanned PDF: one JPEG page image per page, no text layer. */
export async function scannedPdf(images: Uint8Array[]): Promise<Uint8Array> {
  const doc = await PDFDocument.create()
  doc.setCreationDate(FIXED_DATE)
  doc.setModificationDate(FIXED_DATE)
  doc.setProducer('fixture')
  doc.setCreator('fixture')
  for (const bytes of images) {
    const img = await doc.embedJpg(bytes)
    const page = doc.addPage([A4.w, A4.h])
    page.drawImage(img, { x: 0, y: 0, width: A4.w, height: A4.h })
  }
  return doc.save({ useObjectStreams: false })
}

/** A PDF that asks for a password the reader does not have (standard security handler). */
export async function encryptedPdf(pages: PageSpec[]): Promise<Uint8Array> {
  const doc = await PDFDocument.load(await toPdf(pages))
  const ctx = doc.context
  const enc = ctx.obj({ Filter: 'Standard', V: 1, R: 2, P: -44 })
  enc.set(PDFName.of('O'), PDFHexString.of('4f'.repeat(32)))
  enc.set(PDFName.of('U'), PDFHexString.of('55'.repeat(32)))
  ctx.trailerInfo.Encrypt = ctx.register(enc)
  ctx.trailerInfo.ID = ctx.obj([PDFHexString.of('ab'.repeat(16)), PDFHexString.of('ab'.repeat(16))])
  return doc.save({ useObjectStreams: false })
}

export const inr = (n: number, decimals = 2): string => {
  const neg = n < 0
  const [int, dec] = Math.abs(n).toFixed(decimals).split('.')
  const last3 = int.slice(-3)
  const rest = int.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',')
  const s = rest ? `${rest},${last3}` : last3
  return `${neg ? '-' : ''}${s}${decimals ? `.${dec}` : ''}`
}
