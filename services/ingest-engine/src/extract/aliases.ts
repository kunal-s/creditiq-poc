// How dictionary fields are printed. The published dictionaries give one
// label per field; documents print the same field under several captions.
// These are reading aids only: which fields exist, their types and which are
// key fields come from the published dictionary. A caption prefixed "re:" is
// a regular expression whose group 1 is the value as printed.
//
// Keys: "<dictionary>.<field>" (or "<dictionary>.<table>.<column>" for table
// columns); a plain "<field>" entry applies to every dictionary.

export const ALIASES: Record<string, string[]> = {
  // Generic
  pan: ['permanent account number', 'pan', 'pan no', 'pan of the entity'],
  gstin: ['gstin', 'gstin/uin', 'gst registration number', 'gst number'],
  cin: ['corporate identity number', 'cin'],
  legal_name: ['legal name of the registered person', 'legal name of business', 'legal name'],
  assessment_year: ['assessment year', 'a.y.', 'ay'],

  // PAN of the entity, KYC
  'pan_entity.name': ['name of the entity', 'name'],
  'pan_entity.date_of_incorporation': ['date of incorporation/formation', 'date of incorporation', 'date of formation'],
  'kyc_person.name': ['name'],
  'kyc_person.date_of_birth': ['date of birth', 'd.o.b.', 'dob', 'year of birth'],
  'kyc_person.father_name': ["father's name", 'fathers name', 'father name', 'father'],
  'kyc_person.address': ['address'],
  'kyc_person.id_number_last4': ['re:(?:aadhaar|document|passport|licence|card)\\s+(?:no\\.?|number)\\s*[:.]?\\s*((?:[x*]{4}\\s?){2}\\d{4}|[x*]{4,8}\\d{4})'],

  // Certificate of incorporation
  'certificate_of_incorporation.company_name': ['re:certify that\\s+(.+?)\\s+is\\s+incorporated', 'name of the company', 'company name'],
  'certificate_of_incorporation.incorporation_date': ['date of incorporation', 'incorporated on'],
  'certificate_of_incorporation.registrar': ['re:(registrar of companies[, ]+[a-z][a-z ]+[a-z])', 'registrar'],

  // GST registration (REG-06)
  'gst_registration_certificate.gstin': ['registration number', 'gstin'],
  'gst_registration_certificate.trade_name': ['trade name, if any', 'trade name'],
  'gst_registration_certificate.constitution': ['constitution of business', 'constitution'],
  'gst_registration_certificate.registration_date': ['date of liability', 'date of registration', 'date of validity from'],
  'gst_registration_certificate.address': ['address of principal place of business', 'principal place of business', 'address'],
  'gst_registration_certificate.persons.name': ['name', 'name of person'],
  'gst_registration_certificate.persons.designation': ['designation/status', 'designation', 'status'],

  // Udyam
  'udyam_certificate.udyam_number': ['udyam registration number', 'udyam number', 'registration number'],
  'udyam_certificate.enterprise_name': ['name of enterprise', 'name of the enterprise', 'enterprise name'],
  'udyam_certificate.classification': ['type of enterprise', 'enterprise type', 'classification'],
  'udyam_certificate.activity': ['major activity', 'activity'],
  'udyam_certificate.registration_date': ['date of udyam registration', 'date of registration'],

  // GSTR-3B
  'gstr_3b.period': ['tax period', 'period', 'return period', 'month'],
  'gstr_3b.outward_taxable_supplies': ['outward taxable supplies (other than zero rated, nil rated and exempted)', 'outward taxable supplies'],
  'gstr_3b.tax_payable': ['total tax payable', 'tax payable'],
  'gstr_3b.itc_availed': ['net itc available', 'eligible itc', 'all other itc'],
  'gstr_3b.filing_date': ['date of filing', 'filing date', 'date of arn', 'filed on'],

  // Bank statement
  'bank_statement.bank': ['bank name', 're:^\\s*((?:\\S+\\s+){0,4}bank\\b(?:\\s+\\S+){0,2})\\s*$'],
  'bank_statement.account_holder': ['account holder', 'account name', 'customer name', 'name'],
  'bank_statement.account_number_masked': ['account number', 'account no', 'a/c no', 'a/c number'],
  'bank_statement.ifsc': ['ifsc code', 'ifsc'],
  'bank_statement.opening_balance': ['opening balance'],
  'bank_statement.closing_balance': ['closing balance'],
  'bank_statement.transactions.date': ['txn date', 'transaction date', 'value date', 'date'],
  'bank_statement.transactions.narration': ['narration', 'particulars', 'description', 'transaction details', 'remarks'],
  'bank_statement.transactions.cheque_ref': ['chq./ref.no.', 'chq/ref no', 'cheque no', 'ref no', 'reference', 'chq no'],
  'bank_statement.transactions.debit': ['withdrawal amt.', 'withdrawal', 'withdrawals', 'debit', 'debits', 'dr'],
  'bank_statement.transactions.credit': ['deposit amt.', 'deposit', 'deposits', 'credit', 'credits', 'cr'],
  'bank_statement.transactions.balance': ['closing balance', 'balance'],

  // Financial statements
  'financial_statements.period_end': ['balance sheet as at', 'as at', 'for the year ended', 'year ended'],
  'financial_statements.udin': ['udin'],
  'financial_statements.revenue_from_operations': ['revenue from operations', 'income from operations', 'net sales', 'sales'],
  'financial_statements.other_income': ['other income'],
  'financial_statements.ebitda': ['ebitda', 'earnings before interest, tax, depreciation and amortisation'],
  'financial_statements.depreciation': ['depreciation and amortisation expense', 'depreciation and amortization expense', 'depreciation'],
  'financial_statements.finance_costs': ['finance costs', 'finance cost', 'interest expense'],
  'financial_statements.profit_before_tax': ['profit before tax', 'profit/(loss) before tax'],
  'financial_statements.profit_after_tax': ['profit after tax', 'profit for the year', 'profit/(loss) for the year', 'net profit'],
  'financial_statements.share_capital': ['share capital', "partners' capital", 'partners capital', 'capital account'],
  'financial_statements.reserves_and_surplus': ['reserves and surplus', 'other equity'],
  'financial_statements.net_worth': ['net worth', "total shareholders' funds", 'shareholders funds', 'total equity'],
  'financial_statements.long_term_borrowings': ['long-term borrowings', 'long term borrowings'],
  'financial_statements.short_term_borrowings': ['short-term borrowings', 'short term borrowings'],
  'financial_statements.total_borrowings': ['total borrowings', 'total debt'],
  'financial_statements.inventories': ['inventories', 'inventory', 'stock-in-trade'],
  'financial_statements.trade_receivables': ['trade receivables', 'sundry debtors'],
  'financial_statements.trade_payables': ['trade payables', 'sundry creditors'],
  'financial_statements.current_assets': ['total current assets'],
  'financial_statements.current_liabilities': ['total current liabilities'],

  // ITR
  'itr_acknowledgement.name': ['name'],
  'itr_acknowledgement.acknowledgement_number': ['acknowledgement number', 'acknowledgement no'],
  'itr_acknowledgement.filing_date': ['date of filing', 'filed on', 'e-filing date'],
  'itr_acknowledgement.gross_total_income': ['gross total income'],
  'itr_acknowledgement.total_income': ['total income'],
  'itr_acknowledgement.tax_paid': ['total taxes paid', 'taxes paid', 'tax paid'],
  'itr_computation.business_income': ['profits and gains of business or profession', 'income from business or profession', 'income from business'],
  'itr_computation.total_income': ['total income'],
  'itr_computation.turnover': ['turnover', 'gross receipts', 'sales/turnover'],
  'itr_computation.tax_payable': ['net tax payable', 'total tax payable', 'tax payable'],

  // Bureau
  'bureau_report.subject_name': ['name of the entity', 'borrower name', 'consumer name', 'subject name', 'name'],
  'bureau_report.report_date': ['report date', 'date of report', 'date of issue'],
  'bureau_report.score': ['credit score', 'cmr rank', 'rank', 'score'],
  'bureau_report.observations': ['key observations', 'observations', 'remarks'],
  'bureau_report.facilities.lender': ['lender', 'member name', 'institution'],
  'bureau_report.facilities.facility_type': ['facility type', 'account type', 'type', 'facility'],
  'bureau_report.facilities.sanctioned': ['sanctioned amount', 'sanctioned', 'limit'],
  'bureau_report.facilities.outstanding': ['current balance', 'outstanding', 'balance'],
  'bureau_report.facilities.emi': ['emi', 'instalment', 'installment'],
  'bureau_report.facilities.overdue': ['amount overdue', 'overdue'],
  'bureau_report.facilities.status': ['asset classification', 'status', 'dpd'],

  // Partner reports
  'partner_gst_report.periods_missing': ['periods not filed', 'months not filed', 'missing periods', 'returns not filed'],
  'partner_gst_report.periods.period': ['tax period', 'return period', 'period', 'month'],
  'partner_gst_report.periods.turnover': ['taxable turnover', 'taxable value', 'turnover'],
  'partner_gst_report.periods.filing_date': ['date of filing', 'filing date', 'filed on'],
  'partner_gst_report.periods.filed': ['filing status', 'filed', 'status'],
  'partner_bank_analysis.lenders_paid': ['lenders paid by emi', 'emi paid to', 'lenders'],
  'partner_bank_analysis.accounts.bank': ['bank', 'bank name'],
  'partner_bank_analysis.accounts.account_number_masked': ['account number', 'account no', 'account'],
  'partner_bank_analysis.accounts.month': ['month', 'period'],
  'partner_bank_analysis.accounts.credits': ['total credits', 'credits'],
  'partner_bank_analysis.accounts.debits': ['total debits', 'debits'],
  'partner_bank_analysis.accounts.average_balance': ['average balance', 'avg. balance', 'avg balance'],
  'partner_bank_analysis.accounts.emi': ['emi', 'emis'],
  'partner_bank_analysis.accounts.cheque_returns': ['cheque returns', 'inward returns', 'bounces'],
  'partner_bank_analysis.accounts.cash_deposits': ['cash deposits', 'cash deposit'],
}

/** The printed label without a trailing parenthetical: "Outward taxable supplies (3.1a)" -> "Outward taxable supplies". */
const cleanLabel = (l: string) => l.replace(/\s*\([^)]*\)\s*$/, '').trim().toLowerCase()

export function aliasesFor(dictionary: string, path: string, label: string, name: string): string[] {
  const out = [...(ALIASES[`${dictionary}.${path}`] ?? []), ...(ALIASES[name] ?? []), cleanLabel(label), name.replace(/_/g, ' ')]
  return [...new Set(out.filter(Boolean))]
}
