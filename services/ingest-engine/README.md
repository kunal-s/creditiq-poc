# The Ingestion Engine

> New to it? Start with the **[user guide](docs/GUIDE.md)** — how to send documents, what to do when you don't know the type, how to add and maintain catalogue types. This page is the reference.

## In plain words

**What it does.** You send it a document — a web page, a PDF, a Word file, a scanned image, an
e-mail with attachments — and tell it *what kind of information you want out of it* (a regulatory
circular's clauses, an invoice's lines, a vendor's SOC 2 report's findings). It reads the document
(OCR if it's a scan), asks a language model to extract exactly that information, checks the answer
against the shape you asked for, and returns clean JSON.

**Think of it as** a very fast junior analyst who reads any document you hand over and fills in the
form you gave them — and who never remembers your company: everything specific to you arrives with
each request.

**What it does not do.**
- It does not keep your documents or a database of what it read (that's the RAG engine).
- It does not decide what to do with the result; it returns JSON and forgets.
- It does not know your domain. "Information types" (what to extract, in what shape) are profiles
  you define and can add without changing the engine.

**How you use it, in three steps.**
1. Start it (`./start.sh`) with an `AI_API_KEY`; it listens on port 3002 behind an API key.
2. `POST /v1/extract` with the file (or URL) and the information type you want.
3. Read the JSON back; store it, show it, or feed it to the next step.

**Where OneGRC uses it.** The Source Library wizard (a directive URL or file → its clauses), Mail
Intake (an attachment → what it is), and the regulatory-source watch.

A self-contained module that turns **any document** — a web page, an uploaded file (PDF, DOCX,
HTML, text, a scanned image), or an e-mail with attachments — into **the structured information a
calling application asked for**. What to extract is defined per *information type* as a
**profile** (plain-language instructions + the shape of the answer), optionally refined by
**rules** the caller sends with the request. The engine reads, OCRs, extracts and returns JSON;
the caller decides what to do with it. It has **no configuration of its own beyond the model
provider**: no tenants, worlds, folders or channels — everything that is specific to an
application arrives at run time, in the request.

It is its own package — **`packages/ingest-engine/`** — with its own `package.json`, dependencies,
tests and Docker image, and **no import from OneGRC**. It runs as a separate service on
`INGEST_PORT` (default 3002), authenticated by `INGEST_API_KEY` (`x-api-key` or
`Authorization: Bearer`). OneGRC is one client among any number: it calls the engine over HTTP
from `server/src/ingest/client.ts`. Nothing in the engine writes to any application's data.

```bash
packages/ingest-engine/start.sh   # fresh clone → paste your AI_API_KEY → installed, tested, built, running, with test commands
npm run dev:ingest                # engine alone, watch mode (or: npm run dev — web + api + engine)
npm run ingest:serve              # engine alone
npm run test:ingest               # the engine's contract tests (no model needed)
docker compose up ingest          # its own container, built from packages/ingest-engine/Dockerfile
```

---

## 1 · What it does, end to end

```
                         ┌──────────────── the type catalogue ────────────────┐
                         │ types/<ns>/<type>/  profile · rules · reference ·   │
                         │ examples · signatures · validators   (+ feedback/) │
                         └─────────────────────────┬──────────────────────────┘
                                                   │ the type named by the caller,
                                                   │ or chosen by `auto`
input ──► acquire ──► parse ──► [OCR] ──► classify ─┴─► extract ──► validate ──► JSON ──► the app
 url        fetch      PDF text   pages with  signatures    prompt from    warnings     data ·      decides
 file       bytes      DOCX       no text     → model       the pack       from the     type ·
 e-mail     .eml       HTML       layer, and  → or review   + caller rules pack         classification
                       text       images      queue         + examples                  needsReview
                                                   ▲                                       │
                                                   │   POST /v1/feedback: what a person      │
                                                   └─── confirmed or corrected becomes ◄─────┘
                                                        an example the type learns from
```

**The life of a document**

1. **Acquire** — a URL is fetched (cached 6 h); a file is taken as bytes; an `.eml` is parsed
   into its body plus each attachment, and every attachment becomes its own document.
2. **Parse** — PDF via pdf.js (text layer); DOCX via mammoth; HTML via html-to-text; plain text
   as-is. Pages with no text layer (scans) and standalone images (PNG, JPEG, TIFF, BMP, WebP) go
   through **OCR** (tesseract.js, WASM, in-process — no external OCR service). Parses are cached
   by content hash, so a re-sent document never OCRs twice.
3. **Which type** — the caller names one from the **catalogue** (`type: "finance/invoice@1"`,
   §3), sends a one-off `profile`, or says **`auto`** (§3a): the pack signatures are checked
   first (deterministic), then one cheap model call names the genre and picks a type only if the
   document truly *is* one; otherwise the document is read as `generic`, flagged `needsReview`
   and put in the **review queue** for a person.
4. **Prompt** — the pack's instructions and strict output schema, its `rules.md` and reference
   text, up to two **confirmed examples** of that type (feedback first), and the caller's own
   `rules` for this call (§4), which win on conflict.
5. **Extract** — the text is cut into windows (`INGEST_WINDOW_CHARS`, default 14 000) and one
   structured-output call is made per window in parallel, against an OpenAI-compatible endpoint
   (`AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL` — OpenAI, vLLM, Ollama `/v1`, …). The JSON schema is
   *strict*: every property present, no extras, so the answer always has the declared shape.
   A `sections` type (long numbered documents) uses the split → identity ∥ triage → parallel
   extraction → merge pipeline instead (§3, Strategies).
6. **Merge and validate** — window answers are combined in code (arrays concatenate, scalars
   take the first non-empty value); the pack's validators produce `warnings`, never errors.
7. **Answer** — one JSON envelope per request with one entry per document: `data` in the type's
   shape, `type` (id and version it was read as), `classification` and `needsReview` when `auto`
   decided, `warnings`, and provenance (hash, pages, OCR count, model, tokens, cost, cache hit).
8. **Feedback** (§3b) — the application shows the result to a person where it matters; what they
   confirm or correct goes back as `POST /v1/feedback` and becomes an example the type learns
   from. **Metrics** (§3c) watch every type's review and correction rates and say when a type
   drifts or a new kind of document keeps arriving — and can draft a pack for it.

Results are cached by (parsed text hash, type and version, prompt, rules, model). Change a pack,
an example or the rules and the next call re-extracts; send the same thing again and it is free.

---

## 2 · The API

Base path: `/v1`.

### `GET /v1/health`
```json
{ "ok": true, "service": "onegrc-ingest", "promptVersion": "…", "provider": { "model": "gpt-4.1-mini", "baseUrl": "…" },
  "ocr": true, "inputs": ["url","pdf","docx","html","txt","png","jpg","tiff","eml"] }
```

### `POST /v1/extract` — one JSON answer
Send **either** JSON with a `url`, **or** `multipart/form-data` with a `file`.

| Field | Where | Meaning |
|---|---|---|
| `url` | JSON | Page or file to fetch |
| `file` | multipart | The bytes: PDF · DOCX · HTML · TXT · PNG/JPG/TIFF · `.eml` |
| `type` | both | A catalogue type — `bank/statement`, pinned `bank/statement@2` — or **`auto`** to let the engine choose per document (§3a). Default: `generic` |
| `profile` | both | A one-off inline profile object (§3) instead of a catalogue type |
| `rules` | both | The caller's own instructions for this call, appended to the profile's prompt (§4). Optional |
| `channel` | both | `url` · `file` · `email` — a label echoed back; the engine infers it (JSON → `url`; `.eml` → `email`; other files → `file`) and uses it only to decide how to read the bytes |
| `subject` | both | `{ name, description }` — who the reader is; replaces `{{subject}}` in a profile's prompts (or is appended as context) |
| `name` | both | A display name for the document, passed to the model as context |
| `emailScope` | both | For e-mails: `all` (default) · `attachments` · `body` |
| `noCache` | both | `true` to bypass every cache |

In multipart, object fields (`profile`, `subject`) are sent as JSON strings.

**Response**
```json
{
  "id": "ING-3f9c1a0b2d7e",
  "channel": "email",
  "type": "auto",
  "rules": { "applied": true, "sha256": "d214…" },
  "documents": [
    {
      "part": "attachment",                       // "document" | "attachment" | "body"
      "name": "GSTR3B-ACK.txt",
      "sha256": "…",
      "contentType": "text/plain",
      "mail": { "from": "GSTN <noreply@gst.gov.in>", "to": "…", "subject": "…", "date": "…", "messageId": "…" },
      "source": { "kind": "text", "pages": 1, "chars": 212, "ocrPages": 0 },
      "type": { "id": "filing/acknowledgement", "version": 1, "strategy": "fields" },
      "classification": { "type": "filing/acknowledgement", "confidence": 0.9, "by": "signature", "reason": "text ~ /\\bARN\\b/ …", "candidates": [ … ] },   // with type: "auto"
      "needsReview": false,                          // true when auto found nothing: data is the generic shape
      "warnings": [ "supplierTaxId … does not match …" ],   // the pack's validators; never an error
      "data": { "portal": "GSTN", "returnType": "GSTR-3B", "period": "08/2026", "referenceNumber": "AA270826123456Z",
                "filedOn": "2026-09-18", "entityName": "State Bank of India", "registrationId": "27AAACS8577K1ZO",
                "status": "FILED", "amounts": [ { "label": "Tax paid", "value": 412880 } ] },
      "provider": { "model": "gpt-4.1-mini-2025-04-14", "calls": 1, "promptTokens": 1002, "completionTokens": 74, "costUsd": 0.0005, "ms": 2362, "cached": false }
    }
  ],
  "ms": 2410
}
```
`data` is exactly the profile's shape. A document with no readable text carries `data: null` and a
`skipped` reason. Errors: `400 bad_request` · `400 bad_profile` · `401 unauthorised` ·
`400 bad_type` (unknown pin, bad id) · `404 unknown_type` · `422 fetch_failed` · `503 no_provider` (no model key configured).

### `POST /v1/extract/stream` — Server-Sent Events
Same request; the answer arrives as events so a UI can show progress:
`stage` (`fetch` · `parse` · `ocr` · `analyse` · `extract` · `merge`) · `progress` (`ocr` / `extract`, done/total)
· `document` (index, count, name, part, chars, pages, ocrPages) · `units` (sections strategy: each group's units as they land)
· `result` (the envelope above) · `error`.

### `POST /v1/parse` — text only, no model
Same input; returns each document's parsed text (with `[[page n]]` markers for PDFs) and OCR
counts. Use it to see what the extractor will read, or to feed your own model.

### Catalogue, feedback, review, metrics
- `GET /v1/types` — every type: id, version, namespace, `extends`, description, strategy, fields, signatures, example counts.
- `GET /v1/types/<ns>/<type>` — one type in full, resolved through `extends` (instructions, rules, reference, schema, examples).
- `PUT /v1/types/<ns>/<type>` — register or replace a type's `profile.json` in the catalogue.
- `POST /v1/feedback` — `{ sha256, type, verdict: confirmed | corrected, output?, note?, from? }` — what a person settled becomes an example (§3b).
- `GET /v1/metrics` — per-type counts, review and correction rates, drift alerts (§3c).
- `GET /v1/review` · `DELETE /v1/review/<sha256>` — documents `auto` could not place.
- `GET /v1/review/clusters` · `POST /v1/review/propose { cluster }` — look-alike groups and a draft type for one (§3c).

---

## 3 · Types — the catalogue and the profile language

A type's profile answers two questions: **what to look for** (`instructions`, plain language) and
**what shape to return** (`fields`, or a raw JSON `schema`).

### Fields (the simple way)
```json
{
  "description": "A supplier invoice → parties, amounts, taxes, due date",
  "instructions": "The document is an invoice. Extract the supplier and customer as printed, the invoice number and date, the due date, each line item with its amount, taxes by name and the grand total. Amounts as plain numbers.",
  "fields": [
    { "name": "supplier",      "type": "string",   "required": true },
    { "name": "invoiceNumber", "type": "string",   "required": true },
    { "name": "invoiceDate",   "type": "date" },
    { "name": "lineItems",     "type": "object[]", "items": [
        { "name": "description", "type": "string", "required": true },
        { "name": "amount",      "type": "number", "required": true } ] },
    { "name": "total",         "type": "number",   "required": true }
  ]
}
```
Types: `string` · `number` · `boolean` · `date` (ISO 8601 when the full date is printed) ·
`string[]` · `object[]` (with `items`). A field that is not `required` comes back `null` when the
text does not state it — the engine is told never to guess. `description` on a field is passed to
the model, so say what you mean ("GSTIN as printed", "period as printed, e.g. 08/2026").

### Schema (when you already have one)
`"schema": { "type": "object", "properties": { … } }` — any JSON schema for an object; the engine
makes it strict (all properties required, no extras, recursively). Use `["string","null"]` for
optional values.

### Where profiles live — the type catalogue

A profile is the caller's statement of what it wants from a document. Across many applications
the same statements recur — a bank statement is a bank statement — so the engine serves a
**catalogue** of them: one folder per type, namespaced and versioned, owned by whoever owns the
document type (a content team, an app team), loaded fresh from disk on every request.

```
types/<namespace>/<type>/
  profile.json     version · description · extends? · strategy · instructions · fields | schema | unit/identity/triage
                   signatures?  cheap hints for `auto` (sender, subject, file name, text patterns)
                   validators?  post-checks → warnings on the response
  rules.md         how to read this family of documents (appended to the prompt)
  reference/*.md   lookups the prompt may cite (codes, formats…), capped at 12 000 characters
  examples/*.json  { snippet, mail?, output, note? } — confirmed input→output pairs
```

- **Name it**: `type: "finance/invoice@1"`. The pin is the contract — if the catalogue moves to
  version 2 the request is refused until the caller reviews the change and bumps the pin.
- **Extend it**: `"extends": "bank/statement"` in `sbi/statement` inherits fields (merged by
  name), instructions (appended as *specifics*), rules, signatures, validators and examples. One
  definition of "a bank statement", many flavours. `auto` prefers the more specific type.
- **Register it**: `PUT /v1/types/<ns>/<type>` writes `profile.json`; or send a one-off shape
  inline as `profile` — nothing is stored.
- The engine ships a starter catalogue in `packages/ingest-engine/types/` (`regulation/clauses`,
  `regulation/change`, `filing/acknowledgement`, `assurance/report`, `audit/request`,
  `incident/notice`, `finance/invoice`, `bank/statement`, `sbi/statement`) and one built-in,
  `generic`. Everything else is yours.

### 3a · `type: "auto"` — when the caller does not know

Explicit beats inferred: name the type whenever the application knows it. For genuinely unknown
intake (a shared mailbox, a drop folder) `auto` decides per document, in this order:

1. **Signatures** — each pack's deterministic hints (`sender`, `subject`, `filename`, `textAll`,
   `textAny`) over the e-mail headers and the first 4 000 characters. Free, auditable, first. A
   child type that matches beats its parent; two unrelated matches are reported as ambiguous.
2. **One cheap model call** — the document's head against the catalogue's descriptions and up to
   two example snippets per type. The model names the document's *genre* in its own words, picks
   the closest type, and says whether the document truly **is** an instance of it (a delivery note
   is not an order, however similar the fields). Chosen only if it fits *and* confidence ≥
   `INGEST_AUTO_THRESHOLD` (0.7).
3. **Otherwise nothing is chosen**: the document is read with `generic`, the response carries
   `needsReview: true`, the candidates and the reason, and the document joins the **review queue**
   for a person to settle. The engine never forces a match and never invents a type.

Every answer says how it was decided (`classification.by`: `signature` · `model` · `none`).

### 3b · Feedback — how a type learns

```json
POST /v1/feedback
{ "sha256": "<from the response>", "type": "procurement/purchase-order", "verdict": "confirmed",
  "output": { …the data as accepted or corrected by the person… }, "note": "Amounts in lakh grouping read correctly.",
  "from": "finance/invoice"   // for a correction: the type the engine had chosen }
```
The document's opening text (from the engine's parse cache, or `snippet` if sent) and the
accepted output are stored under `INGEST_FEEDBACK_DIR/<ns>/<type>/<sha8>.json` and loaded with the
pack's own examples from then on — as **few-shot** for extraction of that type (feedback examples
first: the caller's own documents), as **snippets** for classification, and as **regression
cases**. Nothing is retrained; every example is a file a person can read, edit or delete. A
feedback verdict also removes the document from the review queue and counts in the metrics.

### 3c · Drift and gaps — metrics, the review queue, proposed types

`GET /v1/metrics` — per type: requests, how `auto` chose it (signature / model / none), average
confidence, validator warnings, confirmed vs corrected verdicts, documents first read as it and
reassigned elsewhere, tokens and cost; over a rolling window of 200 events, the **review rate**
and **correction rate**. Alerts fire when a type's review rate passes 30 % (a layout the
signatures and examples do not cover), its correction rate passes 25 % (instructions or fields no
longer fit), or five documents were reassigned away from it (signatures too loose) — and when the
queue itself has five or more unplaced documents.

`GET /v1/review` lists what `auto` could not place (snippet, headers, candidates, the generic
reading). `GET /v1/review/clusters` groups look-alikes by shared vocabulary; for a cluster of
three or more, `POST /v1/review/propose { "cluster": 0 }` drafts a pack from the samples — a
suggested id, description, instructions, flat fields, signature regexes and the rationale — and
returns exactly the `PUT /v1/types/…` call that would accept it. **A person accepts it; the engine
never registers a type on its own.** Once accepted, the queued documents classify on the next
pass and leave the queue.

### Strategies
`"strategy": "fields"` (default) — windowed structured extraction merged in code, for any shape.

`"strategy": "sections"` — for long documents laid out in numbered units (sections, rules,
paragraphs, articles, controls). The engine splits the text into units, runs an **identity** pass
over the front matter in parallel with a **triage** pass over a compact index of the units, reads
only the selected units in parallel groups (an amendment rides with the section it amends), and
**merges** the answers by a key. Everything the model is told and everything it returns comes
from the profile:

```json
{
  "strategy": "sections",
  "instructions": "…what a unit is, what to skip, how to fill each field… {{subject}} …",
  "unit": {
    "name": "clauses",                 // the array's key in the output, and how the instructions refer to it
    "key": "provision",                // the field that identifies a unit across parallel calls
    "keyNormalise": "section-root",    // "Section 5(3A)" and "12(a)" fold into "Section 5" / "12"; or "exact"
    "pageField": "pageRef",            // earliest page wins as the base when a unit is seen twice
    "textField": "whatItMeans",        // a later occurrence's differing text is appended with a page note
    "confidenceField": "confidence",   // merged units take the minimum
    "skipIf": { "field": "nameOfCompliance", "pattern": "^(removal|omission|deletion|repeal) of\\b" },
    "fields": [ { "name": "provision", "type": "string", "required": true }, … ]
  },
  "identity": { "instructions": "…front-matter prompt… {{subject}}", "fields": [ … ], "defaults": { "instrumentType": "Act" } },
  "triage":   { "instructions": "…which units to read in full…", "alwaysInclude": "\\b(penalty for|interest on)\\b" }
}
```
Output: `data = { identity, units, provider, source }`, where `provider` says which strategy ran
(`triage` or `windowed` fallback), how many units were found and selected and why, calls, tokens,
cost. `{{subject}}` in any instructions is replaced by `"<name>: <description>"` from the
request's `subject`. Field `enum`s are honoured. The catalogue's `regulation/clauses` pack is a
complete worked example (the compliance-analyst prompt, the clause shape, penalty grading,
identity and triage criteria) — content, not engine code.

---

## 4 · Rules — the caller's own instructions, sent at run time

Rules are text the calling application adds to the prompt for one call. They refine the profile;
where they conflict, they win. The engine stores nothing about them — it does not know your
tenants, customers, departments or channels — so **the caller owns the rules and sends them with
every request** (`rules` field). Because rules are part of the cache key, a changed rules text
re-extracts on the next call.

How a caller organises them is its own affair. OneGRC, for example, keeps one file per world
(customer) and channel and reads it in its own code before calling the engine:

```
server/rules/<world>/url.md      pages fetched from the web
server/rules/<world>/file.md     uploaded or dropped files (any type, scans included)
server/rules/<world>/email.md    e-mail attachments and bodies
server/rules/default/*.md        fallback when the world has no file
```
`server/src/sources/rules.ts` → `rulesFor(world, channel)` → `rules` in the request. The Source
Library wizard sends `channel: url` or `file`, Mail Intake sends `email`. The State Bank of India rules under
`server/rules/sbi/` are a worked example of what such text looks like — regulator page anatomy,
reference-number formats, OCR caution, what to skip. Another application might keep rules in its
database per customer, or per document source, and send them the same way.

---

## 5 · Hooking it into an application

### Pattern A — HTTP from any language (recommended)
```bash
# a URL, a catalogue type pinned to its version
curl -s http://ingest:3002/v1/extract -H "x-api-key: $INGEST_API_KEY" -H "content-type: application/json" \
  -d '{"url":"https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=10435","type":"regulation/change@1"}'

# a file, a catalogue type, your own rules for this call
curl -s http://ingest:3002/v1/extract -H "x-api-key: $INGEST_API_KEY" \
  -F file=@statement.pdf -F type=bank/statement@1 -F 'rules=Ignore promotional pages at the end. Amounts are in INR.'

# an e-mail from a shared mailbox — let the engine decide the type per attachment
curl -s http://ingest:3002/v1/extract -H "x-api-key: $INGEST_API_KEY" -F file=@message.eml -F type=auto -F emailScope=attachments

# a one-off shape, inline
curl -s http://ingest:3002/v1/extract -H "x-api-key: $INGEST_API_KEY" -F file=@po.pdf -F 'profile={"instructions":"Extract the purchase order.","fields":[{"name":"poNumber","type":"string","required":true},{"name":"total","type":"number"}]}'

# tell it what a person decided (teaches the type; clears the review queue)
curl -s http://ingest:3002/v1/feedback -H "x-api-key: $INGEST_API_KEY" -H "content-type: application/json" \
  -d '{"sha256":"<from the response>","type":"finance/invoice","verdict":"confirmed","output":{…}}'
```
```ts
// Node / browser
const form = new FormData()
form.set('file', file)                       // File | Blob
form.set('type', 'filing/acknowledgement@1')          // a catalogue type — or 'auto', or an inline profile
const res = await fetch('https://ingest.example/v1/extract', { method: 'POST', headers: { 'x-api-key': KEY }, body: form })
const { documents } = await res.json()
for (const d of documents) if (d.data) saveEvidence(d.data)
```
```python
import requests
r = requests.post("https://ingest.example/v1/extract", headers={"x-api-key": KEY},
                  files={"file": open("invoice.pdf", "rb")}, data={"type": "finance/invoice@1"})
for d in r.json()["documents"]:
    if d["data"]: post_to_erp(d["data"])
```

### Pattern B — in-process (a Node application that depends on the package)
```ts
import { extract } from '@onegrc/ingest-engine'

const rules = await myApp.rulesFor(customer, 'file')     // your own source of rules — a file, a table, a setting
const out = await extract({ raw: { channel: 'file', buf, contentType: 'application/pdf', filename: 'inv.pdf' }, type: 'finance/invoice@1', rules })
```
`extract()` takes an optional event callback (the same events as the SSE stream). `createIngestApp({ auth })`
lets a Hono application mount the HTTP surface with its own authentication.

### Pattern C — behind a queue
Put `{ url | bytes, profile, rules, correlationId }` on your queue; a worker calls
`POST /v1/extract` and posts the envelope to your webhook. Idempotency comes for free: the same
bytes with the same profile and rules return the cached answer.

### What the caller does with the answer
The engine stops at JSON. OneGRC, for instance, turns `regulatory-clauses` into unverified
clauses for a person to review, `filing-acknowledgement` into evidence on an obligation cycle,
`incident-notice` into an incident with regulator clocks. Your application maps `data` to its own
records — keep the `sha256` and `id` for provenance, and keep the person in the loop for anything
that binds the organisation.

### How OneGRC is wired (the reference client)
- `server/src/ingest/client.ts` — `extract`, `extractStream` (relays the SSE events), `parse`,
  `engineHealth`; configured by `INGEST_URL` and `INGEST_API_KEY`.
- `/api/ingest` and `/api/ingest/stream` — take the browser's upload or URL, look up OneGRC's rules
  for the world and channel (`server/src/sources/rules.ts`), call the engine with
  `type: regulation/clauses@1` (`INGEST_CLAUSES_TYPE` — the pin is a deliberate contract), the
  rules, `subject` and `includeText`; turn `{ identity, units }` into clause records
  (`server/src/sources/clauses.ts`: severity from penalty tiers, quotes clipped, `verified: false`);
  keep the bytes in OneGRC's file store, index the text into the knowledge base, hand the clauses
  to the wizard.
- Source watch re-reads regulator pages through `parse` (text only); Mail Intake sends accepted
  attachments through the same route with `channel: email`.
- `/api/health` reports `ingest: { ok, url }` so a missing engine is visible at once.

---

## 6 · Running it as an independent module

### Setting up after cloning

The package ships **`.env.example`** only; the real `.env` holds keys, is git-ignored, and has to
exist before the engine runs. `./start.sh` creates it, asks for **`AI_API_KEY`** (the one value you
supply — an OpenAI key, or any OpenAI-compatible endpoint's key), generates `INGEST_API_KEY`,
installs, tests, builds and runs. `./start.sh --setup` stops after `.env` is written and
dependencies are installed; `./start.sh --help` prints the steps.

**By hand:**

```bash
cp .env.example .env
#   AI_API_KEY=sk-…                  your model key (not OpenAI? also set AI_BASE_URL and AI_MODEL)
#   INGEST_API_KEY=<long random>     what every caller must send as x-api-key (openssl rand -hex 24)
#   everything else is preset for Docker: INGEST_PORT=3002 · INGEST_TYPES_DIR=./types ·
#   INGEST_FEEDBACK_DIR=./feedback · INGEST_AUTO_THRESHOLD=0.7
npm install && npm test
npm run dev                          # with node, on :3002 — or the container:
docker build --build-arg PKG=. -t ingest-engine . && docker run -d --name ingest-engine -p 3002:3002 --env-file .env \
  -v ingest_cache:/app/.cache -v ingest_tessdata:/app/.tessdata -v ingest_feedback:/app/feedback ingest-engine
```
(Inside the OneGRC monorepo the build context is the repository root: `--build-arg PKG=packages/ingest-engine -f packages/ingest-engine/Dockerfile .`
— `start.sh` works this out.) An application calling the engine puts the same `INGEST_API_KEY`
in its own configuration; OneGRC's is `server/.env` (`INGEST_URL`, `INGEST_API_KEY`).

| Symptom | Cause · fix |
|---|---|
| `AI_API_KEY is empty` | put it in `.env`, or `AI_API_KEY=… ./start.sh --yes` |
| `401` from every call | send the key: `-H "x-api-key: $INGEST_API_KEY"`; check it is the value in the engine's `.env` |
| `503 no_provider` | the engine's `.env` has no `AI_API_KEY` (each service reads only its own `.env`) |
| `port 3002 is held by …` | another process; `start.sh` stops an engine of its own, anything else you stop yourself, or change `INGEST_PORT` |
| the docker daemon is not running | Docker Desktop / OrbStack / `colima start` — or `./start.sh --local` |
| the container is up but not reachable on the port | it was started while something else held the port; `./start.sh` again |

### Inside this repository
```bash
packages/ingest-engine/start.sh       # creates .env from .env.example (preset for Docker), asks for AI_API_KEY — the only
                                      # input — generates INGEST_API_KEY, installs, tests, builds and runs the container,
                                      # prints test commands. AI_API_KEY=… ./start.sh --yes for scripts · --no-test · --local · --stop
                                      # OneGRC's server/.env must carry the same INGEST_API_KEY (INGEST_URL=http://localhost:3002)
npm run ingest:serve                  # on :3002 (INGEST_PORT), reads packages/ingest-engine/.env
docker compose up ingest              # the same, as its own container
```
Environment (`packages/ingest-engine/.env.example`): `AI_BASE_URL` `AI_API_KEY` `AI_MODEL`
`AI_TRIAGE_MODEL` (the model provider), `INGEST_PORT`, `INGEST_API_KEY`, `INGEST_TYPES_DIR` (the
catalogue), `INGEST_FEEDBACK_DIR` (examples, the review queue and metrics — a volume in Docker),
`INGEST_AUTO_THRESHOLD`, `INGEST_CACHE_DIR`, `INGEST_TESSDATA_DIR`, `OCR_WORKERS`,
`INGEST_WINDOW_CHARS`, and the sections strategy's tuning (`CLAUSES_WINDOW_CHARS`,
`TRIAGE_MIN_CHARS`, `EXTRACT_*`). No database.

### Moving it to its own repository
It already is a self-contained package: copy `packages/ingest-engine/` as-is (its `package.json`
lists every runtime dependency — `hono` `@hono/node-server` `zod` `unpdf` `@napi-rs/canvas`
`tesseract.js` `html-to-text` `mammoth` `mailparser` `dotenv`), run `npm install`, `npm test`,
`npm start`. The `Dockerfile` builds from the package directory too (see its header). Nothing in
`src/` imports anything outside the package.

```
src/app.ts        HTTP surface           src/service.ts   extraction + merge      src/inputs.ts   acquire · parse · e-mail
src/profiles.ts   the shape language     src/text.ts      PDF/DOCX/HTML/text      src/ocr.ts      tesseract pool
src/catalogue.ts  type packs · versions · extends      src/classify.ts  signatures + model     src/feedback.ts  learned examples
src/metrics.ts    drift rates · alerts   src/review.ts    queue · clusters · proposals            types/          the starter catalogue
src/llm.ts        structured chat calls  src/cache.ts     content-hash cache      src/env.ts      configuration
src/pipeline.ts · sections.ts   the `sections` strategy (split · identity · triage · parallel extract · merge)
src/index.ts      library exports        src/main.ts      standalone entrypoint   tests/          contract tests
```

### Scaling out

The engine keeps no request state, so run as many replicas as the load needs behind a load balancer.
Each process runs at most `INGEST_CONCURRENCY` extractions at once and lets `INGEST_MAX_QUEUE` wait;
beyond that it answers `503 busy` with a message, and a load balancer should retry on another replica.
`GET /v1/health` reports `load: { running, waiting, concurrency, maxQueue }`. Replicas that should
learn from the same corrections share `INGEST_FEEDBACK_DIR` and `INGEST_TYPES_DIR` (a shared volume).

### Operating notes
- **Model provider**: any OpenAI-compatible chat endpoint with `response_format: json_schema`.
  Cost is dominated by document length; the envelope reports tokens and an estimate per call.
- **OCR**: English by default (`eng`); add languages in `ocr.ts` (`createWorker('eng+hin')`).
  Scans at 2× render scale; a 40-page scan takes minutes — stream and show progress.
- **Limits**: fetches time out at 30 s, model calls at 180 s with three retries; a single
  document is windowed, so length is not a hard limit, only cost.
- **Security**: secrets never leave the process; the API key is compared in full; uploaded bytes
  are not stored by the engine (only the parsed text, in the cache, keyed by hash). Put the
  standalone service behind TLS and restrict who can reach it.
- **Versioning**: `promptVersion` in `/v1/health` changes when built-in prompts change; results
  cached under an older version are not reused.

---

## 7 · Worked examples

**A regulator page → a change record**
`POST /v1/extract {"url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=10435", "type": "regulation/change@1"}`
→ `data.regulator = "Reserve Bank of India"`, `referenceNumber`, `summary`, `actionsRequired[]`, `deadlines[]`.

**A scanned invoice (PNG photo) → an invoice record**
`-F file=@photo.png -F type=finance/invoice@1` → OCR (1 page) → supplier, number, line items, taxes, total.

**An e-mail with a SOC 2 report → assurance evidence**
`-F file=@vendor.eml -F type=assurance/report@1 -F emailScope=attachments` → one entry per
attachment with `reportType`, `periodStart/End`, `scope[]`, `exceptions[]`; the body is skipped.

**A new kind of document, learned in a day**
Three delivery challans arrive through `type: auto` from a shared mailbox → each is read as
`generic` with `needsReview` → `GET /v1/review/clusters` groups them → `POST /v1/review/propose`
drafts `logistics/delivery-challan` (fields `deliveryChallanNumber`, `transporter`, `consignee`,
`goodsDescription`, `vehicleNumber`, `dateOfDispatch`, `receivedBy`; signature regexes) → a person
accepts it with the returned `PUT /v1/types/logistics/delivery-challan` → the next challan is
classified at 0.95 and extracted into that shape; confirming it through `/v1/feedback` makes it an
example. (This is the sequence run in testing.)

**A regulation → clauses for review** (OneGRC's own path)
`-F file=@direction.pdf -F type=regulation/clauses@1 -F 'subject={"name":"State Bank of India","description":"scheduled commercial bank…"}' -F rules=@server/rules/rbl/file.md`
→ `data.identity` (title, authority, type, reference, dates) and `data.units[]` each with provision, plain meaning, key parts, penalty tiers, confidence; OneGRC grades severity and marks each `verified: false` until a person confirms it.
