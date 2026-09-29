// Hand-written model answers for the fixtures. There is no API key in this
// build, so the model tiers are exercised through recordings written from
// these answers (record.ts) and replayed by the stub provider in the tests.
//
// Classification: the utility bill is none of the configured types.
// Extraction: the computation of income prints turnover under a caption no
// deterministic reader knows ("Receipts from business operations"); the
// model names that row and the service reads the number from the page.
// Every other requested field is answered "not printed" (null).
import type { ModelRequest } from '../../src/llm/provider.js'

export function answer(req: ModelRequest): unknown {
  if (req.task === 'classify') {
    if (/Electricity Bill/i.test(req.user) && /Units Consumed/i.test(req.user)) {
      return { types: ['none_of_these'], ranked: ['existing_facilities_declaration', 'sanction_letter_other_lender', 'partner_bank_analysis'] }
    }
    return undefined
  }
  if (req.task === 'extract') {
    const fields = [...req.user.matchAll(/^- (\w+) \(/gm)].map((m) => m[1])
    const known: Record<string, { raw: string | null; row_label: string | null; page: number }> = {}
    const pageOf = (text: string) => {
      const at = req.user.indexOf(text)
      const marks = [...req.user.slice(0, at).matchAll(/=== Page (\d+) ===/g)]
      return marks.length ? Number(marks[marks.length - 1][1]) : null
    }
    if (fields.includes('turnover') && req.user.includes('Receipts from business operations')) {
      known.turnover = { raw: null, row_label: 'Receipts from business operations', page: pageOf('Receipts from business operations') ?? 2 }
    }
    return { fields: fields.map((f) => ({ field: f, raw: known[f]?.raw ?? null, row_label: known[f]?.row_label ?? null, page: known[f]?.page ?? null })) }
  }
  return undefined
}
