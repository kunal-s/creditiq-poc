# Ingestion Engine — User Guide

*How to send documents, how to read what comes back, what to do when you don't know the type,
and how to add and maintain types in the catalogue.*

The reference (every endpoint, field and environment variable) is the package
[README](../README.md). This guide is the working manual: it follows the order in which a team
meets the engine.

---

## 1 · In one minute

You send a document — a **URL**, a **file** (PDF, DOCX, HTML, text, a scanned image) or an
**e-mail** (`.eml`, attachments included) — and say what you want out of it: a **type** from the
catalogue (`finance/invoice`, `bank/statement`, `regulation/clauses`…). The engine reads the
document (OCR if needed) and returns **JSON in that type's shape**, with provenance.

```
document + type  ──►  engine  ──►  { data, type, warnings, classification?, provider }
```

If you don't know the type, say `auto`: the engine decides per document, tells you how sure it
is, and — when it isn't — hands the document to a person instead of guessing. What people confirm
or correct is fed back and the engine gets better at *your* documents.

Three things it never does: invent a value that isn't in the text, force a document into a type
it isn't, or register a new type on its own.

---

## 2 · Before you start

| You need | Where |
|---|---|
| The engine's address | `http://localhost:3002` locally; `http://ingest:3002` inside Docker Compose; your deployed URL |
| The API key | `INGEST_API_KEY` from the engine's `.env`; send as `x-api-key: …` (or `Authorization: Bearer …`) |
| A model key on the engine | `AI_API_KEY` in the engine's `.env` — set once by whoever runs it; you never send it |

Check you can reach it:

```bash
curl -s -H "x-api-key: $KEY" http://localhost:3002/v1/health
# {"ok":true,"service":"ingest-engine","provider":{"model":"gpt-4.1-mini",…},"ocr":true,…}
```

See what it can read documents *as*:

```bash
curl -s -H "x-api-key: $KEY" http://localhost:3002/v1/types | jq '.types[] | {id, version, description}'
```

---

## 3 · Using a type you know

### 3.1 Send the document

A file (multipart) — the common case:

```bash
curl -s -H "x-api-key: $KEY" \
  -F file=@invoice.pdf \
  -F type=finance/invoice@1 \
  http://localhost:3002/v1/extract
```

A web page or a file by URL (JSON):

```bash
curl -s -H "x-api-key: $KEY" -H "content-type: application/json" \
  -d '{"url":"https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=10435","type":"regulation/change@1"}' \
  http://localhost:3002/v1/extract
```

An e-mail — every attachment becomes its own document in the answer; the body is one more:

```bash
curl -s -H "x-api-key: $KEY" -F file=@message.eml -F type=filing/acknowledgement@1 -F emailScope=attachments \
  http://localhost:3002/v1/extract
```
`emailScope` is `all` (default), `attachments` or `body`.

**Always pin the version** (`@1`). If the type's owner changes the pack to version 2, your request
is refused with a clear message until you have looked at the change and bumped the pin. That is
the point: a prompt edit upstream can never silently change your numbers.

### 3.2 Add what the engine can't know

- **`rules`** — your own instructions for this call, appended to the type's prompt and winning on
  conflict. Use it for what is specific to *you*: "amounts are in INR", "ignore the marketing
  pages", "the statement is from our own bank, the account holder is always us". Keep the type's
  own instructions for what is true of every document of that kind.
- **`subject`** — `{ "name", "description" }`: who the reader is. Required by `regulation/clauses`
  (applicability is judged against it) and useful wherever a type's prompt says `{{subject}}`.
- **`name`** — a display name for the document, shown to the model as context.
- **`includeText: true`** — return the parsed text too, if you index or store it.

### 3.3 Read the answer

```json
{
  "id": "ING-…", "channel": "file", "type": "finance/invoice@1", "rules": { "applied": true },
  "documents": [{
    "part": "document", "name": "invoice.pdf", "sha256": "…",
    "source": { "kind": "pdf", "pages": 2, "chars": 4120, "ocrPages": 0 },
    "type": { "id": "finance/invoice", "version": 1, "strategy": "fields" },
    "data": { "supplier": "…", "invoiceNumber": "…", "total": 84500, … },
    "warnings": [ "supplierTaxId \"27AAA…\" does not match ^…$" ],
    "provider": { "model": "gpt-4.1-mini-…", "calls": 1, "promptTokens": 1002, "completionTokens": 74, "costUsd": 0.0005, "ms": 2362, "cached": false }
  }],
  "ms": 2410
}
```

- `data` has exactly the type's fields. A field the document does not state is `null` (or `""`
  / `[]`) — the engine is told never to guess.
- `warnings` come from the type's validators (a GSTIN that doesn't look like one, a total below
  zero). They are *hints for you*, never errors.
- `skipped` on a document means no readable text (an empty scan, an e-mail body when you asked
  for attachments only).
- Keep `sha256`: it is what you send back with feedback, and what makes a re-sent document free
  (parse and extraction are cached by content).

### 3.4 Long documents, scans, streaming

- **Long numbered documents** (Acts, Master Directions, contracts) use a type with
  `strategy: "sections"` — `regulation/clauses` is one. The engine splits the text into sections,
  reads only the ones that matter, and returns `{ identity, units[] }` instead of a flat object.
- **Scans and photos** go through OCR automatically; expect a 40-page scan to take minutes.
- **Streaming**: `POST /v1/extract/stream` sends Server-Sent Events (`stage`, `progress`,
  `document`, `classified`, `units`, `result`) so a UI can show what is happening.
- **Text only, no model**: `POST /v1/parse` returns the parsed text — useful to see what the
  extractor will read, or to feed your own model.

---

## 4 · When you don't know the type

Say `type=auto`. For each document the engine decides in this order:

1. **Signatures** — deterministic hints each type declares (sender domain, subject words, file
   name, phrases in the first page). Free, and the first thing tried. A more specific type wins
   over a general one (`sbi/statement` over `bank/statement`).
2. **One cheap model call** — the document's opening text against the catalogue's descriptions
   and a couple of confirmed examples per type. The model names the document's *genre* in its own
   words, picks the closest type, and says whether the document truly **is** one — a delivery
   note is not a purchase order, however similar the fields. The type is taken only if it fits
   *and* confidence ≥ 0.7.
3. **Otherwise nothing is chosen.** The document is read with `generic` (title, summary, dates,
   amounts, parties, references, key points), the answer carries `needsReview: true` with the
   candidates and the reason, and the document joins the **review queue**.

In the answer:

```json
"type": { "id": "sbi/statement", "version": 1, "strategy": "fields" },
"classification": { "type": "sbi/statement", "confidence": 0.95, "by": "signature",
                    "reason": "text ~ /State Bank of India/, …", "candidates": [ … ] }
```
`by` is `signature`, `model` or `none`. Treat `signature` as certain, `model` as strong, `none`
as "a person decides".

### What your application should do with `needsReview`

Show the document to the right person with the candidates, let them pick the type (or say
"none of these"), and send the decision back:

```bash
curl -s -H "x-api-key: $KEY" -H "content-type: application/json" http://localhost:3002/v1/feedback -d '{
  "sha256": "<from the answer>",
  "type": "finance/invoice",
  "verdict": "confirmed",
  "output": { …the data as the person accepted or corrected it… },
  "note": "Our supplier prints the GSTIN under the logo."
}'
```

That one call does three things: the document leaves the review queue, the type gains a
confirmed example (used as few-shot for extraction and as a snippet for classification), and
the metrics record the verdict. If the engine had picked the wrong type, send
`"verdict": "corrected"` with `"from": "<the type it chose>"` so that type's miss is counted too.

### When many unknown documents look alike

That is a new kind of document arriving. The engine notices:

```bash
curl -s -H "x-api-key: $KEY" http://localhost:3002/v1/review/clusters
# [{ "index": 0, "size": 3, "sharedTerms": ["delivery","challan","transporter","consignee"], "items": [ … ] }]

curl -s -H "x-api-key: $KEY" -H "content-type: application/json" -d '{"cluster":0}' http://localhost:3002/v1/review/propose
# { "suggestedId": "logistics/delivery-challan",
#   "pack": { "description": "…", "instructions": "…", "fields": [ … ], "signatures": { "textAny": [ … ] } },
#   "rationale": "…", "accept": { "method": "PUT", "path": "/v1/types/logistics/delivery-challan", "body": { … } } }
```

Read the draft — the fields, the instructions, the signature regexes — edit what you disagree
with, and accept it with the `PUT` it hands you. From the next request those documents classify
into the new type and leave the queue. **The engine never registers a type on its own.**

To drop a queued document without teaching anything: `DELETE /v1/review/<sha256>`.

---

## 5 · Adding a type to the catalogue

### 5.1 Decide whether you need one

Ask: *is this a different kind of document, or the same kind about a different subject?*

- A TDS circular, a GST notification and a state Gazette notification are all **regulations** —
  `regulation/clauses` (or `regulation/change` for an announcement). The subject and the rules
  you send steer them. **No new type.**
- A TDS certificate (Form 16A), a GSTR-3B return, a delivery challan, a purchase order — each is
  a **different kind of document** with its own fields. **New type.**
- An SBI statement is a bank statement with a known layout — **a variant**: `sbi/statement`
  *extends* `bank/statement` and adds only what differs.

### 5.2 Name it

`<namespace>/<type>`, lowercase, dashes: `tax/tds-certificate`, `procurement/purchase-order`,
`sbi/statement`. The namespace is the family or the owner (`finance`, `bank`, `regulation`, a
customer or app name for private types).

### 5.3 Write the pack

A folder in the catalogue (`types/<ns>/<type>/` in this package, or wherever `INGEST_TYPES_DIR`
points):

```
profile.json      what to extract and the shape       (required)
rules.md          how to read this kind of document   (recommended)
reference/*.md    lookups the prompt may cite         (optional)
examples/*.json   confirmed input → output pairs      (2–3 to start; feedback adds more)
```

**profile.json**

```json
{
  "version": 1,
  "description": "A TDS certificate (Form 16A) → deductor, deductee, quarter, amounts and challan details.",
  "instructions": "The document is a TDS certificate in Form 16A issued under section 203 of the Income-tax Act. Extract the deductor and deductee with their TAN/PAN as printed, the financial year and quarter, the certificate number, each payment row with the date, amount paid, tax deducted and the challan (BSR code, date, serial). Amounts as plain numbers. Leave a field empty rather than guess.",
  "fields": [
    { "name": "certificateNumber", "type": "string", "required": true, "description": "As printed" },
    { "name": "deductorName",      "type": "string", "required": true },
    { "name": "deductorTan",       "type": "string", "description": "TAN as printed" },
    { "name": "deducteeName",      "type": "string", "required": true },
    { "name": "deducteePan",       "type": "string" },
    { "name": "financialYear",     "type": "string", "description": "e.g. 2026-27" },
    { "name": "quarter",           "type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"] },
    { "name": "rows", "type": "object[]", "description": "One per payment / deduction line", "items": [
      { "name": "paymentDate", "type": "date", "required": true },
      { "name": "amountPaid",  "type": "number", "required": true },
      { "name": "taxDeducted", "type": "number", "required": true },
      { "name": "bsrCode",     "type": "string" },
      { "name": "challanSerial", "type": "string" } ] },
    { "name": "totalTaxDeducted", "type": "number" }
  ],
  "signatures": { "textAny": ["\\bForm\\s*(No\\.?)?\\s*16A\\b", "\\bTDS certificate\\b", "\\bsection 203\\b"], "confidence": 0.9 },
  "validators": [
    { "field": "deductorTan", "pattern": "^$|^[A-Z]{4}[0-9]{5}[A-Z]$", "message": "TAN is not in the printed format" },
    { "field": "totalTaxDeducted", "min": 0 }
  ]
}
```

Rules of thumb:

- **`description`** — one line; `auto` reads it to decide, so say what the document *is* and
  who issues it.
- **`instructions`** — say what the document is, what to copy exactly ("as printed"), what to
  ignore, what one list item is. Under a page. Don't repeat what the engine already enforces
  (no guessing, ISO dates, plain numbers).
- **Field types**: `string` · `number` · `boolean` · `date` · `string[]` · `object[]` (with
  `items`). `required: true` means the value is never `null`; `enum` on a string restricts it;
  `description` is shown to the model, so say what you mean.
- **`signatures`** — phrases that appear in every document of this kind and rarely elsewhere;
  `textAll` must all match, `textAny` needs one; `sender`, `subject`, `filename` for e-mails and
  files. Regexes are case-insensitive and multiline. Good signatures make `auto` free and certain.
- **`validators`** — the checks a clerk would make: a required id, a format, a range. They produce
  warnings, not failures.

**rules.md** — how to *read* this kind of document, in plain language:

```
- Form 16A prints one row per payment; a row may wrap to two lines — join the continuation.
- The certificate number is in the top-right box, alphanumeric, eight characters.
- "Amount paid/credited" is the gross; "Tax deducted" is the TDS; never add them.
```

**examples/** — two or three short, real cases: `{ "snippet": "<opening text>", "output": { … } }`.
They are used as few-shot for extraction, as snippets for classification, and as regression
tests. Feedback adds more over time.

**Extending a type** — for a variant, write only what differs:

```json
{ "version": 1, "extends": "bank/statement",
  "description": "A State Bank of India account statement (SBI layout).",
  "instructions": "SBI prints Txn Date and Value Date; use Txn Date. Balances carry a CR/DR marker.",
  "fields": [ { "name": "ifsc", "type": "string" } ],
  "signatures": { "textAny": ["\\bState Bank of India\\b", "\\bSBIN0"], "confidence": 0.95 } }
```
Fields merge by name; instructions and rules are appended; signatures, validators and examples
are inherited.

### 5.4 Register it

Either commit the folder (the engine reads the catalogue from disk on every request — nothing
to restart), or register over the API:

```bash
curl -s -X PUT -H "x-api-key: $KEY" -H "content-type: application/json" \
  http://localhost:3002/v1/types/tax/tds-certificate --data-binary @profile.json
```

### 5.5 Test it before anyone depends on it

```bash
# what will the extractor read?
curl -s -H "x-api-key: $KEY" -F file=@sample.pdf http://localhost:3002/v1/parse | jq '.documents[0].text' | head -c 800

# does it extract? (noCache=true while you iterate on the prompt)
curl -s -H "x-api-key: $KEY" -F file=@sample.pdf -F type=tax/tds-certificate@1 -F noCache=true http://localhost:3002/v1/extract | jq '.documents[0] | {data, warnings, provider}'

# does auto find it on its own?
curl -s -H "x-api-key: $KEY" -F file=@sample.pdf -F type=auto http://localhost:3002/v1/extract | jq '.documents[0].classification'
```

Iterate on `instructions` and `rules.md` until three different samples come out right; then
store those three as `examples/`. Run the engine's tests (`npm test`) — every pack must load and
compile.

### 5.6 Change it later — versions

Editing a pack changes what every caller gets. When the change is more than a typo:

1. bump `"version"` in `profile.json`;
2. note what changed and why (a `CHANGELOG.md` in the folder is a good habit);
3. tell the callers — their pinned requests (`@1`) are refused with *"type is at version 2;
   the request pinned @1"* until they review and bump.

Cached results are keyed by the pack's content, so the new version re-extracts and the old one
is never served for it.

---

## 6 · Teaching a type — feedback in practice

| Situation | What to send |
|---|---|
| The result was right | `verdict: confirmed`, `output` = the data as accepted |
| A field was wrong; the type was right | `verdict: corrected`, `output` = the corrected data, `note` = what was wrong ("the GSTIN is under the logo") |
| The type was wrong | `verdict: corrected`, `type` = the right one, `from` = the one chosen, `output` = the right data if you have it |
| `auto` found nothing and a person chose a type | `verdict: confirmed` with that type |

What happens: a file lands in `feedback/<ns>/<type>/<sha8>.json` with the document's opening text
and the accepted output. From the next request it is one of the examples the model sees for that
type, one of the snippets `auto` compares against, and a regression case. **Feedback examples come
first** — the engine prefers your confirmed documents over the pack's shipped ones.

Housekeeping: the files are plain JSON. Delete one that turned out wrong; edit a `note`. Keep
examples short (the engine stores the first 1 500 characters) and representative — three good
ones beat thirty near-duplicates.

---

## 7 · Keeping it healthy

`GET /v1/metrics` — per type:

| Figure | Meaning | When it's off, do this |
|---|---|---|
| `auto.signature / model / none` | how `auto` chose this type | many `model`, few `signature` → add signatures to the pack |
| `reviewRate` | share of recent auto documents that ended in review | > 30 % → a new layout the pack doesn't cover: look at the review queue, add signatures/examples, or propose a variant type |
| `correctionRate` | corrections ÷ verdicts | > 25 % → instructions or fields no longer fit; read the corrections' `note`s and revise the pack (bump the version) |
| `correctedAway` | documents first read as this type, then reassigned | ≥ 5 → the signatures are too loose |
| `warnings` | validator hits | rising → either the documents changed or a validator is wrong |
| `costUsd`, `tokens` | spend | long documents dominate; consider the `sections` strategy or a cheaper model |

`alerts` lists exactly these conditions in words. The review queue itself alerts when five or
more unplaced documents pile up — the cue to look at `/v1/review/clusters`.

---

## 8 · Questions people ask

**Will it tell me a document is a duplicate?** The engine caches by content, so the same bytes
return the same answer at no cost, and `sha256` lets your application recognise a document it has
already processed — but *whether* a repeat matters is the application's call (OneGRC, for
instance, refuses a duplicate instrument and offers "register as a new version"). The engine
extracts; it does not keep your records.

**Can I send the profile instead of naming a type?** Yes — `profile={ instructions, fields }` on
the request, for one-off shapes. Nothing is stored. Use the catalogue as soon as a second caller
or a second day needs the same shape.

**How do I keep a type private to my app?** Put it under your own namespace and keep the folder
in your deployment's catalogue (or register it there). The catalogue is a directory; who can
write to it is who owns the types.

**What does `auto` do with a document that matches two types?** A child beats its parent
(`sbi/statement` over `bank/statement`); two unrelated signature matches are reported as
ambiguous and go to review rather than picking one.

**Does it learn from every document?** No — only from what a person confirmed or corrected. It
proposes types from clusters of unplaced documents; a person accepts them.

**What about secrets?** The model key stays on the engine. Uploaded bytes are not stored; the
parsed text is cached by hash for re-use, and feedback keeps the first 1 500 characters of a
document as an example. Put the engine behind TLS and give each application its own key.

**Limits?** Fetches time out at 30 s, model calls at 180 s with retries. A document of any length
is windowed, so length only costs money; the answer says what it cost.

---

## 9 · Quick reference

| Do this | Call |
|---|---|
| Is it up? | `GET /v1/health` |
| What types exist? | `GET /v1/types` · `GET /v1/types/<ns>/<type>` |
| Extract | `POST /v1/extract` (`file` or `url`; `type` = `ns/type@v` \| `auto`; `rules`, `subject`, `emailScope`, `includeText`, `noCache`) |
| Extract with progress | `POST /v1/extract/stream` (SSE) |
| Text only | `POST /v1/parse` |
| Register / replace a type | `PUT /v1/types/<ns>/<type>` |
| A person's verdict | `POST /v1/feedback` |
| Unplaced documents | `GET /v1/review` · `DELETE /v1/review/<sha>` |
| Look-alikes → draft type | `GET /v1/review/clusters` · `POST /v1/review/propose { cluster }` |
| Health of every type | `GET /v1/metrics` |

Engine settings (its `.env`): `AI_*` (model), `INGEST_PORT`, `INGEST_API_KEY`, `INGEST_TYPES_DIR`,
`INGEST_FEEDBACK_DIR`, `INGEST_AUTO_THRESHOLD`, OCR and window tuning — see the reference.
