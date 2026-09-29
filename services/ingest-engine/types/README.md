# Type catalogue

One folder per document type, namespaced: `types/<namespace>/<type>/`. The engine loads it fresh
on every request (edits apply at once) and ships nothing else of its own beyond `generic`.

```
profile.json     version · description · extends? · strategy · instructions · fields | schema | unit/identity/triage
                 signatures?  cheap, deterministic hints used by `type: "auto"` before any model call
                 validators?  post-checks on the output → warnings on the response
rules.md         how to read this family of documents (appended to the prompt)
reference/*.md   lookups the prompt may cite (department codes, formats…) — capped at 12 000 chars
examples/*.json  { snippet, mail?, output, note? } — confirmed input→output pairs: few-shot for
                 extraction, snippets for classification, regression tests (npm run test:types)
```

- **Versions**: `version` in profile.json. A caller pins `type: "bank/statement@2"`; if the
  catalogue has moved to 3 the request is refused until the caller reviews and bumps the pin.
- **Inheritance**: `"extends": "bank/statement"` — fields merge by name, instructions and rules
  are appended, signatures and validators unioned, examples inherited (`sbi/statement` is the example).
- **Feedback** (`POST /v1/feedback`) lands under `INGEST_FEEDBACK_DIR/<namespace>/<type>/` and is
  loaded with the pack's own examples — the catalogue stays read-only content; what it learns lives
  next to it, as files a person can read, edit or delete.
- **Register over the API**: `PUT /v1/types/<namespace>/<type>` writes `profile.json`.
- Applications name a type they know (`type: "finance/invoice@1"`), or say `type: "auto"` and get
  `classification` + `needsReview` back for a person to settle.
