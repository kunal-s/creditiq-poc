// Synthetic documents for the sidecar's tests (FRD AD-6). Fictional entities
// only, valid-format identifiers that pass their checks, no seals, emblems or
// QR codes, at most one small footer line, no watermark (CLAUDE.md rule 8).
// Each document carries the values a reviewer would read off it: those are
// the expected results, written here, never taken from the service's output.
import { gstinCheckDigit } from '../../../src/extract/identifiers.js'
import { inr, Page } from './layout.js'

export type Value = string | number | boolean | null
/** A field a reviewer reads off the document: value and page (1-based within the document). */
export interface Expect { field: string; value: Value; page: number | null; key?: boolean }
export interface Doc { name: string; types: string[]; pages: Page[]; fields: Expect[]; instance?: string }

export const CO = {
  name: 'EXAMPLE TOOLS PRIVATE LIMITED',
  trade: 'EXAMPLE TOOLS',
  pan: 'AAGCE4821K',
  cin: 'U28990MH2016PTC281734',
  udyam: 'UDYAM-MH-26-0048213',
  address: 'Plot 14, MIDC Industrial Area, Bhosari, Pune, Maharashtra 411026',
}
export const GSTIN = `27${CO.pan}1Z${gstinCheckDigit(`27${CO.pan}1Z`)}`
export const DIRECTORS = [
  { name: 'ANAND VARMA RAO', father: 'SURESH VARMA RAO', pan: 'ABKPV7310R', dob: '12/08/1978', dobIso: '1978-08-12' },
  { name: 'KAVITA MENON DESAI', father: 'RAMESH MENON DESAI', pan: 'BCQPD2284M', dob: '03/02/1982', dobIso: '1982-02-03' },
]

const L = 56 // label column
const V = 270 // value column

function footer(p: Page, k: number, n: number): void { p.text(297, 815, `Page ${k} of ${n}`, { size: 8 }) }

// ------------------------------------------------------------------ identity

export function panEntity(): Doc {
  const p = new Page()
  p.text(L, 90, 'INCOME TAX DEPARTMENT', { size: 14, bold: true })
  p.text(L, 112, 'Permanent Account Number Card', { size: 11 })
  p.rule(L, 124, 540)
  p.text(L, 160, 'Permanent Account Number', { size: 9 })
  p.text(L, 178, CO.pan, { size: 14, bold: true })
  p.text(L, 214, 'Name', { size: 9 })
  p.text(L, 232, CO.name, { size: 12 })
  p.text(L, 268, 'Date of Incorporation/Formation', { size: 9 })
  p.text(L, 286, '14/03/2016', { size: 12 })
  return {
    name: 'pan_entity', types: ['pan_entity'], pages: [p],
    fields: [
      { field: 'pan', value: CO.pan, page: 1, key: true },
      { field: 'name', value: CO.name, page: 1, key: true },
      { field: 'date_of_incorporation', value: '2016-03-14', page: 1 },
    ],
  }
}

export function panPerson(i = 0): Doc {
  const d = DIRECTORS[i]
  const p = new Page()
  p.text(L, 90, 'INCOME TAX DEPARTMENT', { size: 14, bold: true })
  p.text(L, 112, 'Permanent Account Number Card', { size: 11 })
  p.rule(L, 124, 540)
  p.text(L, 160, 'Permanent Account Number', { size: 9 })
  p.text(L, 180, d.pan, { size: 15, bold: true })
  p.text(L, 216, 'Name', { size: 9 })
  p.text(L, 236, d.name, { size: 13 })
  p.text(L, 272, "Father's Name", { size: 9 })
  p.text(L, 292, d.father, { size: 13 })
  p.text(L, 328, 'Date of Birth', { size: 9 })
  p.text(L, 348, d.dob, { size: 13 })
  return {
    name: `pan_person_${i + 1}`, types: ['kyc_pan_individual'], pages: [p], instance: d.pan,
    fields: [
      { field: 'pan', value: d.pan, page: 1, key: true },
      { field: 'name', value: d.name, page: 1, key: true },
      { field: 'father_name', value: d.father, page: 1 },
      { field: 'date_of_birth', value: d.dobIso, page: 1 },
    ],
  }
}

export function coi(): Doc {
  const p = new Page()
  p.text(297, 90, 'Certificate of Incorporation', { size: 16, bold: true })
  p.text(150, 110, '[Pursuant to sub-section (2) of section 7 of the Companies Act, 2013]', { size: 9 })
  p.text(L, 160, `I hereby certify that ${CO.name} is incorporated on this`, { size: 10 })
  p.text(L, 176, 'fourteenth day of March two thousand sixteen under the Companies Act, 2013 (18 of 2013)', { size: 10 })
  p.text(L, 192, 'and that the company is limited by shares.', { size: 10 })
  p.text(L, 224, `The Corporate Identity Number of the company is ${CO.cin}.`, { size: 10 })
  p.text(L, 256, 'Date of Incorporation', { size: 10 })
  p.text(V, 256, '14/03/2016', { size: 10 })
  p.text(L, 272, 'Permanent Account Number', { size: 10 })
  p.text(V, 272, CO.pan, { size: 10 })
  p.text(L, 320, 'Given under my hand at Mumbai.', { size: 10 })
  p.text(360, 380, 'Registrar of Companies, Mumbai', { size: 10 })
  return {
    name: 'coi', types: ['certificate_of_incorporation'], pages: [p],
    fields: [
      { field: 'company_name', value: CO.name, page: 1, key: true },
      { field: 'cin', value: CO.cin, page: 1, key: true },
      { field: 'incorporation_date', value: '2016-03-14', page: 1 },
      { field: 'registrar', value: 'Registrar of Companies, Mumbai', page: 1 },
    ],
  }
}

export function gstReg(): Doc {
  const p = new Page()
  p.text(297, 70, 'Form GST REG-06', { size: 13, bold: true })
  p.text(260, 86, '[See Rule 10(1)]', { size: 9 })
  p.text(230, 106, 'Registration Certificate', { size: 12, bold: true })
  p.text(L, 132, 'Goods and Services Tax Act', { size: 9 })
  p.text(L, 160, 'Registration Number', { size: 10 })
  p.text(V, 160, GSTIN, { size: 11, bold: true })
  const rows: [string, string][] = [
    ['1. Legal Name', CO.name],
    ['2. Trade Name, if any', CO.trade],
    ['3. Constitution of Business', 'Private Limited Company'],
    ['4. Address of Principal Place of Business', 'Plot 14, MIDC Industrial Area, Bhosari'],
    ['', 'Pune, Maharashtra 411026'],
    ['5. Date of Liability', '01/07/2017'],
    ['6. Type of Registration', 'Regular'],
  ]
  rows.forEach(([a, b], i) => { if (a) p.text(L, 190 + i * 18, a, { size: 10 }); p.text(V, 190 + i * 18, b, { size: 10 }) })
  p.text(L, 340, 'Details of Managing / Authorized Partners / Karta / Directors', { size: 10, bold: true })
  p.text(L, 364, 'Name', { size: 10, bold: true })
  p.text(V, 364, 'Designation/Status', { size: 10, bold: true })
  DIRECTORS.forEach((d, i) => { p.text(L, 384 + i * 18, d.name, { size: 10 }); p.text(V, 384 + i * 18, 'Director', { size: 10 }) })
  return {
    name: 'gst_reg', types: ['gst_registration_certificate'], pages: [p],
    fields: [
      { field: 'gstin', value: GSTIN, page: 1, key: true },
      { field: 'legal_name', value: CO.name, page: 1, key: true },
      { field: 'trade_name', value: CO.trade, page: 1 },
      { field: 'constitution', value: 'Private Limited Company', page: 1, key: true },
      { field: 'registration_date', value: '2017-07-01', page: 1 },
      { field: 'persons[0].name', value: DIRECTORS[0].name, page: 1, key: true },
      { field: 'persons[0].designation', value: 'Director', page: 1 },
      { field: 'persons[1].name', value: DIRECTORS[1].name, page: 1, key: true },
      { field: 'persons[1].designation', value: 'Director', page: 1 },
    ],
  }
}

export function udyam(): Doc {
  const p = new Page()
  p.text(297, 80, 'Udyam Registration Certificate', { size: 15, bold: true })
  p.text(150, 100, 'Ministry of Micro, Small and Medium Enterprises', { size: 10 })
  const rows: [string, string][] = [
    ['Udyam Registration Number', CO.udyam],
    ['Type of Enterprise', 'Small'],
    ['Major Activity', 'Manufacturing'],
    ['Name of Enterprise', CO.name],
    ['Date of Incorporation', '14/03/2016'],
    ['Date of Udyam Registration', '18/09/2020'],
  ]
  rows.forEach(([a, b], i) => { p.text(L, 150 + i * 22, a, { size: 11 }); p.text(V, 150 + i * 22, b, { size: 11 }) })
  p.text(L, 300, 'Official address of enterprise', { size: 11 })
  p.text(V, 300, 'Plot 14, MIDC Industrial Area, Bhosari, Pune', { size: 11 })
  return {
    name: 'udyam', types: ['udyam_certificate'], pages: [p],
    fields: [
      { field: 'udyam_number', value: CO.udyam, page: 1, key: true },
      { field: 'enterprise_name', value: CO.name, page: 1, key: true },
      { field: 'classification', value: 'Small', page: 1 },
      { field: 'activity', value: 'Manufacturing', page: 1 },
      { field: 'registration_date', value: '2020-09-18', page: 1 },
    ],
  }
}

// ------------------------------------------------------------------ tax

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export function gstr3b(month: number, taxable: number, filed: string): Doc {
  const p = new Page()
  const fy = '2025-26'
  const cgst = Math.round(taxable * 0.09 * 100) / 100
  p.text(297, 60, 'Form GSTR-3B', { size: 14, bold: true })
  p.text(275, 76, '[See rule 61(5)]', { size: 9 })
  p.text(380, 100, 'Year', { size: 10 }); p.text(450, 100, fy, { size: 10 })
  p.text(380, 116, 'Period', { size: 10 }); p.text(450, 116, MONTH_NAMES[month - 1], { size: 10 })
  const kv: [string, string][] = [
    ['1. GSTIN', GSTIN],
    ['2(a). Legal name of the registered person', CO.name],
    ['2(b). Trade name, if any', CO.trade],
    ['2(c). ARN', `AA27${String(month).padStart(2, '0')}25${String(3100000 + month * 7919).slice(0, 7)}`],
    ['2(d). Date of ARN', filed],
  ]
  kv.forEach(([a, b], i) => { p.text(40, 150 + i * 16, a, { size: 9 }); p.text(V, 150 + i * 16, b, { size: 9 }) })
  p.text(40, 250, '3.1 Details of Outward supplies and inward supplies liable to reverse charge', { size: 9, bold: true })
  const cols = [340, 400, 460, 515, 560]
  const hdr = ['Total Taxable value', 'Integrated Tax', 'Central Tax', 'State/UT Tax', 'Cess']
  p.text(40, 270, 'Nature of Supplies', { size: 7, bold: true })
  hdr.forEach((h, i) => p.text(cols[i], 270, h, { size: 7, bold: true, right: true }))
  const rows: [string, number[]][] = [
    ['(a) Outward taxable supplies (other than zero rated, nil rated and exempted)', [taxable, 0, cgst, cgst, 0]],
    ['(b) Outward taxable supplies (zero rated)', [0, 0, 0, 0, 0]],
    ['(c) Other outward supplies (nil rated, exempted)', [0, 0, 0, 0, 0]],
    ['(d) Inward supplies (liable to reverse charge)', [0, 0, 0, 0, 0]],
  ]
  rows.forEach(([label, vals], i) => {
    p.text(40, 288 + i * 15, label, { size: 7 })
    vals.forEach((v, k) => p.text(cols[k], 288 + i * 15, inr(v), { size: 7, right: true }))
  })
  const itc = Math.round(cgst * 0.78 * 100) / 100
  p.text(40, 370, '4. Eligible ITC', { size: 9, bold: true })
  p.text(40, 388, 'Details', { size: 7, bold: true })
  hdr.slice(1).forEach((h, i) => p.text(cols[i + 1], 388, h, { size: 7, bold: true, right: true }))
  p.text(40, 404, '(C) Net ITC Available (A) - (B)', { size: 7 })
  ;[0, itc, itc, 0].forEach((v, k) => p.text(cols[k + 1], 404, inr(v), { size: 7, right: true }))
  const period = `2025-${String(month).padStart(2, '0')}`
  return {
    name: `gstr3b_${period}`, types: ['gstr_3b'], pages: [p], instance: period,
    fields: [
      { field: 'gstin', value: GSTIN, page: 1, key: true },
      { field: 'legal_name', value: CO.name, page: 1 },
      { field: 'period', value: period, page: 1, key: true },
      { field: 'outward_taxable_supplies', value: taxable, page: 1, key: true },
      { field: 'filing_date', value: `${filed.slice(6)}-${filed.slice(3, 5)}-${filed.slice(0, 2)}`, page: 1, key: true },
    ],
  }
}

export function itrCombined(): Doc {
  const a = new Page()
  a.text(297, 70, 'INDIAN INCOME TAX RETURN ACKNOWLEDGEMENT', { size: 12, bold: true })
  a.text(230, 88, '[Where the data of the Return of Income has been transmitted electronically]', { size: 8 })
  const kv: [string, string][] = [
    ['Assessment Year', '2025-26'],
    ['Name', CO.name],
    ['PAN', CO.pan],
    ['Form Number', 'ITR-6'],
    ['Acknowledgement Number', '482716305140725'],
    ['Date of filing', '28/10/2025'],
    ['Filed through', 'e-Filing portal'],
  ]
  kv.forEach(([k, v], i) => { a.text(L, 130 + i * 18, k, { size: 10 }); a.text(V, 130 + i * 18, v, { size: 10 }) })
  const inc: [string, number][] = [['Gross Total Income', 10245600], ['Total Income', 9840200], ['Total taxes paid', 2532100]]
  inc.forEach(([k, v], i) => { a.text(L, 290 + i * 18, k, { size: 10 }); a.text(480, 290 + i * 18, inr(v, 0), { size: 10, right: true }) })
  footer(a, 1, 2)
  const b = new Page()
  b.text(297, 70, 'Computation of Total Income', { size: 13, bold: true })
  b.text(L, 100, 'Assessment Year', { size: 10 }); b.text(V, 100, '2025-26', { size: 10 })
  b.text(L, 116, 'PAN', { size: 10 }); b.text(V, 116, CO.pan, { size: 10 })
  const comp: [string, number][] = [
    ['Receipts from business operations', 184625400],
    ['Profits and gains of business or profession', 9610400],
    ['Income from other sources', 229800],
    ['Total Income', 9840200],
    ['Net tax payable', 2532100],
  ]
  comp.forEach(([k, v], i) => { b.text(L, 160 + i * 18, k, { size: 10 }); b.text(480, 160 + i * 18, inr(v, 0), { size: 10, right: true }) })
  footer(b, 2, 2)
  return {
    name: 'itr_ay2025-26', types: ['itr_acknowledgement', 'itr_computation'], pages: [a, b], instance: 'AY2025-26',
    fields: [
      { field: 'assessment_year', value: '2025-26', page: 1, key: true },
      { field: 'pan', value: CO.pan, page: 1, key: true },
      { field: 'name', value: CO.name, page: 1 },
      { field: 'acknowledgement_number', value: '482716305140725', page: 1 },
      { field: 'filing_date', value: '2025-10-28', page: 1 },
      { field: 'gross_total_income', value: 10245600, page: 1 },
      { field: 'total_income', value: 9840200, page: 1, key: true },
      { field: 'tax_paid', value: 2532100, page: 1 },
      { field: 'business_income', value: 9610400, page: 2 },
      { field: 'turnover', value: 184625400, page: 2, key: true },
      { field: 'tax_payable', value: 2532100, page: 2 },
    ],
  }
}

// ------------------------------------------------------------------ financial statements

export function auditedFs(): Doc {
  const r = new Page()
  r.text(297, 70, "Independent Auditor's Report", { size: 14, bold: true })
  r.text(L, 100, `To the Members of ${CO.name}`, { size: 10 })
  const para = [
    'Report on the Audit of the Financial Statements',
    'Opinion',
    'We have audited the accompanying financial statements of the Company, which comprise the balance',
    'sheet as at 31 March 2025, the statement of profit and loss for the year then ended, and notes to',
    'the financial statements. In our opinion the financial statements give a true and fair view in',
    'conformity with the accounting principles generally accepted in India.',
  ]
  para.forEach((t, i) => r.text(L, 130 + i * 16, t, { size: 10, bold: i < 2 }))
  r.text(L, 300, 'For Gokhale Nair & Co.', { size: 10 })
  r.text(L, 316, 'Chartered Accountants', { size: 10 })
  r.text(L, 332, 'Firm Registration No. 112233W', { size: 10 })
  r.text(L, 364, 'UDIN: 25123456AABBCC1234', { size: 10 })
  r.text(L, 380, 'Place: Pune', { size: 10 })
  r.text(L, 396, 'Date: 12/09/2025', { size: 10 })
  footer(r, 1, 3)

  const colNote = 330
  const col1 = 450
  const col2 = 550
  const bs = new Page()
  bs.text(L, 60, CO.name, { size: 11, bold: true })
  bs.text(L, 78, 'Balance Sheet as at 31 March 2025', { size: 12, bold: true })
  bs.text(col2, 96, '(Amount in Rs.)', { size: 8, right: true })
  bs.text(L, 116, 'Particulars', { size: 9, bold: true }); bs.text(colNote, 116, 'Note', { size: 9, bold: true, right: true })
  bs.text(col1, 116, '31 March 2025', { size: 9, bold: true, right: true }); bs.text(col2, 116, '31 March 2024', { size: 9, bold: true, right: true })
  const bsRows: [string, number | null, number | null, string?][] = [
    ["Shareholders' funds", null, null],
    ['Share capital', 10000000, 10000000, '3'],
    ['Reserves and surplus', 28456300, 22140800, '4'],
    ["Total shareholders' funds", 38456300, 32140800],
    ['Non-current liabilities', null, null],
    ['Long-term borrowings', 11240000, 13080000, '5'],
    ['Current liabilities', null, null],
    ['Short-term borrowings', 18520000, 16210000, '6'],
    ['Trade payables', 9645200, 8812600, '7'],
    ['Other current liabilities', 2218400, 1965300, '8'],
    ['Total current liabilities', 30383600, 26987900],
    ['Current assets', null, null],
    ['Inventories', 16430500, 14820100, '9'],
    ['Trade receivables', 22175900, 19640300, '10'],
    ['Cash and bank balances', 1842700, 1285400, '11'],
    ['Total current assets', 40449100, 35745800],
  ]
  bsRows.forEach(([label, a, b, note], i) => {
    const y = 138 + i * 17
    bs.text(label === label.replace(/^(Total|Shareholders|Non-current|Current)/, '') ? L + 10 : L, y, label, { size: 9, bold: a === null })
    if (note) bs.text(colNote, y, note, { size: 9, right: true })
    if (a !== null) bs.text(col1, y, inr(a, 0), { size: 9, right: true })
    if (b !== null) bs.text(col2, y, inr(b, 0), { size: 9, right: true })
  })
  footer(bs, 2, 3)

  const pl = new Page()
  pl.text(L, 60, CO.name, { size: 11, bold: true })
  pl.text(L, 78, 'Statement of Profit and Loss for the year ended 31 March 2025', { size: 12, bold: true })
  pl.text(col2, 96, '(Amount in Rs.)', { size: 8, right: true })
  pl.text(L, 116, 'Particulars', { size: 9, bold: true }); pl.text(colNote, 116, 'Note', { size: 9, bold: true, right: true })
  pl.text(col1, 116, '31 March 2025', { size: 9, bold: true, right: true }); pl.text(col2, 116, '31 March 2024', { size: 9, bold: true, right: true })
  const plRows: [string, number, number, string?][] = [
    ['Revenue from operations', 184625400, 161280300, '12'],
    ['Other income', 1240600, 985200, '13'],
    ['Total income', 185866000, 162265500],
    ['Cost of materials consumed', 118240300, 104512800, '14'],
    ['Employee benefits expense', 21480600, 19806400, '15'],
    ['Finance costs', 3862100, 4120500, '16'],
    ['Depreciation and amortisation expense', 2418300, 2205600, '17'],
    ['Other expenses', 31444000, 24583300, '18'],
    ['Total expenses', 177445300, 155228600],
    ['Profit before tax', 8420700, 7036900],
    ['Tax expense', 2105200, 1772100],
    ['Profit for the year', 6315500, 5264800],
  ]
  plRows.forEach(([label, a, b, note], i) => {
    const y = 138 + i * 17
    pl.text(L, y, label, { size: 9, bold: /^(Total|Profit)/.test(label) })
    if (note) pl.text(colNote, y, note, { size: 9, right: true })
    pl.text(col1, y, inr(a, 0), { size: 9, right: true })
    pl.text(col2, y, inr(b, 0), { size: 9, right: true })
  })
  footer(pl, 3, 3)
  return {
    name: 'fs_fy2024-25', types: ['audited_financial_statements'], pages: [r, bs, pl], instance: 'FY-end 2025-03-31',
    fields: [
      { field: 'period_end', value: '2025-03-31', page: 2, key: true },
      { field: 'audited', value: true, page: 1 },
      { field: 'auditor', value: 'Gokhale Nair & Co.', page: 1 },
      { field: 'udin', value: '25123456AABBCC1234', page: 1 },
      { field: 'revenue_from_operations', value: 184625400, page: 3, key: true },
      { field: 'other_income', value: 1240600, page: 3 },
      { field: 'ebitda', value: null, page: null, key: true },
      { field: 'depreciation', value: 2418300, page: 3 },
      { field: 'finance_costs', value: 3862100, page: 3 },
      { field: 'profit_before_tax', value: 8420700, page: 3 },
      { field: 'profit_after_tax', value: 6315500, page: 3, key: true },
      { field: 'share_capital', value: 10000000, page: 2 },
      { field: 'reserves_and_surplus', value: 28456300, page: 2 },
      { field: 'net_worth', value: 38456300, page: 2, key: true },
      { field: 'long_term_borrowings', value: 11240000, page: 2 },
      { field: 'short_term_borrowings', value: 18520000, page: 2 },
      { field: 'total_borrowings', value: null, page: null, key: true },
      { field: 'inventories', value: 16430500, page: 2 },
      { field: 'trade_receivables', value: 22175900, page: 2 },
      { field: 'trade_payables', value: 9645200, page: 2 },
      { field: 'current_assets', value: 40449100, page: 2, key: true },
      { field: 'current_liabilities', value: 30383600, page: 2, key: true },
    ],
  }
}

// ------------------------------------------------------------------ bank

export const OPENING = 542180.5
export const TXNS: [string, string, string, number, number][] = [
  // date, narration, ref, debit, credit
  ['02/04/2025', 'NEFT CR CUSTOMER A INV 1021', 'N091234', 0, 325000],
  ['04/04/2025', 'NACH DR LENDER X EMI', 'NACH0425', 145000, 0],
  ['07/04/2025', 'CASH DEPOSIT PUNE BRANCH', '', 0, 85000],
  ['10/04/2025', 'RTGS DR SUPPLIER C', 'R10423', 210500, 0],
  ['15/04/2025', 'GST PAYMENT', 'CPIN2504', 64300, 0],
  ['18/04/2025', 'NEFT CR CUSTOMER B', 'N118820', 0, 192750],
  ['22/04/2025', 'CHQ DEP 004512 HARBOUR TRADERS', '004512', 0, 60000],
  ['23/04/2025', 'CHQ RETURN 004512 INSUFFICIENT FUNDS', '004512', 60000, 0],
  ['28/04/2025', 'SALARY APR 2025', '', 340000, 0],
  ['02/05/2025', 'NEFT CR CUSTOMER A INV 1044', 'N092207', 0, 410200],
  ['05/05/2025', 'NACH DR LENDER X EMI', 'NACH0525', 145000, 0],
  ['09/05/2025', 'CASH DEPOSIT PUNE BRANCH', '', 0, 120000],
  ['14/05/2025', 'RTGS DR SUPPLIER C', 'R14518', 245800, 0],
  ['20/05/2025', 'GST PAYMENT', 'CPIN2505', 71900, 0],
  ['27/05/2025', 'SALARY MAY 2025', '', 340000, 0],
  ['03/06/2025', 'NEFT CR NORTHLINE COMPONENTS', 'N093318', 0, 502400],
  ['05/06/2025', 'NACH DR LENDER X EMI', 'NACH0625', 145000, 0],
  ['06/06/2025', 'NACH DR LENDER Z FINANCE EMI', 'NACH0626', 38500, 0],
  ['12/06/2025', 'CASH DEPOSIT PUNE BRANCH', '', 0, 95000],
  ['19/06/2025', 'NEFT CR DELTA CASTINGS', 'N119904', 0, 218300],
  ['20/06/2025', 'GST PAYMENT', 'CPIN2506', 68450, 0],
  ['27/06/2025', 'SALARY JUN 2025', '', 340000, 0],
]

export function bankStatement(): Doc {
  const pages = [new Page(), new Page()]
  const [p1, p2] = pages
  p1.text(L, 60, 'Bank Y Limited', { size: 15, bold: true })
  p1.text(L, 78, 'Pune Industrial Area Branch', { size: 9 })
  p1.text(L, 104, 'Statement of Account', { size: 12, bold: true })
  const kv: [string, string][] = [
    ['Account Holder', CO.name],
    ['Account Number', 'XXXXXXXX4521'],
    ['IFSC', 'BKYL0004521'],
    ['Statement Period', 'From 01/04/2025 To 30/06/2025'],
  ]
  kv.forEach(([k, v], i) => { p1.text(L, 128 + i * 15, k, { size: 9 }); p1.text(180, 128 + i * 15, v, { size: 9 }) })
  const X = { date: 40, nar: 96, ref: 262, wd: 395, dep: 475, bal: 555 }
  const header = (p: Page, y: number) => {
    p.text(X.date, y, 'Date', { size: 8, bold: true })
    p.text(X.nar, y, 'Narration', { size: 8, bold: true })
    p.text(X.ref, y, 'Chq./Ref.No.', { size: 8, bold: true })
    p.text(X.wd, y, 'Withdrawal Amt.', { size: 8, bold: true, right: true })
    p.text(X.dep, y, 'Deposit Amt.', { size: 8, bold: true, right: true })
    p.text(X.bal, y, 'Closing Balance', { size: 8, bold: true, right: true })
    p.rule(36, y + 5, 560)
  }
  header(p1, 212)
  p1.text(X.nar, 230, 'Opening Balance', { size: 8 })
  p1.text(X.bal, 230, inr(OPENING), { size: 8, right: true })
  const fields: Expect[] = [
    { field: 'bank', value: 'Bank Y Limited', page: 1, key: true },
    { field: 'account_holder', value: CO.name, page: 1, key: true },
    { field: 'account_number_masked', value: 'XXXXXXXX4521', page: 1, key: true },
    { field: 'ifsc', value: 'BKYL0004521', page: 1 },
    { field: 'period_from', value: '2025-04-01', page: 1, key: true },
    { field: 'period_to', value: '2025-06-30', page: 1, key: true },
    { field: 'opening_balance', value: OPENING, page: 1 },
  ]
  let bal = OPENING
  const split = 14
  TXNS.forEach(([date, nar, ref, dr, cr], i) => {
    const onFirst = i < split
    const p = onFirst ? p1 : p2
    const y = onFirst ? 248 + i * 17 : 90 + (i - split) * 17
    bal = Math.round((bal + cr - dr) * 100) / 100
    p.text(X.date, y, date, { size: 8 })
    p.text(X.nar, y, nar, { size: 8 })
    if (ref) p.text(X.ref, y, ref, { size: 8 })
    if (dr) p.text(X.wd, y, inr(dr), { size: 8, right: true })
    if (cr) p.text(X.dep, y, inr(cr), { size: 8, right: true })
    p.text(X.bal, y, inr(bal), { size: 8, right: true })
    const page = onFirst ? 1 : 2
    const iso = `${date.slice(6)}-${date.slice(3, 5)}-${date.slice(0, 2)}`
    fields.push({ field: `transactions[${i}].date`, value: iso, page })
    fields.push({ field: `transactions[${i}].narration`, value: nar, page })
    if (dr) fields.push({ field: `transactions[${i}].debit`, value: dr, page, key: true })
    if (cr) fields.push({ field: `transactions[${i}].credit`, value: cr, page, key: true })
    fields.push({ field: `transactions[${i}].balance`, value: bal, page, key: true })
  })
  header(p2, 72)
  const endY = 90 + (TXNS.length - split) * 17 + 10
  p2.text(X.nar, endY, 'Closing Balance', { size: 8, bold: true })
  p2.text(X.bal, endY, inr(bal), { size: 8, bold: true, right: true })
  fields.push({ field: 'closing_balance', value: bal, page: 2 })
  footer(p1, 1, 2)
  footer(p2, 2, 2)
  return { name: 'bank_statement', types: ['bank_statement'], pages, fields, instance: 'acct-4521' }
}

// ------------------------------------------------------------------ partner outputs

export function bankAnalysis(): Doc {
  const p = new Page()
  p.text(L, 60, 'Bank Statement Analysis Report', { size: 15, bold: true })
  p.text(L, 80, 'Prepared by Analytics Partner P', { size: 9 })
  p.text(L, 104, 'Customer', { size: 9 }); p.text(170, 104, CO.name, { size: 9 })
  p.text(L, 120, 'Accounts analysed', { size: 9 }); p.text(170, 120, '1', { size: 9 })
  p.text(L, 150, 'Monthly Summary', { size: 11, bold: true })
  const X = [40, 110, 170, 250, 320, 390, 440, 490, 555]
  const hdr = ['Bank', 'Account No', 'Month', 'Total Credits', 'Total Debits', 'Avg. Balance', 'EMI', 'Cheque Returns', 'Cash Deposits']
  hdr.forEach((h, i) => p.text(X[i], 172, h, { size: 7, bold: true, right: i >= 3 }))
  const months: [string, number, number, number, number, number, number][] = [
    ['Apr-2025', 662750, 819800, 691240.35, 145000, 1, 85000],
    ['May-2025', 530200, 802700, 612870.1, 145000, 0, 120000],
    ['Jun-2025', 815700, 736950, 523115.8, 183500, 0, 95000],
  ]
  const fields: Expect[] = []
  months.forEach((m, i) => {
    const y = 190 + i * 16
    p.text(X[0], y, 'Bank Y', { size: 7 })
    p.text(X[1], y, 'XXXX4521', { size: 7 })
    p.text(X[2], y, m[0], { size: 7 })
    ;[m[1], m[2], m[3], m[4]].forEach((v, k) => p.text(X[3 + k], y, inr(v), { size: 7, right: true }))
    p.text(X[7], y, String(m[5]), { size: 7, right: true })
    p.text(X[8], y, inr(m[6]), { size: 7, right: true })
    const f = (c: string, v: Value, key = false) => fields.push({ field: `accounts[${i}].${c}`, value: v, page: 1, key })
    f('bank', 'Bank Y'); f('account_number_masked', 'XXXX4521'); f('month', `2025-0${4 + i}`, true)
    f('credits', m[1], true); f('debits', m[2], true); f('average_balance', m[3]); f('emi', m[4], true); f('cheque_returns', m[5], true); f('cash_deposits', m[6], true)
  })
  p.text(L, 280, 'Lenders paid by EMI', { size: 9 }); p.text(200, 280, 'Lender X, Lender Z Finance', { size: 9 })
  fields.push({ field: 'lenders_paid', value: 'Lender X, Lender Z Finance', page: 1, key: true })
  return { name: 'bank_analysis', types: ['partner_bank_analysis'], pages: [p], fields }
}

export function bureauCommercial(): Doc {
  const p = new Page()
  p.text(L, 60, 'Commercial Credit Information Report', { size: 14, bold: true })
  p.text(L, 78, 'Credit Bureau X', { size: 9 })
  const kv: [string, string][] = [['Name of the Entity', CO.name], ['PAN', CO.pan], ['Report Date', '15/07/2025'], ['CMR Rank', 'CMR-4']]
  kv.forEach(([k, v], i) => { p.text(L, 104 + i * 16, k, { size: 9 }); p.text(200, 104 + i * 16, v, { size: 9 }) })
  p.text(L, 190, 'Credit Facilities', { size: 11, bold: true })
  const X = [40, 130, 290, 350, 410, 470, 500]
  const hdr = ['Lender', 'Facility Type', 'Sanctioned Amount', 'Current Balance', 'EMI', 'Amount Overdue', 'Status']
  hdr.forEach((h, i) => p.text(X[i], 210, h, { size: 7, bold: true, right: i >= 2 && i <= 5 }))
  const rows: [string, string, number, number, number, number, string][] = [
    ['Lender X', 'Term Loan', 5000000, 3240000, 145000, 0, 'Standard'],
    ['Lender Z Finance', 'Equipment Loan', 1500000, 612000, 38500, 0, 'Standard'],
    ['Bank Y', 'Cash Credit', 15000000, 13820000, 0, 0, 'Standard'],
  ]
  const fields: Expect[] = [
    { field: 'subject_name', value: CO.name, page: 1, key: true },
    { field: 'pan', value: CO.pan, page: 1 },
    { field: 'report_date', value: '2025-07-15', page: 1 },
    { field: 'score', value: 'CMR-4', page: 1, key: true },
  ]
  rows.forEach((r, i) => {
    const y = 228 + i * 16
    p.text(X[0], y, r[0], { size: 7 })
    p.text(X[1], y, r[1], { size: 7 })
    ;[r[2], r[3], r[4], r[5]].forEach((v, k) => p.text(X[2 + k], y, inr(v, 0), { size: 7, right: true }))
    p.text(X[6], y, r[6], { size: 7 })
    const f = (c: string, v: Value, key = false) => fields.push({ field: `facilities[${i}].${c}`, value: v, page: 1, key })
    f('lender', r[0], true); f('facility_type', r[1]); f('sanctioned', r[2], true); f('outstanding', r[3], true); f('emi', r[4], true); f('overdue', r[5], true); f('status', r[6])
  })
  p.text(L, 340, 'Key Observations', { size: 9, bold: true })
  p.text(200, 340, 'No overdue in the last 12 months', { size: 9 })
  fields.push({ field: 'observations', value: 'No overdue in the last 12 months', page: 1, key: true })
  return { name: 'bureau_commercial', types: ['bureau_commercial'], pages: [p], fields }
}

/** Rows of the partner GST report (XLSX): period, turnover, filed on, status. */
export const GST_ROWS: [string, number, string | null][] = [
  ['Apr-2025', 4215300, '20/05/2025'],
  ['May-2025', 3968400, '20/06/2025'],
  ['Jun-2025', 4402750, '19/07/2025'],
  ['Jul-2025', 4120900, '20/08/2025'],
  ['Aug-2025', 3877600, null],
  ['Sep-2025', 4310050, '20/10/2025'],
]

export function gstReportExpect(): Expect[] {
  const f: Expect[] = [
    { field: 'gstin', value: GSTIN, page: 1, key: true },
    { field: 'legal_name', value: CO.name, page: 1 },
    { field: 'periods_missing', value: 'Aug-2025', page: 1, key: true },
  ]
  GST_ROWS.forEach(([per, t, d], i) => {
    f.push({ field: `periods[${i}].period`, value: `2025-${per.slice(0, 3) === 'Apr' ? '04' : per.slice(0, 3) === 'May' ? '05' : per.slice(0, 3) === 'Jun' ? '06' : per.slice(0, 3) === 'Jul' ? '07' : per.slice(0, 3) === 'Aug' ? '08' : '09'}`, page: 1, key: true })
    f.push({ field: `periods[${i}].turnover`, value: t, page: 1, key: true })
    if (d) f.push({ field: `periods[${i}].filing_date`, value: `${d.slice(6)}-${d.slice(3, 5)}-${d.slice(0, 2)}`, page: 1 })
    f.push({ field: `periods[${i}].filed`, value: Boolean(d), page: 1 })
  })
  return f
}

// ------------------------------------------------------------------ outside the list

export function utilityBill(): Doc {
  const p = new Page()
  p.text(L, 60, 'City Power Utility', { size: 15, bold: true })
  p.text(L, 80, 'Electricity Bill', { size: 12 })
  const kv: [string, string][] = [
    ['Consumer Name', CO.name],
    ['Consumer No.', '170023456781'],
    ['Bill Month', 'June 2025'],
    ['Tariff Category', 'LT-V Industrial'],
    ['Sanctioned Load', '85 kW'],
    ['Units Consumed', '14,210'],
    ['Current Charges', '1,38,450.00'],
    ['Previous Balance', '0.00'],
    ['Amount Payable', '1,38,450.00'],
    ['Due Date', '18/07/2025'],
  ]
  kv.forEach(([k, v], i) => { p.text(L, 110 + i * 18, k, { size: 10 }); p.text(V, 110 + i * 18, v, { size: 10 }) })
  p.text(L, 320, 'Please pay by the due date to avoid a delayed payment charge.', { size: 9 })
  return { name: 'utility_bill', types: [], pages: [p], fields: [] }
}
