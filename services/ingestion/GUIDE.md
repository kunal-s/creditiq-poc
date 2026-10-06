# Configuration guide

Every behaviour is published configuration under `config/ingestion/`. A change is a new version;
nothing is edited in place. Run `python -m ingestion.cli config-validate config/ingestion` before
publishing (`creditiq config publish`): it compiles every regex and checks every cross-reference.

## Add a document type

1. **`document_types.json`**: add the type with its `fields` and `tables` (name, type, required).
2. **`signals.yaml`**: add `required` (all must match), `supporting`, `contrary` regexes. Choose
   `required` phrases that appear on every document of the kind and rarely elsewhere; put the phrases
   of look-alikes under `contrary` (a provisional statement against an audited one).
3. **`fields.yaml`**: for each field say where it is printed.
4. **`validators.yaml`**: name the checks a clerk would make.
5. Add a fixture with its expected values and run the tests.

## Read a field

Tried in this order; the first hit wins.

```yaml
company_name: {aliases: ['Name of Company']}                  # label, then the value in the next column or line
cin:          {identifier: cin, validators: ['format:cin']}   # scan for the identifier format
roc:          {patterns: ['Office of the (Registrar of Companies[^\n]*)']}   # group 1 is the value
directors:    {patterns: [{regex: '...are\s+(.+?)\.\s*$', flags: ims, multi: true, split: '\s+and\s+', strip: '^(?:Smt|Sri)\.?\s+'}]}
objects:      {patterns: [{regex: '...', flags: ims, span_pages: true}]}      # a value that runs over a page break
purpose:      {llm: false}                                                    # never ask the model for this one
```

Flags: `i` ignore case, `m` multiline, `s` dot matches newline. `take: rest` keeps the whole rest of
the line. `next_line: false` stops a label with no value from borrowing the next line. Dates and
amounts are normalised from the schema type (`date`, `number`); a value that does not parse is
reported missing with the raw text kept. What the model may fill is set by `llm.yaml: fill`
(`missing`: any field the deterministic pass left empty; `flagged`: only fields marked `llm: true`).

## Read a table

```yaml
transactions:
  start: '^Date\s+Particulars\s+Reference'     # the header line; header_lines: extra header lines below it
  end: '^Statement Summary'
  multi_page: true                             # continue on the following pages; a repeated header re-anchors
  row_start_col: date                          # a line starts a row when this cell matches row_start
  row_start: '^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$'
  repair: {kind: running_balance, debit: debit, credit: credit, balance: balance}
  columns:
    - {name: date, header: '^Date$'}           # header: a regex for ONE word of the header; nth picks the nth match
    - {name: debit, header: '^Debit$', align: right}
    - {name: signature, header: '^Signature$', emit: false}   # a boundary column that is not output
```

Columns of the schema that have no entry here come out `null`. Without `row_start`, a line with a
label and a value starts a row; `text_only: continuation` makes label-only lines join the row above.
Lines farther than `max_attach` points from every row are not part of the table.

## Noise

`routing.yaml → reading.boilerplate` lists regexes for lines that repeat on every page (footers,
page numbers): they stay in the index, flagged, and are left out of the text. Text set at an angle
(watermarks, stamps) is dropped while `drop_rotated_text` is true.

## Thresholds

`quality.yaml` (page grades, limits, re-scan wording), `confidence.yaml` (weights, caps, review
threshold), `decision.yaml` (accept and review bounds). A threshold change republishes as a new
version and the cases are re-run.

## Prompts and model

`llm.yaml` holds the provider, model id, endpoint, the environment variable for the key, window
sizes and the prompt text. Prompt text is part of the published version, so editing it changes the
recording keys: re-record (`INGEST_MODEL_MODE=record`) against the new version. Another vendor means
another `Provider` class; the pipeline does not change.
