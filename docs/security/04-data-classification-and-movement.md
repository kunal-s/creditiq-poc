# 4. Data Classification and Data Movement

| Document group | Documents | Sensitive data | Classification |
|---|---|---|---|
| KYC | Director KYC, company PAN | PAN, masked Aadhaar, date of birth, address, photograph | Restricted |
| Constitution | Certificate of incorporation, memorandum and articles, board resolution | Promoter and director names, signatures | Confidential |
| Financials and tax | Audited financials, ITR, GSTR-3B, GSTR-1 | PAN, GSTIN, income, turnover | Restricted |
| Banking and credit | Bank statements, existing facilities, sanction letters, bureau report | Account numbers, transactions, credit history | Restricted |
| Credit outputs | Spread, CAM, PD note | Borrower data and the credit decision | Confidential |

**Data movement**

| Stage | From → To | What moves | Protection |
|---|---|---|---|
| 1. Intake | RM, customer link, LOS → CreditIQ | Documents and case details | TLS 1.2+; mTLS with LOS; customer link limited to one case |
| 2. Processing | Inside CreditIQ (OCR, rules) | Documents and extracted data | Encrypted at rest with a KMS key dedicated to RBL |
| 3. AI assist | CreditIQ → Amazon Bedrock | Extracted text only, never files or images | Private AWS endpoint; Bedrock does not store prompts or train on them |
| 4. Output | CreditIQ → LOS, DMS | Approved CAM, spread, PD note and credit file | mTLS through RBL's API gateway |
| 5. Retention | CreditIQ | Case documents and data | Deleted 90 days after closure `[confirm]`; the DMS is the system of record |

Every stage runs in AWS Mumbai (`ap-south-1`). **No data leaves India.**
