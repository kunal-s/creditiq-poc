// Acquire: turn whatever the caller sent — a URL, a file, an e-mail — into documents with text.
// One e-mail becomes several documents (the body and each attachment); everything else is one.
// Text comes from the parsers in ../extract/text.ts (PDF text layer + OCR, DOCX, HTML, plain
// text); standalone images are OCR'd here.
import { simpleParser } from 'mailparser'
import { fetchSource, toText, type SourceText } from './text.js'
import { ocrImage } from './ocr.js'
import { cacheGet, cacheSet, sha256 } from './cache.js'

/** How the input arrived — a label the caller may set; the engine only uses it to decide how to read the bytes. */
export type Channel = 'url' | 'file' | 'email'
export interface RawInput {
  /** Where the bytes came from. */
  channel: Channel
  url?: string
  buf: Uint8Array
  contentType: string
  filename: string
}
export interface Document {
  /** 'body' for an e-mail's own text, otherwise the attachment / file / page. */
  part: 'body' | 'attachment' | 'document'
  name: string
  sha256: string
  contentType: string
  text: SourceText
  /** E-mail headers when the document came from a message. */
  mail?: { from: string; to: string; subject: string; date: string | null; messageId: string | null }
}

export type OnParse = (e: { type: 'stage'; stage: 'fetch' | 'parse' | 'ocr'; detail?: string; total?: number } | { type: 'progress'; stage: 'ocr'; done: number; total: number }) => void

const IMAGE = /^image\/(png|jpe?g|tiff?|bmp|webp)$/i
const isImage = (ct: string, name: string) => IMAGE.test(ct) || /\.(png|jpe?g|tiff?|bmp|webp)$/i.test(name)
/** An RFC 822 message: declared as such, named .eml, or opening with real mail headers (a transport header plus From/To/Subject). */
const isEml = (ct: string, name: string, buf: Uint8Array) => {
  if (/message\/rfc822/i.test(ct) || /\.eml$/i.test(name)) return true
  const head = new TextDecoder().decode(buf.slice(0, 4096))
  const transport = /^(Received|Return-Path|Delivered-To|MIME-Version|Message-ID|X-Mailer|DKIM-Signature):/im.test(head)
  const envelope = (head.match(/^(From|To|Subject|Date):\s/gim) ?? []).length
  return transport && envelope >= 2
}

/** Parse bytes to text, with the parse cached by content hash (OCR is the expensive part). */
export async function parseBytes(buf: Uint8Array, contentType: string, filename: string, on: OnParse, noCache = false): Promise<{ sha: string; text: SourceText }> {
  const sha = sha256(buf)
  const hit = noCache ? null : await cacheGet<SourceText>(`parse-${sha}`)
  if (hit) return { sha, text: hit }
  on({ type: 'stage', stage: 'parse', detail: filename || contentType })
  let text: SourceText
  if (isImage(contentType, filename)) {
    on({ type: 'stage', stage: 'ocr', total: 1 })
    const t = await ocrImage(buf)
    on({ type: 'progress', stage: 'ocr', done: 1, total: 1 })
    text = { text: t, pages: 1, kind: 'text', bytes: buf.length, ocrPages: 1 }
  } else {
    text = await toText(buf, contentType, filename, {
      onOcrStart: (total) => on({ type: 'stage', stage: 'ocr', total }),
      onOcrProgress: (done, total) => on({ type: 'progress', stage: 'ocr', done, total }),
    })
  }
  await cacheSet(`parse-${sha}`, text)
  return { sha, text }
}

export async function fromUrl(url: string, on: OnParse): Promise<RawInput> {
  on({ type: 'stage', stage: 'fetch', detail: url })
  const f = await fetchSource(url)
  return { channel: 'url', url, buf: f.buf, contentType: f.contentType, filename: decodeURIComponent(url.split('/').pop()?.split('?')[0] ?? '') }
}

/** An e-mail → its body as one document and each attachment as another (attachments first). */
export async function fromEmail(buf: Uint8Array, on: OnParse, scope: 'all' | 'attachments' | 'body' = 'all', noCache = false): Promise<Document[]> {
  const mail = await simpleParser(Buffer.from(buf))
  const hdr = { from: mail.from?.text ?? '', to: Array.isArray(mail.to) ? mail.to.map((t) => t.text).join(', ') : mail.to?.text ?? '', subject: mail.subject ?? '', date: mail.date ? mail.date.toISOString() : null, messageId: mail.messageId ?? null }
  const out: Document[] = []
  if (scope !== 'body') {
    for (const a of mail.attachments ?? []) {
      const bytes = new Uint8Array(a.content)
      const { sha, text } = await parseBytes(bytes, a.contentType, a.filename ?? 'attachment', on, noCache)
      out.push({ part: 'attachment', name: a.filename ?? 'attachment', sha256: sha, contentType: a.contentType, text, mail: hdr })
    }
  }
  if (scope !== 'attachments') {
    const body = (mail.text ?? '').trim() || (mail.html ? (await toText(new TextEncoder().encode(String(mail.html)), 'text/html', 'body.html')).text : '')
    const headed = `From: ${hdr.from}\nTo: ${hdr.to}\nSubject: ${hdr.subject}\nDate: ${hdr.date ?? ''}\n\n${body}`
    out.push({ part: 'body', name: hdr.subject || 'message', sha256: sha256(buf), contentType: 'message/rfc822', text: { text: headed, pages: 1, kind: 'text', bytes: buf.length }, mail: hdr })
  }
  return out
}

/** Everything → documents. */
export async function acquire(raw: RawInput, on: OnParse, opts: { emailScope?: 'all' | 'attachments' | 'body'; noCache?: boolean } = {}): Promise<Document[]> {
  if (raw.channel === 'email' || isEml(raw.contentType, raw.filename, raw.buf)) return fromEmail(raw.buf, on, opts.emailScope ?? 'all', opts.noCache)
  const { sha, text } = await parseBytes(raw.buf, raw.contentType, raw.filename, on, opts.noCache)
  return [{ part: 'document', name: raw.filename || raw.url || 'document', sha256: sha, contentType: raw.contentType, text }]
}
