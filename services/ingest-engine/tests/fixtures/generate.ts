// Writes the test fixtures: tests/fixtures/TC-xx/<files> + expected.json.
//   npm run fixtures
// Deterministic: the same inputs give the same bytes (fixed PDF dates, seeded noise).
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import ExcelJS from 'exceljs'
import { A4, degrade, encryptedPdf, jpeg, png, scannedPdf, toCanvas, toPdf, Page, type Degrade } from './lib/layout.js'
import * as D from './lib/docs.js'
import type { Doc, Expect } from './lib/docs.js'

const ROOT = new URL('.', import.meta.url).pathname

interface FileSpec { file: string; original_name: string; label_hint?: string | null; content_type: string }
interface DocExpect {
  file: string
  page_from: number
  page_to: number
  types?: string[]
  instance_key?: string | null
  fields?: Expect[]
  scanned?: boolean
  grades?: string[]
  reasons_any?: string[]
  candidates_min?: number
  split_uncertain?: boolean
}
interface RequestSpec { name: string; files: FileSpec[]; documents: DocExpect[]; same_doc_key?: string[][]; duplicate_pair?: string[]; file_status?: Record<string, string> }
interface TcSpec { tc: string; title: string; requests: RequestSpec[] }

const PDF = 'application/pdf'
const JPG = 'image/jpeg'
const PNG = 'image/png'
const XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const SCAN: Degrade = { blur: 1.3, skewDeg: 0.4, noise: 12, seed: 11 }

async function scanPdf(doc: Doc, d: Degrade = SCAN, dpi = 200): Promise<Uint8Array> {
  const imgs: Uint8Array[] = []
  for (const [i, p] of doc.pages.entries()) imgs.push(await jpeg(degrade(toCanvas(p, dpi), { ...d, seed: (d.seed ?? 1) + i }), 80))
  return scannedPdf(imgs)
}

/** Shift a document's expected pages to where it sits in a merged file. */
function at(doc: Doc, file: string, from: number, scanned = false): DocExpect {
  return {
    file, page_from: from, page_to: from + doc.pages.length - 1, types: doc.types, instance_key: doc.instance ?? undefined, scanned,
    fields: doc.fields.map((f) => ({ ...f, page: f.page === null ? null : f.page + from - 1 })),
  }
}

async function write(dir: string, name: string, bytes: Uint8Array): Promise<void> { await writeFile(join(dir, name), bytes) }

async function gstReportXlsx(): Promise<Uint8Array> {
  const wb = new ExcelJS.Workbook()
  wb.created = new Date('2025-01-01T00:00:00Z')
  wb.modified = new Date('2025-01-01T00:00:00Z')
  wb.creator = 'fixture'
  const ws = wb.addWorksheet('GST Summary')
  ws.addRow(['GST Analysis Report'])
  ws.addRow(['Prepared by Analytics Partner P'])
  ws.addRow(['GSTIN', D.GSTIN])
  ws.addRow(['Legal Name', D.CO.name])
  ws.addRow(['Returns covered', 'GSTR-3B and GSTR-1'])
  ws.addRow([])
  ws.addRow(['Tax Period', 'Taxable Turnover', 'Date of Filing', 'Filing Status'])
  for (const [per, t, d] of D.GST_ROWS) {
    const date = d ? new Date(Date.UTC(Number(d.slice(6)), Number(d.slice(3, 5)) - 1, Number(d.slice(0, 2)))) : null
    ws.addRow([per, t, date, d ? 'Filed' : 'Not filed'])
  }
  ws.addRow([])
  ws.addRow(['Periods not filed', 'Aug-2025'])
  ws.addRow(['Months not filed', 1])
  ws.addRow(['Turnover trend', 'Stable'])
  return new Uint8Array(await wb.xlsx.writeBuffer())
}

async function main(): Promise<void> {
  const tcs: TcSpec[] = []
  const dirs = new Map<string, string>()
  const dirOf = async (tc: string) => {
    let d = dirs.get(tc)
    if (!d) { d = join(ROOT, tc); await rm(d, { recursive: true, force: true }); await mkdir(d, { recursive: true }); dirs.set(tc, d) }
    return d
  }

  const panEntity = D.panEntity()
  const pan1 = D.panPerson(0)
  const pan2 = D.panPerson(1)
  const coi = D.coi()
  const gstReg = D.gstReg()
  const udyam = D.udyam()
  const g4 = D.gstr3b(4, 4215300, '20/05/2025')
  const g5 = D.gstr3b(5, 3968400, '20/06/2025')
  const g6 = D.gstr3b(6, 4402750, '19/07/2025')
  const bank = D.bankStatement()
  const fs = D.auditedFs()
  const itr = D.itrCombined()
  const bureau = D.bureauCommercial()
  const analysis = D.bankAnalysis()
  const bill = D.utilityBill()

  // ---------------------------------------------------------------- TC-03 duplicates
  {
    const dir = await dirOf('TC-03')
    const bytes = await toPdf(udyam.pages)
    await write(dir, 'udyam.pdf', bytes)
    await write(dir, 'udyam_copy.pdf', bytes)
    await write(dir, 'udyam_scan.jpg', await jpeg(degrade(toCanvas(udyam.pages[0], 250), { noise: 8, seed: 3 }), 85))
    const e = at(udyam, 'udyam.pdf', 1)
    tcs.push({
      tc: 'TC-03', title: 'Duplicate files: the same file twice gives the same doc_key; a scanned copy of the same document is a near-duplicate',
      requests: [
        {
          name: 'same file twice',
          files: [
            { file: 'udyam.pdf', original_name: 'udyam_certificate.pdf', content_type: PDF },
            { file: 'udyam_copy.pdf', original_name: 'udyam certificate (1).pdf', content_type: PDF },
          ],
          documents: [e, { ...e, file: 'udyam_copy.pdf' }],
          same_doc_key: [['udyam.pdf', 'udyam_copy.pdf']],
        },
        { name: 'copy alone, later', files: [{ file: 'udyam_copy.pdf', original_name: 'registration.pdf', content_type: PDF }], documents: [{ ...e, file: 'udyam_copy.pdf' }] },
        {
          name: 'digital and scanned copy',
          files: [
            { file: 'udyam.pdf', original_name: 'udyam_certificate.pdf', content_type: PDF },
            { file: 'udyam_scan.jpg', original_name: 'IMG_0412.jpg', content_type: JPG },
          ],
          documents: [e, { ...at(udyam, 'udyam_scan.jpg', 1, true) }],
          duplicate_pair: ['udyam.pdf', 'udyam_scan.jpg'],
        },
      ],
    })
  }

  // ---------------------------------------------------------------- TC-04 merged PDFs
  {
    const dir = await dirOf('TC-04')
    await write(dir, 'merged_bundle.pdf', await toPdf([...coi.pages, ...bank.pages, ...g4.pages]))
    await write(dir, 'merged_gstr3b.pdf', await toPdf([...g4.pages, ...g5.pages, ...g6.pages]))
    tcs.push({
      tc: 'TC-04', title: 'Merged PDFs split into logical documents with page ranges, each classified',
      requests: [
        { name: 'three different documents', files: [{ file: 'merged_bundle.pdf', original_name: 'documents.pdf', content_type: PDF }], documents: [at(coi, 'merged_bundle.pdf', 1), at(bank, 'merged_bundle.pdf', 2), at(g4, 'merged_bundle.pdf', 4)] },
        { name: 'three instances of one type', files: [{ file: 'merged_gstr3b.pdf', original_name: 'gst_returns_q1.pdf', content_type: PDF }], documents: [at(g4, 'merged_gstr3b.pdf', 1), at(g5, 'merged_gstr3b.pdf', 2), at(g6, 'merged_gstr3b.pdf', 3)] },
      ],
    })
  }

  // ---------------------------------------------------------------- TC-05 quality
  {
    const dir = await dirOf('TC-05')
    const p = udyam.pages[0]
    await write(dir, 'scan_clean.jpg', await jpeg(degrade(toCanvas(p, 300), { noise: 6, seed: 5 }), 88))
    await write(dir, 'scan_blur.jpg', await jpeg(degrade(toCanvas(p, 200), { blur: 7, noise: 6, seed: 6 }), 85))
    await write(dir, 'scan_lowres.png', await png(degrade(toCanvas(p, 70), { noise: 4, seed: 7 })))
    await write(dir, 'scan_skew.jpg', await jpeg(degrade(toCanvas(p, 200), { skewDeg: 6, noise: 6, seed: 8 }), 85))
    await write(dir, 'scan_shadow.jpg', await jpeg(degrade(toCanvas(p, 200), { shadow: 0.85, noise: 6, seed: 9 }), 85))
    await write(dir, 'blank.pdf', await toPdf([new Page()]))
    const junk = new Uint8Array(4096)
    for (let i = 0; i < junk.length; i++) junk[i] = (i * 7919 + 13) % 251
    await write(dir, 'corrupt.pdf', new Uint8Array([...new TextEncoder().encode('%PDF-1.7\n'), ...junk]))
    await write(dir, 'encrypted.pdf', await encryptedPdf(udyam.pages))
    // types null: classification of an unreadable page is attempted but not asserted (F-07.6).
    const one = (file: string, ct: string, grades: string[], reasons: string[], types: string[] | null = ['udyam_certificate']): RequestSpec => ({
      name: file, files: [{ file, original_name: file, content_type: ct }],
      documents: [{ file, page_from: 1, page_to: 1, types: types ?? undefined, grades, reasons_any: reasons, scanned: true }],
    })
    tcs.push({
      tc: 'TC-05', title: 'Quality grade per page with reason codes (blurred, skewed, shadowed, low-resolution, blank, corrupt, encrypted)',
      requests: [
        one('scan_clean.jpg', JPG, ['A'], []),
        one('scan_blur.jpg', JPG, ['C', 'U'], ['blur'], null),
        one('scan_lowres.png', PNG, ['B', 'C', 'U'], ['resolution'], null),
        one('scan_skew.jpg', JPG, ['A', 'B', 'C'], ['skew']),
        one('scan_shadow.jpg', JPG, ['A', 'B', 'C'], ['shadow'], null),
        { ...one('blank.pdf', PDF, ['U'], ['blank'], []), file_status: { 'blank.pdf': 'exception' } },
        { ...one('corrupt.pdf', PDF, ['U'], ['corrupt'], []), file_status: { 'corrupt.pdf': 'exception' } },
        { ...one('encrypted.pdf', PDF, ['U'], ['encrypted'], []), file_status: { 'encrypted.pdf': 'exception' } },
      ],
    })
  }

  // ---------------------------------------------------------------- TC-06 by content, not by name
  {
    const dir = await dirOf('TC-06')
    const set: [Doc, string, string, string | null][] = [
      [panEntity, 'pan_entity.pdf', 'bank_statement.pdf', 'bank statement'],
      [pan1, 'pan_director.pdf', 'gst_certificate.pdf', 'gst'],
      [coi, 'coi.pdf', 'itr_2025.pdf', 'itr'],
      [gstReg, 'gst_reg.pdf', 'pan_card.pdf', 'pan'],
      [udyam, 'udyam.pdf', 'balance_sheet.pdf', 'balance sheet'],
      [g4, 'gstr3b_apr.pdf', 'balance_sheet_fy25.pdf', 'balance sheet'],
      [bank, 'bank.pdf', 'kyc_director_1.pdf', 'kyc'],
      [fs, 'fs.pdf', 'bank_statement_april.pdf', 'bank statement'],
      [itr, 'itr.pdf', 'udyam.pdf', 'udyam'],
      [bureau, 'bureau.pdf', 'sanction_letter.pdf', 'sanction letter'],
    ]
    const files: FileSpec[] = []
    const documents: DocExpect[] = []
    for (const [doc, file, misleading, hint] of set) {
      await write(dir, file, await toPdf(doc.pages))
      files.push({ file, original_name: misleading, label_hint: hint, content_type: PDF })
      documents.push({ ...at(doc, file, 1), fields: undefined })
    }
    tcs.push({ tc: 'TC-06', title: 'Every document classified by content; misleading file names and label hints make no difference', requests: [{ name: 'misleading names', files, documents }] })
  }

  // ---------------------------------------------------------------- TC-09 outside the list
  {
    const dir = await dirOf('TC-09')
    await write(dir, 'utility_bill.pdf', await toPdf(bill.pages))
    tcs.push({
      tc: 'TC-09', title: 'A document outside the checklist is unclassified, with suggested types, and never assigned',
      requests: [{ name: 'utility bill', files: [{ file: 'utility_bill.pdf', original_name: 'bank_statement_june.pdf', label_hint: 'bank statement', content_type: PDF }], documents: [{ file: 'utility_bill.pdf', page_from: 1, page_to: 1, types: [], candidates_min: 3 }] }],
    })
  }

  // ---------------------------------------------------------------- TC-10 partner outputs
  {
    const dir = await dirOf('TC-10')
    await write(dir, 'gst_report.xlsx', await gstReportXlsx())
    await write(dir, 'bank_analysis.pdf', await toPdf(analysis.pages))
    await write(dir, 'bureau_commercial.pdf', await toPdf(bureau.pages))
    tcs.push({
      tc: 'TC-10', title: 'Partner GST report (spreadsheet), bank-statement analysis and bureau report recognised and extracted',
      requests: [{
        name: 'partner outputs',
        files: [
          { file: 'gst_report.xlsx', original_name: 'gst_report.xlsx', content_type: XLSX },
          { file: 'bank_analysis.pdf', original_name: 'analysis.pdf', content_type: PDF },
          { file: 'bureau_commercial.pdf', original_name: 'bureau.pdf', content_type: PDF },
        ],
        documents: [
          { file: 'gst_report.xlsx', page_from: 1, page_to: 1, types: ['partner_gst_report'], fields: D.gstReportExpect() },
          at(analysis, 'bank_analysis.pdf', 1),
          at(bureau, 'bureau_commercial.pdf', 1),
        ],
      }],
    })
  }

  // ---------------------------------------------------------------- TC-17 identity
  {
    const dir = await dirOf('TC-17')
    await write(dir, 'pan_entity.pdf', await toPdf(panEntity.pages))
    await write(dir, 'pan_director_1.pdf', await toPdf(pan1.pages))
    await write(dir, 'pan_director_2_photo.jpg', await jpeg(degrade(toCanvas(pan2.pages[0], 220), { skewDeg: 0.8, shadow: 0.2, noise: 10, blur: 1.2, seed: 21 }), 82))
    await write(dir, 'coi.pdf', await toPdf(coi.pages))
    await write(dir, 'gst_reg.pdf', await toPdf(gstReg.pages))
    await write(dir, 'gst_reg_scan.pdf', await scanPdf(gstReg))
    await write(dir, 'udyam.pdf', await toPdf(udyam.pages))
    const f = (file: string, ct = PDF): FileSpec => ({ file, original_name: file, content_type: ct })
    tcs.push({
      tc: 'TC-17', title: 'Identity fields (identifiers, names, dates, the promoter set) extracted with page evidence',
      requests: [{
        name: 'identity documents',
        files: [f('pan_entity.pdf'), f('pan_director_1.pdf'), f('pan_director_2_photo.jpg', JPG), f('coi.pdf'), f('gst_reg.pdf'), f('gst_reg_scan.pdf'), f('udyam.pdf')],
        documents: [at(panEntity, 'pan_entity.pdf', 1), at(pan1, 'pan_director_1.pdf', 1), at(pan2, 'pan_director_2_photo.jpg', 1, true), at(coi, 'coi.pdf', 1), at(gstReg, 'gst_reg.pdf', 1), at(gstReg, 'gst_reg_scan.pdf', 1, true), at(udyam, 'udyam.pdf', 1)],
      }],
    })
  }

  // ---------------------------------------------------------------- TC-18 financial statements
  {
    const dir = await dirOf('TC-18')
    await write(dir, 'fs_fy2024-25.pdf', await toPdf(fs.pages))
    await write(dir, 'fs_fy2024-25_scan.pdf', await scanPdf(fs))
    await write(dir, 'itr_ay2025-26.pdf', await toPdf(itr.pages))
    tcs.push({
      tc: 'TC-18', title: 'Balance-sheet and P&L items extracted per year (digital and scanned); a combined ITR acknowledgement and computation carries both types',
      requests: [{
        name: 'financials',
        files: [{ file: 'fs_fy2024-25.pdf', original_name: 'fs.pdf', content_type: PDF }, { file: 'fs_fy2024-25_scan.pdf', original_name: 'fs_scan.pdf', content_type: PDF }, { file: 'itr_ay2025-26.pdf', original_name: 'itr.pdf', content_type: PDF }],
        documents: [at(fs, 'fs_fy2024-25.pdf', 1), at(fs, 'fs_fy2024-25_scan.pdf', 1, true), at(itr, 'itr_ay2025-26.pdf', 1)],
      }],
    })
  }

  // ---------------------------------------------------------------- TC-19 GSTR-3B
  {
    const dir = await dirOf('TC-19')
    await write(dir, 'gstr3b_2025-04.pdf', await toPdf(g4.pages))
    await write(dir, 'gstr3b_2025-05_scan.pdf', await scanPdf(g5))
    tcs.push({
      tc: 'TC-19', title: 'GSTR-3B turnover by period and filing dates (digital and scanned)',
      requests: [{
        name: 'gst returns',
        files: [{ file: 'gstr3b_2025-04.pdf', original_name: 'gstr3b_apr.pdf', content_type: PDF }, { file: 'gstr3b_2025-05_scan.pdf', original_name: 'gstr3b_may.pdf', content_type: PDF }],
        documents: [at(g4, 'gstr3b_2025-04.pdf', 1), at(g5, 'gstr3b_2025-05_scan.pdf', 1, true)],
      }],
    })
  }

  // ---------------------------------------------------------------- TC-20 bank statement
  {
    const dir = await dirOf('TC-20')
    await write(dir, 'bank_statement.pdf', await toPdf(bank.pages))
    await write(dir, 'bank_statement_scan.pdf', await scanPdf(bank))
    tcs.push({
      tc: 'TC-20', title: 'Bank statement: header fields and every transaction row, checked against the running balance (digital and scanned)',
      requests: [{
        name: 'bank statements',
        files: [{ file: 'bank_statement.pdf', original_name: 'statement.pdf', content_type: PDF }, { file: 'bank_statement_scan.pdf', original_name: 'statement_scan.pdf', content_type: PDF }],
        documents: [at(bank, 'bank_statement.pdf', 1), at(bank, 'bank_statement_scan.pdf', 1, true)],
      }],
    })
  }

  for (const t of tcs) await writeFile(join(await dirOf(t.tc), 'expected.json'), `${JSON.stringify(t, null, 2)}\n`)
  console.log(`fixtures: ${tcs.length} test cases written (page ${A4.w.toFixed(0)}x${A4.h.toFixed(0)} pt)`)
}

main().catch((e) => { console.error(e); process.exit(1) })
